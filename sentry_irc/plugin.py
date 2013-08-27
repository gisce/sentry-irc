"""
sentry_irc.models
~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2012 by Eduard Carreras, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import socket
import re
import time
from random import randrange
from ssl import wrap_socket

from django import forms
from django.core.urlresolvers import reverse

from sentry.plugins.bases.notify import NotifyPlugin
from sentry.utils.http import absolute_uri

import sentry_irc


BASE_MAXIMUM_MESSAGE_LENGTH = 400
PING_RE = re.compile(r'^PING\s*:\s*(.*)$')


class IRCOptionsForm(forms.Form):
    server = forms.CharField()
    port = forms.IntegerField()
    room = forms.CharField(help_text="You can add multiple rooms separated "
                                     "by comma",
                           required=False)
    without_join = forms.BooleanField(required=False)
    user = forms.CharField(help_text="You can add multiple users to be "
                                     "notified separated by comma",
                           required=False)
    nick = forms.CharField()
    password = forms.CharField(required=False)
    ssl = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super(IRCOptionsForm, self).clean()
        room = cleaned_data.get('room', '')
        user = cleaned_data.get('user', '')
        if not any((user, room)):
            msg = u"Must put either a room or an user"
            for k in ('room', 'user'):
                self._errors[k] = self.error_class([msg])
        return cleaned_data


class IRCMessage(NotifyPlugin):
    author = 'Eduard Carreras'
    author_url = 'http://code.gisce.net/sentry-irc'
    title = 'IRC'
    conf_title = 'IRC'
    conf_key = 'irc'
    version = sentry_irc.VERSION
    project_conf_form = IRCOptionsForm

    # socket / read timeout
    timeout = 15.0

    def is_configured(self, project):
        go = self.get_option
        return (
            all(go(k, project) for k in ('server', 'port', 'nick'))
            and any(go(k, project) for k in ('room', 'user'))
        )

    def get_group_url(self, group):
        return absolute_uri(reverse('sentry-group', args=[
            group.team.slug,
            group.project.slug,
            group.id,
        ]))

    def on_alert(self, alert, **kwargs):
        project = alert.project

        message = self.format_message(
            project,
            alert.message.encode('utf-8').splitlines()[0],
            'ALERT',
            alert.get_absolute_url(),
        )

        self.send_payload(project, message)

    def post_process(self, group, event, is_new, is_sample, **kwargs):
        project = event.project
        if not is_new or not self.is_configured(project):
            return

        message = self.format_message(
            project,
            event.message.encode('utf-8').splitlines()[0],
            event.get_level_display().upper(),
            self.get_group_url(group),
        )

        self.send_payload(project, message)

    def format_message(self, project, message, level, link):
        message_format = '[%s] %s %s (%s)'
        max_message_length = (
            BASE_MAXIMUM_MESSAGE_LENGTH
            - len(link)
            - len(level)
            - len(project.name)
            - len(message_format.replace('%s', ''))  # No of brackets/spaces
        )
        if len(message) > max_message_length:
            message = message[0:max_message_length-3] + '...'

        return message_format % (level, project.name, message, link)

    def send_payload(self, project, message):
        server = self.get_option('server', project)
        port = self.get_option('port', project)
        nick = self.get_option('nick', project)
        rooms = self.get_option('room', project) or ''
        without_join = self.get_option('without_join', project)
        users = self.get_option('user', project) or ''
        rooms = [x.startswith('#') and x or '#%s' % x
                 for x in (x.strip() for x in rooms.split(','))]
        users = [x.strip() for x in users.split(',')]
        password = self.get_option('password', project)
        ssl_c = self.get_option('ssl', project)

        start = time.time()
        irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        irc.settimeout(self.timeout)
        irc.connect((server, port))
        if ssl_c:
            ircsock = wrap_socket(irc)
        else:
            ircsock = irc
        if password:
            ircsock.send("PASS %s\n" % password)
        ircsock.send("USER %s %s %s :Sentry IRC bot\n" % ((nick,) * 3))
        ircsock.send("NICK %s\n" % nick)
        while (time.time() - start) < self.timeout:
            ircmsg = ircsock.recv(2048).strip('\n\r')
            pong = PING_RE.findall(ircmsg)
            if pong:
                ircsock.send("PONG %s\n" % pong)
            if re.findall(' 433 \* %s' % nick, ircmsg):
                nick += '%s' % randrange(1000, 2000)
                ircsock.send("NICK %s\n" % nick)
                ircmsg = ircsock.recv(2048)
            if re.findall(' 00[1-4] %s' % nick, ircmsg):
                for room in rooms:
                    if not without_join:
                        ircsock.send("JOIN %s\n" % room)
                    ircsock.send("PRIVMSG %s :%s\n" % (room, message))
                    if not without_join:
                        ircsock.send("PART %s\n" % room)
                for user in users:
                    ircsock.send("PRIVMSG %s :%s\n" % (user, message))
                break

        ircsock.send("QUIT\n")

        # try to flush pending buffer
        while (time.time() - start) < self.timeout and ircmsg:
            ircmsg = ircsock.recv(2048)
        irc.close()
