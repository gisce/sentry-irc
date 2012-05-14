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
from sentry.models import ProjectOption
from sentry.plugins import Plugin, register



class IRCOptionsForm(forms.Form):
    server = forms.CharField()
    port = forms.IntegerField()
    room = forms.CharField()
    nick = forms.CharField()
    password = forms.CharField(required=False)
    ssl = forms.BooleanField(required=False)


@register
class IRCMessage(Plugin):
    author = 'Eduard Carreras'
    author_url = 'http://code.gisce.net/sentry-irc'
    title = 'IRC'
    conf_title = 'IRC'
    conf_key = 'irc'
    project_conf_form = IRCOptionsForm

    def is_configured(self, project):
        return all((self.get_option(k, project)
                   for k in ('server', 'port', 'nick', 'room')))

    def post_process(self, group, event, is_new, is_sample, **kwargs):
        if not is_new:
            return
        server = self.get_option('server', event.project)
        port = self.get_option('port', event.project)
        nick = self.get_option('nick', event.project)
        room = self.get_option('room', event.project)
        if not room.startswith('#'):
            room = '#%s' % room
        password = self.get_option('password', event.project)
        ssl = self.get_option('ssl', event.project)
        link = '%s/%s/group/%d/' % (settings.URL_PREFIX, group.project.slug,
                                    group.id)
        message = '[%s] %s (%s)' % (event.server_name, event.message, link)
        self.send_payload(server, port, nick, password, room, ssl, message)

    def send_payload(self, server, port, nick, password, room, ssl_c, message):
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
            if re.findall(' 00[1-4] %s' % nick, ircmsg):
                ircsock.send("JOIN %s\n" % room)
            pong = re.findall('^PING\s*:\s*(.*)$', ircmsg)
            if pong:
                ircsock.send("PONG %s\n" % pong)
            if re.findall(' 366 %s %s :' % (nick, room), ircmsg):
                ircsock.send("PRIVMSG %s :%s\n" % (room, message))
                ircsock.send("PART %s\n" % room)
                break
        irc.send("QUIT\n")
        irc.close()
