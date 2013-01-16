"""
sentry_irc.models
~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2012 by Eduard Carreras, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import socket
import re
from random import randrange
from ssl import wrap_socket

from django import forms

from sentry.conf import settings
from sentry.plugins import Plugin

import sentry_irc


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


class IRCMessage(Plugin):
    author = 'Eduard Carreras'
    author_url = 'http://code.gisce.net/sentry-irc'
    title = 'IRC'
    conf_title = 'IRC'
    conf_key = 'irc'
    version = sentry_irc.VERSION
    project_conf_form = IRCOptionsForm

    def is_configured(self, project):
        return (
            all((self.get_option(k, project)
                 for k in ('server', 'port', 'nick'))
            ) and any((self.get_option(k, project)
                for k in ('room', 'user'))
            )
        )

    def post_process(self, group, event, is_new, is_sample, **kwargs):
        if not is_new or not self.is_configured(event.project):
            return
        link = '%s/%s/group/%d/' % (settings.URL_PREFIX, group.project.slug,
                                    group.id)
        message = '[%s] %s (%s)' % (event.server_name, event.message, link)
        self.send_payload(event.project, message)

    def send_payload(self, project, message):
        server = self.get_option('server', project)
        port = self.get_option('port', project)
        nick = self.get_option('nick', project)
        rooms = self.get_option('room', project)
        without_join = self.get_option('without_join', project)
        users = self.get_option('user', project) or ''
        rooms = [x.startswith('#') and x or '#%s' % x
                 for x in [x.strip() for x in rooms.split(',')]]
        users = [x.strip() for x in users.split(',')]
        password = self.get_option('password', project)
        ssl_c = self.get_option('ssl', project)

        irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        irc.connect((server, port))
        if ssl_c:
            ircsock = wrap_socket(irc)
        else:
            ircsock = irc
        if password:
            ircsock.send("PASS %s\n" % password)
        ircsock.send("USER %s %s %s :Sentry IRC bot\n" % ((nick,) * 3))
        ircsock.send("NICK %s\n" % nick)
        while 1:
            ircmsg = ircsock.recv(2048).strip('\n\r')
            pong = re.findall('^PING\s*:\s*(.*)$', ircmsg)
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
        ircsock.recv(2048)
        ircsock.send("QUIT\n")
        irc.close()
