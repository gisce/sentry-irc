"""
sentry_irc.models
~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2012 by Eduard Carreras, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from django import forms

from sentry.models import ProjectOption
from sentry.plugins import Plugin, register



class IRCOptionsForm(forms.Form):
    server = forms.CharField(help_text="Server")
    port = forms.IntegerField(help_text="Port")
    room = forms.CharField(help_text="Room")
    nick = forms.CharField(help_text="Nick")
    password = forms.CharField(widget=forms.PasswordInput,
                               help_text="Password")
    ssl = forms.BooleanField(help_text="Ssl")


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
        password = self.get_option('password', event.project)
        ssl = self.get_option('ssl', event.project)
        message = '[%s] %s' % (event.server_name, event.message)
        self.send_payload(server, port, nick, password, room, ssl, message)

    def send_payload(self, server, port, nick, password, room, ssl_c, message):
        import socket
        from ssl import wrap_socket
        irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        irc.connect((server, port))
        if ssl_c:
            ircsock = wrap_socket(irc)
        else:
            ircsock = irc
        ircsock.send("USER %s %s %s :Sentry IRC bot\n" % ((nick,) * 3))
        ircsock.send("NICK %s\n" % nick)
        ircsock.send("JOIN %s\n" % room)
        while 1:
            ircmsg = ircsock.recv(2048).strip('\n\r') # receive data from the server
            print(ircmsg) # Here we print what's coming from the server
            if ircmsg.find("PING :") != -1: # if the server pings us then we've got to respond!
                ircsock.send("PONG :pingis\n")
                break
        ircsock.send("PRIVMSG %s %s\n" % (room, message))
        irc.send("PART %s\n" % room)
        irc.send("QUIT\n")
        irc.close()
