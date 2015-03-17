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

NOTRACK = { 'mpris:trackid': '/org/mpris/MediaPlayer2/TrackList/NoTrack' }


def convert_dict (dict):
    if dict['id'] == 0:
        return NOTRACK

    # id is mandatory
    ret_dict = {
        'mpris:trackid': dbus.ObjectPath('/org/mpris/MediaPlayer2/TrackList/{}'.format(dict['id']))
    }

    def translate_rating(x): return x/5.
    def translate_duration(x): return x*1000L
    def identity(x): return x

    key_list = [('duration', 'mpris:length', translate_duration),
                ('tracknr', 'xesam:trackNumber', identity),
                ('title', 'xesam:title', identity),
                ('artist', 'xesam:artist', identity),
                ('album', 'xesam:album', identity),
                ('genre', 'xesam:genre', identity),
                ('comment', 'xesam:comment', identity),
                ('rating', 'xesam:userRating', translate_rating)]

    for xmms2_key, mpris_key, trans in key_list:
        try: ret_dict[mpris_key] = trans(dict[xmms2_key])
        except KeyError: pass

    ret_dict=dbus.Dictionary(ret_dict, signature='sv')

    return ret_dict

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
    def __init__ (self, xmms2, properties_changed):
        self.xmms2 = xmms2
        self.properties_changed = properties_changed
        self.playback_status = 'Stopped'
        self.metadata = NOTRACK
        self.volume = 1.0
        self.position = 1

        self.xmms2.playback_status(cb=self._cb_set_status)
        self.xmms2.broadcast_playback_status(cb=self._cb_status_changed)

        self.xmms2.playback_current_id(cb=self._cb_set_id)
        self.xmms2.broadcast_playback_current_id(cb=self._cb_set_id)

        self.xmms2.broadcast_playback_volume_changed(cb=self._cb_set_volume)
        self.xmms2.playback_volume_get(cb=self._cb_set_volume)

        self.xmms2.playback_playtime(cb=self._cb_set_position)
        self.xmms2.signal_playback_playtime(cb=self._cb_set_position)

    def _cb_status_changed(self,res):
        self._cb_set_status(res)
        self.properties_changed({ 'PlaybackStatus': self.playback_status }, [])

    def _cb_set_status(self,res):
        status = res.value()
        if status == PLAYBACK_STATUS_STOP:
            self.playback_status = 'Stopped'
        elif status == PLAYBACK_STATUS_PAUSE:
            self.playback_status = 'Paused'
        else:
            self.playback_status = 'Playing'

    def _cb_set_id(self,res):
        trackid = res.value()
        if trackid == 0:
            self.metadata = NOTRACK
            self.properties_changed({ 'Metadata': self.metadata }, [])
        else:
            self.xmms2.medialib_get_info(trackid,cb=self._cb_set_metadata)

    def _cb_set_metadata(self,res):
        metadata = res.value()
        self.metadata = convert_dict(metadata)
        self.properties_changed({ 'Metadata': self.metadata }, [])

    def _cb_set_volume(self,res):
        self.volume = res.value()['master']/100.
        self.properties_changed({ 'Volume': self.volume }, [])

    def _cb_set_position(self,res):
        self.position = res.value()*1000L
        self.properties_changed({ 'Position': self.position }, [])

    CANGONEXT = True
    CANGOPREVIOUS = True
    CANPLAY = True
    CANPAUSE = True
    CANSEEK = True
    CANCONTROL = True
    RATE = 1.0

    def Get(self, property_name):
        return self.GetAll()[property_name]

    def GetAll(self):
        return dbus.Dictionary({
            'PlaybackStatus': self.playback_status,
            # 'LoopStatus': 'None',
            'Rate': self.RATE,
            # 'Shuffle': False,
            'Metadata': self.metadata,
            'Volume': self.volume,
            'Position': self.position,
            'MinimumRate': self.RATE,
            'MaximumRate': self.RATE,
            'CanGoNext': self.CANGONEXT,
            'CanGoPrevious': self.CANGOPREVIOUS,
            'CanPlay': self.CANPLAY,
            'CanPause': self.CANPAUSE,
            'CanSeek': self.CANSEEK,
            'CanControl': self.CANCONTROL
        }, signature='sv')

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
        self.player = player(xmms2,self.player_properies_changed)


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

    def player_properies_changed(self, changed_propreties, invalidated_properties):
        self.PropertiesChanged(MEDIAPLAYER_PLAYER, changed_propreties, invalidated_properties)

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

    @dbus.service.signal (dbus.PROPERTIES_IFACE, signature='sa{sv}as')
    def PropertiesChanged(self, interface_name, changed_properties,
                          invalidated_properties):
        pass




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
