#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  xmms2-mpris2-bridge - MPRIS v2 interface for XMMS2
#  Copyright (C) 2012      Rémi Vanicat
#  with code from xmms2-mpris-bridge
#  Copyright (C) 2008-2010 Thomas Frauendorfer
#  Copyright (C) 2010      Hannes Janetzek


"""
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

3. The name of the author may not be used to endorse or promote products
   derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR "AS IS" AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
"""

import sys
try:
    import xmmsclient
    import xmmsclient.glib
    from xmmsclient.consts import *
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    import gobject
    import urllib
except ImportError:
    print "Could not start the XMMS2 MPRIS2 bridge."
    print "Please install python bindings for xmms2, dbus and gobject"
    sys.exit(1)

MPRIS = "org.mpris.MediaPlayer2.xmms2"
MEDIAPLAYER = "org.mpris.MediaPlayer2"
MEDIAPLAYER_PLAYER = "org.mpris.MediaPlayer2.Player"

# The name reported to dbus
DBUS_CLIENTNAME = "XMMS2_MPRIS2"
# The name reported to xmms2, only alphanumeric caracters
XMMS2_CLIENTNAME = 'MPRIS2_bridge'

class root():
    def __init__ (self, xmms2):
        self.xmms2 = xmms2

    IDENTITY = "Xmms2"
    CANQUIT = True
    CANRAISE = False
    HASTRACKLIST = False
    FULLSCREEN = False
    CANSETFULLSCREEN = False
    SUPPORTEDURISCHEMES = [ 'file', 'http', 'rtsp' ], # TODO : lot more to put there...
    SUPPORTEDMIMETYPES = [ 'audio/mpeg', 'application/ogg', ], # TODO : lot more to put there...

    def Get(self, property_name):
        return self.GetAll()[property_name]

    def GetAll(self):
        return { 'CanQuit': self.CANQUIT,
                 'Fullscreen' : self.FULLSCREEN,
                 'CanSetFullscreen' : self.CANSETFULLSCREEN,
                 'CanRaise': self.CANRAISE,
                 'HasTrackList': self.HASTRACKLIST,
                 'Identity' : self.IDENTITY,
                 # 'DesktopEntry' : ...,
                 'SupportedUriSchemes' : self.SUPPORTEDURISCHEMES,
                 'SupportedMimeTypes' : self.SUPPORTEDMIMETYPES
             }

    def Raise (self):
        pass

    def Quit (self):
        self.xmms2.quit()

## The org.mpris.MediaPlayer2.Player interface
class player():
    def __init__ (self, xmms2):
        self.xmms2 = xmms2

    def Get(self, property_name):
        return self.GetAll()[property_name]

    def GetAll(self):
        return {
            'PlaybackStatus': 'Stopped',
            # 'LoopStatus': 'None',
            'Rate': 1.0,
            # 'Shuffle': False,
            'Metadata': { 'mpris:trackid': 321 },
            'Volume': 1.0,
            'Position': 1,
            'MinimumRate': 1.0,
            'MaximumRate': 1.0,
            'CanGoNext': True,
            'CanGoPrevious': True,
            'CanPlay': True,
            'CanPause': True,
            'CanSeek': False,
            'CanControl': True,
        }

    def Next(self):
        self.xmms2.playlist_set_next_rel (1)
        self.xmms2.playback_tickle ()

    def Previous(self):
        self.xmms2.playlist_set_next_rel (-1)
        self.xmms2.playback_tickle ()

    def Pause(self):
        self.xmms2.playback_pause()

    def PlayPause(self):
        self.xmms2.playback_status(cb=self._cb_handle_play_pause)

    def _cb_handle_play_pause(self, status):
        status = status.value()
        if status == PLAYBACK_STATUS_STOP or status == PLAYBACK_STATUS_PAUSE:
            self.xmms2.playback_start()
        else:
            self.xmms2.playback_pause()

    def Stop(self):
        self.xmms2.playback_stop()

    def Play(self):
        self.xmms2.playback_start()

    def Seek(self,position):
        self.xmms2.playback_seek_ms(position)

    def SetPosition(self,trackid, position):
        pass

    def OpenUri(self,uri):
        pass

    def Seeked (self, caps):
        pass

class mpris(dbus.service.Object):
    def __init__ (self, xmms2):
        self.xmms2 = xmms2
        dbus.service.Object.__init__ (self, dbus.SessionBus(), "/org/mpris/MediaPlayer2")
        self.root = root(xmms2)
        self.player = player(xmms2)


    @dbus.service.method (MEDIAPLAYER, in_signature='', out_signature='')
    def Raise (self):
        self.root.Raise()

    @dbus.service.method (MEDIAPLAYER, in_signature='', out_signature='')
    def Quit (self):
        self.root.Quit()

    @dbus.service.method(MEDIAPLAYER_PLAYER, in_signature='', out_signature='')
    def Next(self):
        self.player.Next()

    @dbus.service.method (MEDIAPLAYER_PLAYER, in_signature='', out_signature='')
    def Previous(self):
        self.player.Previous()

    @dbus.service.method (MEDIAPLAYER_PLAYER, in_signature='', out_signature='')
    def Pause(self):
        self.player.Pause()

    @dbus.service.method (MEDIAPLAYER_PLAYER, in_signature='', out_signature='')
    def PlayPause(self):
        self.player.PlayPause()

    @dbus.service.method (MEDIAPLAYER_PLAYER, in_signature='', out_signature='')
    def Stop(self):
        self.player.Stop()

    @dbus.service.method (MEDIAPLAYER_PLAYER, in_signature='', out_signature='')
    def Play(self):
        self.player.Play()

    @dbus.service.method (MEDIAPLAYER_PLAYER, in_signature='x', out_signature='')
    def Seek(self,position):
        self.player.Seek()

    @dbus.service.method (MEDIAPLAYER_PLAYER, in_signature='ox', out_signature='')
    def SetPosition(self,trackid, position):
        self.player.SetPosition(trackid, position)

    @dbus.service.method (MEDIAPLAYER_PLAYER, in_signature='s', out_signature='')
    def OpenUri(self,uri):
        self.player.OpenUri(uri)

    @dbus.service.signal (MEDIAPLAYER_PLAYER, signature='x')
    def Seeked (self, caps):
        self.player.Seeked(caps)

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='ss', out_signature='v')
    def Get(self, interface_name, property_name):
        if interface_name == MEDIAPLAYER:
            return self.root.Get(property_name)
        elif interface_name == MEDIAPLAYER_PLAYER:
            return self.player.Get(property_name)
        else:
            raise dbus.exceptions.DBusException(
                'com.example.UnknownInterface',
                'The Foo object does not implement the %s interface' % interface_name)

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface_name):
        if interface_name == MEDIAPLAYER:
            return self.root.GetAll()
        elif interface_name == MEDIAPLAYER_PLAYER:
            return self.player.GetAll()
        else:
            raise dbus.exceptions.DBusException(
                'com.example.UnknownInterface',
                'The Foo object does not implement the %s interface' % interface_name)

class Xmms2MPRIS:
    def __init__(self):
        # The glib mainloop is used to glue the xmms2 and the dbus connection
        # together, because they both provide their own mainloop and I'm
        # too lazy to write a sprecial connector
        self.ml = gobject.MainLoop(None, False)
        self.xmms2 = xmmsclient.XMMS(XMMS2_CLIENTNAME)
        #connect to the xmms2 server, it should be running as it started us
        #TODO: perhaps this could make use of a bi more error handling
        try:
            self.xmms2.connect(disconnect_func = self._on_server_quit)
        except IOError, detail:
            print 'Connection failed:', detail
            sys.exit(1)
        self.xmmsconn = xmmsclient.glib.GLibConnector(self.xmms2)

        self.dbusconn = DBusGMainLoop(set_as_default=True)
        dbus.SessionBus().request_name(MPRIS);

        self.mpris = mpris(self.xmms2)
        # self.mpris_player = mpris_Player(self.xmms2)
        # self.mpris_tracklist = mpris_TrackList(self.xmms2, self.mpris_player)

    def _on_server_quit(self, result):
        self.ml.quit ()


def start_mpris():
    client = Xmms2MPRIS()
    client.ml.run ()
    return client

def usage():
    print "Usage: %s [start]" % sys.argv[0]

if __name__ == "__main__":
    if len(sys.argv) == 1:
        start_mpris()
    elif len(sys.argv) == 2:
        if sys.argv[1] == 'start':
            start_mpris()
        else:
            usage()
    else:
        usage()
