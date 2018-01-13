#!/usr/bin/env python

# Pykaraoke VLC

#******************************************************************************
#**** Copyright (C) 2018  Ken Williams GW3TMH (ken@kensmail.uk)            ****
#**** Copyright (C) 2010  Kelvin Lawson (kelvinl@users.sourceforge.net)    ****
#**** Copyright (C) 2010  PyKaraoke Development Team                       ****
#****                                                                      ****
#**** This library is free software; you can redistribute it and/or        ****
#**** modify it under the terms of the GNU Lesser General Public           ****
#**** License as published by the Free Software Foundation; either         ****
#**** version 3 of the License, or (at your option) any later version.     ****
#****                                                                      ****
#**** This library is distributed in the hope that it will be useful,      ****
#**** but WITHOUT ANY WARRANTY; without even the implied warranty of       ****
#**** MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU    ****
#**** Lesser General Public License for more details.                      ****
#****                                                                      ****
#**** You should have received a copy of the GNU Lesser General Public     ****
#**** License along with this library; if not, write to the                ****
#**** Free Software Foundation, Inc.                                       ****
#**** 59 Temple Place, Suite 330                                           ****
#**** Boston, MA  02111-1307  USA                                          ****
#******************************************************************************

import wx
import vlc
import sys
import os
from pykconstants import *
from pykenv import env

class vlcPlayer(wx.Frame):
    
    def __init__(self, Settings=None, errorNotifyCallback=None, doneCallback=None):
        
        self.Settings = Settings
        
        if self.Settings.NoFrame == True:
            default = wx.NO_BORDER
        else:
            default = wx.DEFAULT_FRAME_STYLE
            
        if env == ENV_POSIX:    
            wx.Frame.__init__(self, None, -1, title = "PyKaraoke " + PROGRAM_VERSION, pos = self.Settings.PlayerPosition, size = self.Settings.PlayerSize, style = default)
        else:
            wx.Frame.__init__(self, None, -1, title = "PyKaraoke " + PROGRAM_VERSION, size = self.Settings.PlayerSize, style = default)    

        if self.Settings.FullScreen == True:
            self.ShowFullScreen(True)
                
        # The video panel
        self.videopanel = wx.Panel(self, -1)
        self.videopanel.SetBackgroundColour(wx.BLUE)
        
        # The ticker panel
        self.marquepanel = wx.Panel(self, -1)
        self.marquepanel.SetBackgroundColour(wx.BLUE)
        
        # Put video panel in sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.videopanel, 20, flag = wx.EXPAND)
        sizer.Add(self.marquepanel, 1, flag = wx.GROW)
        self.SetSizer(sizer)
        
        self.TickerText = ""
         
        self.MyTicker = Ticker(self.marquepanel, size=(self.GetSize().GetWidth(), self.GetSize().GetHeight() / 20))

        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.Show(True)
               
        self.Bind(wx.EVT_SIZE, self.OnSize)

        # Create vlc instance
        self.Instance = vlc.Instance("--no-xlib")
        self.vlcplayer = self.Instance.media_player_new()

        # Caller can register a callback by which we
        # print out error information
        if errorNotifyCallback:
            self.ErrorNotifyCallback = errorNotifyCallback
        else:
            self.ErrorNotifyCallback = None
            
        # Caller can register a callback so we
        # know when the file is finished
        if doneCallback:
            self.SongFinishedCallback = doneCallback
        else:
            self.SongFinishedCallback = None

        self.filename = ""
        
    def OnSize(self, event):
        event.Skip()
        self.MyTicker.Stop()
        self.MyTicker.Destroy()                
        self.MyTicker = Ticker(self.marquepanel, size=(self.GetSize().GetWidth(), self.GetSize().GetHeight() / 20))
        self.MyTicker.SetText(self.TickerText)    


    # Poll so volume can be changed in real time
    def Poll(self):
         # Set volume
        vol = self.Settings.Volume
        self.vlcplayer.audio_set_volume(vol * 2)
        length = self.vlcplayer.get_length()
        pos = self.vlcplayer.get_time()
        if length > 2000:
            if pos > (length - 1000):
                self.vlcplayer.stop()
                self.SongFinishedCallback()
        return
        
        
    # Singers list
    def Singers(self, singerslist):
        self.TickerText = singerslist
        self.MyTicker.SetText(self.TickerText)    
        

    # Play button only works when nothing is being played
    def Play(self, filename):
        # Only play if player not busy
        pos = self.vlcplayer.get_time()
        if pos != -1:
            # Player is busy
            return False
        
        # Player free play file
        self.filename = filename
      
        self.PlaySomething(self.filename)
        return True
    

    # Pause video
    def Pause(self):
        self.vlcplayer.pause()


    # Rewind plays file again from start       
    def Rewind(self):
        if self.vlcplayer.get_length() > 0:
            self.PlaySomething(self.filename)
        
        
    def Stop(self):
        self.vlcplayer.stop()
        self.SongFinishedCallback()


    # Give the length of song in seconds
    def GetLength(self):
        length = self.vlcplayer.get_length()
        return length / 1000


    # Get how many seconds the song has played for.
    # Pykaraoke expects a millisecond value here
    # so multiply by 1000
    def GetPos(self):
        pos = self.vlcplayer.get_time()
        return pos / 1000
    
        
    # Function to close down window
    def Close(self):
        return


    # Prevent window from being closed
    def OnClose(self, event):        
        return
        
                
    # Called by play and rewind functions to actually play file
    def PlaySomething(self, filename):
        # Change filename extension to mp3 if it is cdg
        root, ext  = os.path.splitext(filename)
        if ext == '.cdg':
            filename = root + '.mp3'

        # Creation set the window id where to render VLC's video output
        handle = self.videopanel.GetHandle()
        
        self.Media = self.Instance.media_new(unicode(filename))
        
        # Title of file to play
        self.vlcplayer.set_media(self.Media)

        if sys.platform.startswith('linux'): # for Linux using the X Server
            self.vlcplayer.set_xwindow(handle)
        elif sys.platform == "win32": # for Windows
            self.vlcplayer.set_hwnd(handle)
        elif sys.platform == "darwin": # for MacOS
            self.vlcplayer.set_nsobject(handle)             

        # Try to launch the media, if this fails display an error message
        if self.vlcplayer.play() == -1:
            self.ErrorNotifyCallback("Unable to play.")    

                                
#----------------------------------------------------------------------#


class Ticker(wx.Control):
    def __init__(self, 
            parent, 
            id=-1, 
            text=wx.EmptyString,        #text in the ticker
            fgcolor = wx.RED,           #text/foreground color
            bgcolor = '#c0c0c0',         #background color
            start=True,                 #if True, the ticker starts immediately
            ppf=1,                      #pixels per frame
            fps=25,                     #frames per second
            direction="rtl",            #direction of ticking, rtl or ltr
            pos=wx.DefaultPosition, size=wx.DefaultSize, style=wx.NO_BORDER, 
            name="Ticker"
        ):
        wx.Control.__init__(self, parent, id=id, pos=pos, size=size, style=style, name=name)
        self.timer = wx.Timer(owner=self)
        self._extent = (-1, -1)  #cache value for the GetTextExtent call
        self._offset = 0
        self._fps = fps  #frames per second
        self._ppf = ppf  #pixels per frame
        self.SetDirection(direction)
        self.SetText(text)
        self.SetInitialSize(size)
        self.SetForegroundColour(fgcolor)
        self.SetBackgroundColour(bgcolor)
        self.Bind(wx.EVT_TIMER, self.OnTick)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)        
        if start:
            self.Start()


    def Stop(self):
        """Stop moving the text"""
        self.timer.Stop()

        
    def Start(self):
        """Starts the text moving"""
        if not self.timer.IsRunning():
            self.timer.Start(1000 / self._fps)

    
    def IsTicking(self):
        """Is the ticker ticking? ie, is the text moving?"""
        return self.timer.IsRunning()

        
    def SetFPS(self, fps):
        """Adjust the update speed of the ticker"""
        self._fps = fps
        self.Stop()
        self.Start()

        
    def GetFPS(self):
        """Update speed of the ticker"""
        return self._fps

        
    def SetPPF(self, ppf):
        """Set the number of pixels per frame the ticker moves - ie, how "jumpy" it is"""
        self._ppf = ppf

        
    def GetPPF(self):
        """Pixels per frame"""
        return self._ppf

        
    def SetFont(self, font):
        self._extent = (-1, -1)
        wx.Control.SetFont(self, font)

        
    def SetDirection(self, dir):
        """Sets the direction of the ticker: right to left(rtl) or left to right (ltr)"""
        if dir == "ltr" or dir == "rtl":
            if self._offset <> 0:
                #Change the offset so it's correct for the new direction
                self._offset = self._extent[0] + self.GetSize()[0] - self._offset
            self._dir = dir
        else:
            raise TypeError

            
    def GetDirection(self):
        return self._dir

        
    def SetText(self, text):
        """Set the ticker text."""
        self._text = text
        self._extent = (-1, -1)
        if not self._text:
            self.Refresh() #Refresh here to clear away the old text.
            
            
    def GetText(self):
        return self._text

        
    def UpdateExtent(self, dc):
        """Updates the cached text extent if needed"""
        if not self._text:
            self._extent = (-1, -1)
            return
        if self._extent == (-1, -1):
            self._extent = dc.GetTextExtent(self.GetText())
            
            
    def DrawText(self, dc):
        """Draws the ticker text at the current offset using the provided DC"""
        dc.SetTextForeground(self.GetForegroundColour())
        font = self.GetFont()
        font.SetPixelSize((0,self.GetSize().GetHeight()))
        dc.SetFont(font)
        self.UpdateExtent(dc)
        if self._dir == "ltr":
            offx = self._offset - self._extent[0]
        else:
            offx = self.GetSize()[0] - self._offset
        offy = (self.GetSize()[1] - self._extent[1]) / 2 #centered vertically
        dc.DrawText(self._text, offx, offy)
        
        
    def OnTick(self, evt):
        self._offset += self._ppf
        w1 = self.GetSize()[0]
        w2 = self._extent[0]
        if self._offset >= w1+w2:
            self._offset = 0
        self.Refresh()
        
        
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        brush = wx.Brush(self.GetBackgroundColour())
        dc.SetBackground(brush)
        dc.Clear()
        self.DrawText(dc)
        
        
    def OnErase(self, evt):
        """Noop because of double buffering"""
        pass
        

    def AcceptsFocus(self):
        """Non-interactive, so don't accept focus"""
        return False

        
    def DoGetBestSize(self):
        """Width we don't care about, height is either -1, or the character
        height of our text with a little extra padding
        """
        if self._extent == (-1, -1):
            if not self._text:
                h = self.GetCharHeight()
            else:
                h = self.GetTextExtent(self.GetText())[1]
        else:
            h = self._extent[1]
        return (100, h + 5)


    def ShouldInheritColours(self): 
        """Don't get colours from our parent..."""
        return False
        

    
       
