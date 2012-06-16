"""
sentry_irc.models
~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2012 by Eduard Carreras, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import socket
import re
from ssl import wrap_socket

from django import forms

from sentry.conf import settings
from sentry.plugins import Plugin

import sentry_irc


class IRCOptionsForm(forms.Form):
    server = forms.CharField()
    port = forms.IntegerField()
    room = forms.CharField()
    without_join = forms.BooleanField(required=False)
    nick = forms.CharField()
    password = forms.CharField(required=False)
    ssl = forms.BooleanField(required=False)


class IRCMessage(Plugin):
    author = 'Eduard Carreras'
    author_url = 'http://code.gisce.net/sentry-irc'
    title = 'IRC'
    conf_title = 'IRC'
    conf_key = 'irc'
    version = sentry_irc.VERSION
    project_conf_form = IRCOptionsForm

    def is_configured(self, project):
        return all((self.get_option(k, project)
                   for k in ('server', 'port', 'nick', 'room')))

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
        room = self.get_option('room', project)
        without_join = self.get_option('without_join', project)
        if not room.startswith('#'):
            room = '#%s' % room
        password = self.get_option('password', project)
        ssl_c = self.get_option('ssl', project)

        irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        irc.connect((server, port))
        if ssl_c:
            ircsock = wrap_socket(irc)
        else:
            ircsock = irc
        ircsock.send("USER %s %s %s :Sentry IRC bot\n" % ((nick,) * 3))
        ircsock.send("NICK %s\n" % nick)
        while 1:
            ircmsg = ircsock.recv(2048).strip('\n\r')
            pong = re.findall('^PING\s*:\s*(.*)$', ircmsg)
            if pong:
                ircsock.send("PONG %s\n" % pong)
            if re.findall(' 00[1-4] %s' % nick, ircmsg):
                if not without_join:
                    ircsock.send("JOIN %s\n" % room)
                ircsock.send("PRIVMSG %s :%s\n" % (room, message))
                if not without_join:
                    ircsock.send("PART %s\n" % room)
                break
        ircsock.recv(2048)
        ircsock.send("QUIT\n")
        ircsock.close()
