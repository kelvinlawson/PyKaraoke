#!/usr/bin/env python

# pykaraoke - Karaoke Player Frontend
#
#******************************************************************************
#****                                                                      ****
#**** Copyright (C) 2010  Kelvin Lawson (kelvinl@users.sourceforge.net)    ****
#**** Copyright (C) 2010  PyKaraoke Development Team                       ****
#****                                                                      ****
#**** This library is free software; you can redistribute it and/or        ****
#**** modify it under the terms of the GNU Lesser General Public           ****
#**** License as published by the Free Software Foundation; either         ****
#**** version 2.1 of the License, or (at your option) any later version.   ****
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


# OVERVIEW
#
# pykaraoke is a frontend for the pycdg and pympg karaoke players. It provides
# a search engine to find your songs, a file/folder browser to pick songs from
# disk, as well as a playlist.
#
# The default view is the search engine - you add your folders that contain
# karaoke songs, and hit the Scan button to build the database. The search
# engine can also look inside ZIP files for karaoke tracks.
#
# This frontend uses the WxPython library (www.wxpython.org) to provide the
# GUI. The CDG and MPG player functionality is handled by the external
# pycdg and pympg libraries (which use the pygame library (www.pygame.org)
# for audio/video).
#
# The frontend and player libraries run on any operating system that run pygame
# and WxPython (currently Linux, Windows and OSX).


# REQUIREMENTS
#
# pykaraoke requires the following to be installed on your system:
# . WxPython (www.wxpython.org)
# . Python (www.python.org)
# . Pygame (www.pygame.org)


# USAGE INSTRUCTIONS
#
# To start the player, run the following from the command line:
#       python pykaraoke.py
#
# The player starts in Search View. From here you can search for songs in
# your song database. You need to first set up the database, however, by
# clicking "Add Songs".
#
# To set up the database, add the folders that contain your karaoke songs.
# Select which type of files you are interested in adding to the search
# database (CDG, MPG etc). Click "Look Inside Zips" if you also want to
# search inside any ZIP files found in the folders for more karaoke songs.
#
# When you have finished adding folders, and setting your preferences,
# click "Scan Now" to start building the database. This can take some time
# but only needs to be done once. The search engine then searches your
# database, rather than searching the hard disk every time you search for
# a song.
#
# Once you have set up your database, clicking "Save" will save the database
# and settings for the next time you run the program. (The information is
# saved in a .pykaraoke folder in your home directory).
#
# If you get more karaoke files, don't forget to rescan the hard disk and
# build the database again. Otherwise the new files won't be visible in
# the search engine.
#
# With your database set up, you are ready to start searching for and
# playing your karaoke songs. From the main window, enter the name of the
# song you would like to find and click "Search". This will populate the
# Search Results panel below with the matching song files. From here
# double-clicking a song plays it directly. You can also add the song to
# your playlist by right-clicking on the song and using the popup menu.
#
# There is also a simple explorer-like interface that can be selected using
# a drop-down box on the main window ("Folder View"). Using this you can
# also play songs directly or add them to the playlist, by right-clicking
# on the song and using the popup menu.
#
# In the right-hand side of the window you will find your playlist. Songs
# can be added from the search results or folder browser, until you have
# built up your playlist. Once ready, click on the song you would like to
# start with. When the song is finished playing, the next song down the
# playlist will automatically start playing. You can also delete single
# songs, or clear the entire playlist by right-clicking on an item in
# the playlist.
#
# This is an early release of pykaraoke. Please let us know if there are
# any features you would like to see added, or you have any other
# suggestions or bug reports. Contact the project at
# kelvinl@users.sourceforge.net.


# IMPLEMENTATION DETAILS
#
# pykaraoke is a python module that implements a frontend for
# the external pycdg and pympg player modules. The frontend
# is implemented using WxPython.
#
# Everything is kicked off by the PyKaraokeMgr class, which
# instantiates the main window (PyKaraokeWindow class). It
# also handles calling the player modules and managing the
# playlist.
#
# All panels, windows and controls tend to be sub-classed from the
# base WxPython classes.
#
# The players are started by instantiating the class exported by
# their modules (e.g. pycdg.cdgPlayer()). They can then be
# controlled by calling their methods (Play(), Close() etc). The
# player modules do not take over the main loop, so the GUI is still
# usable while the songs are playing, allowing the user to
# continue adding to the playlist etc.

import sys

# Ensure that we have at least wx version 2.6, but also protect
# wxversion against py2exe (wxversion requires actual wx directories
# on-disk, so it doesn't work in the py2exe-compiled version used for
# Windows distribution).

if not hasattr(sys, 'frozen'):
    import wxversion
    wxversion.ensureMinimal('2.6')

import os, string, wx, time, copy, types
from wx.lib.pubsub import pub
from pykconstants import *
from pykenv import env
import pycdg, pympg, pykar, pykversion, pykdb
import codecs
import cPickle
from pykmanager import manager
import random
import performer_prompt as PerformerPrompt
import glob
import wx.html

# Constants
PLAY_COL_TITLE =      "Title"
PLAY_COL_ARTIST =     "Artist"
PLAY_COL_FILENAME =   "Filename"
PLAY_COL_PERFORMER =  "Singer"


class wxAppYielder(pykdb.AppYielder):
    def Yield(self):
        wx.GetApp().Yield()


# Popup busy window with cancel button
class wxBusyCancelDialog(wx.ProgressDialog, pykdb.BusyCancelDialog):
    def __init__(self, parent, title):
        pykdb.BusyCancelDialog.__init__(self)
        wx.ProgressDialog.__init__(
            self, title, title, style = wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_AUTO_HIDE)

    def SetProgress(self, label, progress):
        """ Called from time to time to update the progress display. """

        cont = self.Update(int(progress * 100), label)
        if isinstance(cont, types.TupleType):
            # Later versions of wxPython return a tuple from the above.
            cont, skip = cont

        if not cont:
            # Cancel clicked
            self.Clicked = True


# Popup settings window for adding song folders, requesting a
# new folder scan to fill the database etc.
class DatabaseSetupWindow (wx.Frame):
    def __init__(self,parent,id,title,KaraokeMgr):
        wx.Frame.__init__(self, parent, wx.ID_ANY, title, style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN, size = (500,600))
        self.KaraokeMgr = KaraokeMgr

        self.panel = wx.Panel(self)

        # Help text
        self._HelpText = wx.StaticText (self.panel, wx.ID_ANY,
                "Add folders to build a searchable database of your karaoke songs\n",
                style = wx.ALIGN_CENTER)

        # Add the folder list
        self.FolderList = wx.ListBox(self.panel, -1, style=wx.LB_SINGLE)
        for item in self.KaraokeMgr.SongDB.GetFolderList():
            self.FolderList.Append(item)

        # Add the buttons
        self.AddFolderButtonID = wx.NewId()
        self.DelFolderButtonID = wx.NewId()
        self.AddFolderButton = wx.Button(self.panel, self.AddFolderButtonID, "Add Folder")
        self.DelFolderButton = wx.Button(self.panel, self.DelFolderButtonID, "Delete Folder")
        self.FolderButtonsSizer = wx.BoxSizer(wx.VERTICAL)
        self.FolderButtonsSizer.Add(self.AddFolderButton, 0, wx.ALIGN_LEFT, 3)
        self.FolderButtonsSizer.Add(self.DelFolderButton, 0, wx.ALIGN_LEFT, 3)
        wx.EVT_BUTTON(self, self.AddFolderButtonID, self.OnAddFolderClicked)
        wx.EVT_BUTTON(self, self.DelFolderButtonID, self.OnDelFolderClicked)

        # Create a sizer for the folder list and folder buttons
        self.FolderSizer = wx.BoxSizer (wx.HORIZONTAL)
        self.FolderSizer.Add (self.FolderList, 1, wx.EXPAND, 3)
        self.FolderSizer.Add (self.FolderButtonsSizer, 0, wx.ALL, 3)

        # Create the settings controls
        self.FileExtensionID = wx.NewId()
        self.FiletypesText = wx.StaticText (self.panel, wx.ID_ANY, "Include File Types: ")
        self.FiletypesSizer = wx.BoxSizer (wx.HORIZONTAL)

        settings = self.KaraokeMgr.SongDB.Settings
        self.extCheckBoxes = {}
        for ext in settings.KarExtensions + settings.CdgExtensions + settings.MpgExtensions:
            cb = wx.CheckBox(self.panel, self.FileExtensionID, ext[1:])
            cb.SetValue(self.KaraokeMgr.SongDB.IsExtensionValid(ext))
            self.FiletypesSizer.Add(cb, 0, wx.ALL | wx.RIGHT, border = 2)
            self.extCheckBoxes[ext] = cb

        wx.EVT_CHECKBOX (self, self.FileExtensionID, self.OnFileExtChanged)

        # Create the ZIP file setting checkbox
        self.zipID = wx.NewId()
        self.zipText = wx.StaticText (self.panel, wx.ID_ANY, "Look Inside ZIPs: ")
        self.zipCheckBox = wx.CheckBox(self.panel, self.zipID, "Enabled")
        self.zipCheckBox.SetValue(settings.LookInsideZips)
        self.ZipSizer = wx.BoxSizer (wx.HORIZONTAL)
        self.ZipSizer.Add (self.zipCheckBox, 0, wx.ALL)
        wx.EVT_CHECKBOX (self, self.zipID, self.OnZipChanged)

        # Create the titles.txt file setting checkbox
        self.titlesID = wx.NewId()
        self.titlesText = wx.StaticText (self.panel, wx.ID_ANY, "Read titles.txt files: ")
        self.titlesCheckBox = wx.CheckBox(self.panel, self.titlesID, "Enabled")
        self.titlesCheckBox.SetValue(self.KaraokeMgr.SongDB.Settings.ReadTitlesTxt)
        self.TitlesSizer = wx.BoxSizer (wx.HORIZONTAL)
        self.TitlesSizer.Add (self.titlesCheckBox, 0, wx.ALL)
        wx.EVT_CHECKBOX (self, self.titlesID, self.OnTitlesChanged)

        # Create the filesystem and zip file coding boxes.
        fsCodingText = wx.StaticText(self.panel, -1, "System filename encoding:")
        self.fsCoding = wx.ComboBox(
            self.panel, -1, value = settings.FilesystemCoding,
            choices = settings.Encodings)
        zipCodingText = wx.StaticText(self.panel, -1, "Filename encoding within zips:")
        self.zipCoding = wx.ComboBox(
            self.panel, -1, value = settings.ZipfileCoding,
            choices = settings.Encodings)

        # Create the hash-check options
        self.hashCheckBox = wx.CheckBox(self.panel, -1, "Check for identical files (by comparing MD5 hash)")
        self.hashCheckBox.SetValue(self.KaraokeMgr.SongDB.Settings.CheckHashes)
        self.Bind(wx.EVT_CHECKBOX, self.OnHashChanged, self.hashCheckBox)
        self.deleteIdenticalCheckBox = wx.CheckBox(self.panel, -1, "Delete duplicate identical files from disk")
        self.deleteIdenticalCheckBox.SetValue(self.KaraokeMgr.SongDB.Settings.DeleteIdentical)
        self.deleteIdenticalCheckBox.Enable(self.KaraokeMgr.SongDB.Settings.CheckHashes)
        self.Bind(wx.EVT_CHECKBOX, self.OnDeleteIdenticalChanged, self.deleteIdenticalCheckBox)

        # Create the scan folders button
        self.ScanText = wx.StaticText (self.panel, wx.ID_ANY, "Rescan all folders: ")
        self.ScanFoldersButtonID = wx.NewId()
        self.ScanFoldersButton = wx.Button(self.panel, self.ScanFoldersButtonID, "Scan Now")
        wx.EVT_BUTTON(self, self.ScanFoldersButtonID, self.OnScanFoldersClicked)

        # Create the save settings button
        self.SaveText = wx.StaticText (self.panel, wx.ID_ANY, "Save settings and song database: ")
        self.SaveSettingsButtonID = wx.NewId()
        self.SaveSettingsButton = wx.Button(self.panel, self.SaveSettingsButtonID, "Save and Close")
        wx.EVT_BUTTON(self, self.SaveSettingsButtonID, self.OnSaveSettingsClicked)

        # Create the settings and buttons grid
        self.LowerSizer = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 3)
        self.LowerSizer.Add(self.FiletypesText, 0, wx.ALL, 3)
        self.LowerSizer.Add(self.FiletypesSizer, 1, wx.ALL, 3)
        self.LowerSizer.Add(self.zipText, 0, wx.ALL, 3)
        self.LowerSizer.Add(self.ZipSizer, 1, wx.ALL, 3)
        self.LowerSizer.Add(self.titlesText, 0, wx.ALL, 3)
        self.LowerSizer.Add(self.TitlesSizer, 1, wx.ALL, 3)
        self.LowerSizer.Add(fsCodingText, 0, wx.ALL, 3)
        self.LowerSizer.Add(self.fsCoding, 1, wx.ALL, 3)
        self.LowerSizer.Add(zipCodingText, 0, wx.ALL, 3)
        self.LowerSizer.Add(self.zipCoding, 1, wx.ALL, 3)
        self.LowerSizer.Add((0, 0))
        self.LowerSizer.Add(self.hashCheckBox, 1, wx.LEFT | wx.RIGHT | wx.TOP, 3)
        self.LowerSizer.Add((0, 0))
        self.LowerSizer.Add(self.deleteIdenticalCheckBox, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM, 3)
        self.LowerSizer.Add(self.ScanText, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.LowerSizer.Add(self.ScanFoldersButton, 1, wx.ALL, 3)
        self.LowerSizer.Add(self.SaveText, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        self.LowerSizer.Add(self.SaveSettingsButton, 1, wx.ALL, 3)

        # Create the main sizer
        self.MainSizer = wx.BoxSizer(wx.VERTICAL)
        self.MainSizer.Add(self._HelpText, 0, wx.EXPAND | wx.TOP, 3)
        self.MainSizer.Add(self.FolderSizer, 1, wx.EXPAND, 3)
        self.MainSizer.Add(self.LowerSizer, 0, wx.ALL, 3)

        # Add a close handler to ask the user if they want to rescan folders
        self.ScanNeeded = False
        self.SaveNeeded = False
        wx.EVT_CLOSE(self, self.ExitHandler)

        self.panel.SetSizer(self.MainSizer)

        psizer = wx.BoxSizer(wx.VERTICAL)
        psizer.Add(self.panel, flag = wx.EXPAND, proportion = 1)
        self.SetSizerAndFit(psizer)

        self.Centre()
        self.Show()

    # User wants to add a folder
    def OnAddFolderClicked(self, event):
        dirDlg = wx.DirDialog(self)
        retval = dirDlg.ShowModal()
        FolderPath = dirDlg.GetPath()
        dirDlg.Destroy()

        if retval == wx.ID_OK:
            # User made a valid selection
            folder_list = self.KaraokeMgr.SongDB.GetFolderList()
            # Add it to the list control and song DB if not already in
            if FolderPath not in folder_list:
                self.KaraokeMgr.SongDB.FolderAdd(FolderPath)
                self.FolderList.Append(FolderPath)
                self.ScanNeeded = True
                self.SaveNeeded = True

    # User wants to delete a folder, get the selection in the folder list
    def OnDelFolderClicked(self, event):
        index = self.FolderList.GetSelection()
        Folder = self.FolderList.GetString(index)
        self.KaraokeMgr.SongDB.FolderDel(Folder)
        self.FolderList.Delete(index)
        self.ScanNeeded = True
        self.SaveNeeded = True

    def __getCodings(self):
        # Extract the filesystem and zip file encodings.  These aren't
        # captured as they are changed, unlike the other parameters
        # here, because that's just a nuisance.
        settings = self.KaraokeMgr.SongDB.Settings

        FilesystemCoding = self.fsCoding.GetValue()
        if FilesystemCoding != settings.FilesystemCoding:
            settings.FilesystemCoding = FilesystemCoding
            self.ScanNeeded = True
            self.SaveNeeded = True

        ZipfileCoding = self.zipCoding.GetValue()
        if ZipfileCoding != settings.ZipfileCoding:
            settings.ZipfileCoding = ZipfileCoding
            self.ScanNeeded = True
            self.SaveNeeded = True

    # User wants to rescan all folders
    def OnScanFoldersClicked(self, event):
        self.__getCodings()
        # Create a temporary SongDatabase we can use to initiate the
        # scanning.  This way, if the user cancels out halfway
        # through, we can abandon it instead of being stuck with a
        # halfway-scanned database.
        songDb = pykdb.SongDB()
        songDb.Settings = self.KaraokeMgr.SongDB.Settings
        cancelled = songDb.BuildSearchDatabase(
            wxAppYielder(), wxBusyCancelDialog(self.KaraokeMgr.Frame, "Searching"))
        if not cancelled:
            # The user didn't cancel, so make the new database the
            # effective one.

            self.KaraokeMgr.SongDB = songDb
            pykdb.globalSongDB = songDb
            self.ScanNeeded = False
            self.SaveNeeded = True

    # User wants to save all settings
    def OnSaveSettingsClicked(self, event):
        self.__getCodings()
        self.Show(False)
        self.KaraokeMgr.SongDB.SaveSettings()
        self.KaraokeMgr.SongDB.SaveDatabase()
        self.SaveNeeded = False
        self.Destroy()

    # User changed a checkbox, just do them all again
    def OnFileExtChanged(self, event):
        ignored_ext_list = []
        for ext, cb in self.extCheckBoxes.items():
            if not cb.IsChecked():
                ignored_ext_list.append(ext)
        self.KaraokeMgr.SongDB.Settings.IgnoredExtensions = ignored_ext_list
        self.ScanNeeded = True
        self.SaveNeeded = True

    # User changed the zip checkbox, enable it
    def OnZipChanged(self, event):
        self.KaraokeMgr.SongDB.Settings.LookInsideZips = self.zipCheckBox.IsChecked()
        self.ScanNeeded = True
        self.SaveNeeded = True

    # User changed the titles.txt checkbox, enable it
    def OnTitlesChanged(self, event):
        self.KaraokeMgr.SongDB.Settings.ReadTitlesTxt = self.titlesCheckBox.IsChecked()
        self.ScanNeeded = True
        self.SaveNeeded = True

    # User changed the hash checkbox, enable it
    def OnHashChanged(self, event):
        self.KaraokeMgr.SongDB.Settings.CheckHashes = self.hashCheckBox.IsChecked()
        self.deleteIdenticalCheckBox.Enable(self.KaraokeMgr.SongDB.Settings.CheckHashes)
        self.ScanNeeded = True
        self.SaveNeeded = True

    # User changed the delete identical checkbox, enable it
    def OnDeleteIdenticalChanged(self, event):
        self.KaraokeMgr.SongDB.Settings.DeleteIdentical = self.deleteIdenticalCheckBox.IsChecked()
        self.ScanNeeded = True
        self.SaveNeeded = True

    # Popup asking if want to rescan the database after changing settings
    def ExitHandler(self, event):
        self.__getCodings()
        if self.ScanNeeded:
            changedString = "You have changed settings, would you like to rescan your folders now?"
            answer = wx.MessageBox(changedString, "Rescan folders now?", wx.YES_NO | wx.ICON_QUESTION)
            if answer == wx.YES:
                cancelled = self.KaraokeMgr.SongDB.BuildSearchDatabase(
                    wxAppYielder(), wxBusyCancelDialog(self.KaraokeMgr.Frame, "Searching"))
                if not cancelled:
                    self.SaveNeeded = True
        if self.SaveNeeded:
            saveString = "You have made changes, would you like to save your settings and database now?"
            answer = wx.MessageBox(saveString, "Save changes?", wx.YES_NO | wx.ICON_QUESTION)
            if answer == wx.YES:
                self.Show(False)
                self.KaraokeMgr.SongDB.SaveSettings()
                self.KaraokeMgr.SongDB.SaveDatabase()
        self.Destroy()


# Popup config window for setting full-screen mode etc
class ConfigWindow (wx.Frame):
    def __init__(self,parent,id,title,KaraokeMgr):
        wx.Frame.__init__(self, parent, wx.ID_ANY, title, style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN, size = (500,600))
        self.parent = parent
        self.panel = wx.Panel(self)
        self.KaraokeMgr = KaraokeMgr

        vsizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self.panel)

        self.__layoutDisplayPage()
        self.__layoutAudioPage()
        self.__layoutKarPage()
        self.__layoutCdgPage()
        self.__layoutMpgPage()

        vsizer.Add(self.notebook, flag = wx.EXPAND | wx.ALL,
                   proportion = 1, border = 5)

        # Make the OK and Cancel buttons.

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(self.panel, wx.ID_OK, 'OK')
        self.Bind(wx.EVT_BUTTON, self.clickedOK, b)
        hsizer.Add(b, flag = wx.EXPAND | wx.RIGHT | wx.LEFT, border = 10)

        b = wx.Button(self.panel, wx.ID_CANCEL, 'Cancel')
        self.Bind(wx.EVT_BUTTON, self.clickedCancel, b)
        hsizer.Add(b, flag = wx.EXPAND | wx.RIGHT, border = 10)
        vsizer.Add(hsizer, flag = wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM,
                   border = 10)

        self.panel.SetSizer(vsizer)

        psizer = wx.BoxSizer(wx.VERTICAL)
        psizer.Add(self.panel, flag = wx.EXPAND, proportion = 1)
        self.SetSizerAndFit(psizer)

        self.Centre()
        self.Show()

    def __layoutDisplayPage(self):
        """ Creates the page for the display config options """

        settings = self.KaraokeMgr.SongDB.Settings

        panel = wx.Panel(self.notebook)
        dispsizer = wx.BoxSizer(wx.VERTICAL)

        self.FSCheckBox = wx.CheckBox(panel, -1, "Enable Player Full-Screen Mode")
        self.FSCheckBox.SetValue(settings.FullScreen)
        dispsizer.Add(self.FSCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)
        self.NoFrameCheckBox = wx.CheckBox(panel, -1, "Enable Player With No Frame")
        self.NoFrameCheckBox.SetValue(settings.NoFrame)
        dispsizer.Add(self.NoFrameCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        self.DoubleBufCheckBox = wx.CheckBox(panel, -1, "Use double-buffered rendering (recommended)")
        self.DoubleBufCheckBox.SetValue(settings.DoubleBuf)
        dispsizer.Add(self.DoubleBufCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)
        self.HardwareSurfaceCheckBox = wx.CheckBox(panel, -1, "Request a hardware surface (recommended)")
        self.HardwareSurfaceCheckBox.SetValue(settings.HardwareSurface)
        dispsizer.Add(self.HardwareSurfaceCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        gsizer = wx.FlexGridSizer(0, 4, 2, 0)
        text = wx.StaticText(panel, -1, "Player Window Size:")
        gsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
        self.PlayerSizeX = wx.TextCtrl(panel, -1, value = str(settings.PlayerSize[0]))
        gsizer.Add(self.PlayerSizeX, flag = wx.EXPAND | wx.RIGHT, border = 5)
        self.PlayerSizeY = wx.TextCtrl(panel, -1, value = str(settings.PlayerSize[1]))
        gsizer.Add(self.PlayerSizeY, flag = wx.EXPAND | wx.RIGHT, border = 10)
        gsizer.Add((0, 0))

        # Window placement only seems to work reliably on Linux.  Only
        # offer it there.
        self.DefaultPosCheckBox = None
        if env == ENV_POSIX:
            text = wx.StaticText(panel, -1, "Player Placement:")
            gsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
            pos_x = pos_y = ''
            if settings.PlayerPosition:
                pos_x, pos_y = settings.PlayerPosition
            self.PlayerPositionX = wx.TextCtrl(panel, -1, value = str(pos_x))
            gsizer.Add(self.PlayerPositionX, flag = wx.EXPAND | wx.RIGHT, border = 5)
            self.PlayerPositionY = wx.TextCtrl(panel, -1, value = str(pos_y))
            gsizer.Add(self.PlayerPositionY, flag = wx.EXPAND | wx.RIGHT, border = 10)

            self.DefaultPosCheckBox = wx.CheckBox(panel, -1, "Default placement")
            self.Bind(wx.EVT_CHECKBOX, self.clickedDefaultPos, self.DefaultPosCheckBox)
            self.DefaultPosCheckBox.SetValue(settings.PlayerPosition is None)
            self.clickedDefaultPos(None)

            gsizer.Add(self.DefaultPosCheckBox, flag = wx.EXPAND)
        dispsizer.Add(gsizer, flag = wx.EXPAND | wx.ALL, border = 10)

        # Enables or disables the double-click playing from the play-list
        self.DoubleClickPlayCheckBox = wx.CheckBox(panel, -1, "Enable playing from play-list")
        self.DoubleClickPlayCheckBox.SetValue(settings.DoubleClickPlayList)
        dispsizer.Add(self.DoubleClickPlayCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        # Enables or disables playing from a search list functionality
        self.PlayFromSearchListCheckBox = wx.CheckBox(panel, -1, "Enable playing from search-list")
        self.PlayFromSearchListCheckBox.SetValue(settings.PlayFromSearchList)
        dispsizer.Add(self.PlayFromSearchListCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        # Enables or disables the performer functionality
        self.PerformerCheckBox = wx.CheckBox(panel, -1, "Enable performer enquiry")
        self.PerformerCheckBox.SetValue(settings.UsePerformerName)
        dispsizer.Add(self.PerformerCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        # Enables or disables the performer functionality
        self.ArtistTitleCheckBox = wx.CheckBox(panel, -1, "Display derived Artist/Title columns")
        self.ArtistTitleCheckBox.SetValue(settings.DisplayArtistTitleCols)
        dispsizer.Add(self.ArtistTitleCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        panel.SetSizer(dispsizer)
        self.notebook.AddPage(panel, "Display")


    def __layoutAudioPage(self):
        """ Creates the page for the audio config options """

        settings = self.KaraokeMgr.SongDB.Settings

        panel = wx.Panel(self.notebook)
        audsizer = wx.BoxSizer(wx.VERTICAL)

        self.StereoCheckBox = wx.CheckBox(panel, -1, "Stereo")
        self.StereoCheckBox.SetValue(settings.NumChannels > 1)
        audsizer.Add(self.StereoCheckBox, flag = wx.ALL, border = 10)

        self.UseMp3SettingsCheckBox = wx.CheckBox(panel, -1, "Use source sample rate if possible")
        self.UseMp3SettingsCheckBox.SetValue(settings.UseMp3Settings)
        audsizer.Add(self.UseMp3SettingsCheckBox, flag = wx.EXPAND | wx.LEFT, border = 10)

        gsizer = wx.FlexGridSizer(0, 2, 2, 0)
        text = wx.StaticText(panel, -1, "Sample rate:")
        gsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
        self.SampleRate = wx.ComboBox(
            panel, -1, value = str(settings.SampleRate),
            choices = map(str, settings.SampleRates))
        gsizer.Add(self.SampleRate, flag = wx.EXPAND)

        text = wx.StaticText(panel, -1, "Buffer size (ms):")
        gsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
        self.BufferSize = wx.TextCtrl(panel, -1,
                                      value = str(settings.BufferMs))
        gsizer.Add(self.BufferSize, flag = wx.EXPAND)

        text = wx.StaticText(panel, -1, "Sync delay (ms):")
        gsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
        self.SyncDelay = wx.TextCtrl(panel, -1,
                                     value = str(settings.SyncDelayMs))
        gsizer.Add(self.SyncDelay, flag = wx.EXPAND)

        audsizer.Add(gsizer, flag = wx.EXPAND | wx.ALL, border = 10)
        panel.SetSizer(audsizer)

        self.notebook.AddPage(panel, "Audio")


    def __layoutKarPage(self):
        """ Creates the page for the kar-file config options """

        settings = self.KaraokeMgr.SongDB.Settings

        panel = wx.Panel(self.notebook)
        karsizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(panel, -1, "Encoding:")
        hsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
        self.KarEncoding = wx.ComboBox(
            panel, -1, value = settings.KarEncoding,
            choices = settings.Encodings)
        hsizer.Add(self.KarEncoding, flag = wx.EXPAND, proportion = 1)
        karsizer.Add(hsizer, flag = wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(panel, -1, "Font:")
        hsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
        self.KarFont = copy.copy(settings.KarFont)
        self.KarFontLabel = wx.StaticText(panel, -1, self.KarFont.getDescription())
        # Make sure the label has enough space to include big font names.
        w, h = self.KarFontLabel.GetSize()
        self.KarFontLabel.SetMinSize((max(w, 100), h))
        hsizer.Add(self.KarFontLabel, flag = wx.ALIGN_CENTER_VERTICAL, proportion = 1)
        b = wx.Button(panel, -1, 'Select')
        self.Bind(wx.EVT_BUTTON, self.clickedFontSelect, b)
        hsizer.Add(b, flag = wx.EXPAND | wx.LEFT, border = 10)
        b = wx.Button(panel, -1, 'Browse')
        self.Bind(wx.EVT_BUTTON, self.clickedFontBrowse, b)
        hsizer.Add(b, flag = wx.EXPAND | wx.LEFT, border = 10)

        karsizer.Add(hsizer, flag = wx.EXPAND | wx.ALL, border = 10)

        gsizer = wx.FlexGridSizer(0, 2, 2, 0)
        gsizer.AddGrowableCol(1, 1)
        text = wx.StaticText(panel, -1, "MIDI Sample rate:")
        gsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
        self.MIDISampleRate = wx.ComboBox(
            panel, -1, value = str(settings.MIDISampleRate),
            choices = map(str, settings.SampleRates))
        gsizer.Add(self.MIDISampleRate, flag = wx.EXPAND)
        karsizer.Add(gsizer, flag = wx.EXPAND | wx.LEFT | wx.RIGHT, border = 10)

        self.Colours = {}
        self.ColourSamples = {}
        gsizer = wx.FlexGridSizer(0, 3, 2, 0)
        gsizer.AddGrowableCol(1, 1)
        for attribName in ['Ready', 'Sweep', 'Info', 'Title', 'Background']:
            text = wx.StaticText(panel, -1, "%s colour:" % (attribName))
            gsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
            colour = getattr(settings, 'Kar%sColour' % (attribName))
            sample = wx.Panel(panel)
            sample.SetSize((50, 10))
            sample.SetBackgroundColour(colour)
            gsizer.Add(sample, flag = wx.EXPAND, proportion = 1)
            b = wx.Button(panel, -1, 'Select')
            self.Bind(wx.EVT_BUTTON, lambda evt, attribName = attribName: self.clickedColourSelect(attribName), b)
            gsizer.Add(b, flag = wx.EXPAND | wx.LEFT, border = 10)

            self.Colours[attribName] = colour
            self.ColourSamples[attribName] = sample
        karsizer.Add(gsizer, flag = wx.EXPAND | wx.ALL, border = 10)

        panel.SetSizer(karsizer)
        self.notebook.AddPage(panel, 'Kar (MIDI)')


    def __layoutCdgPage(self):
        """ Creates the page for the cdg-file config options """

        settings = self.KaraokeMgr.SongDB.Settings

        panel = wx.Panel(self.notebook)
        cdgsizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(panel, -1, "Zoom:")
        hsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
        selection = settings.Zoom.index(settings.CdgZoom)
        choices = map(lambda z: '%s: %s' % (z, settings.ZoomDesc[z]), settings.Zoom)
        self.CdgZoom = wx.Choice(panel, -1, choices = choices)
        self.CdgZoom.SetSelection(selection)
        hsizer.Add(self.CdgZoom, flag = wx.EXPAND, proportion = 1)
        cdgsizer.Add(hsizer, flag = wx.EXPAND | wx.ALL, border = 10)

        # Enable/disable optimised C implementation of CDG decoder
        self.CdgUseCCheckBox = wx.CheckBox(panel, -1, "Use optimised (C-based) implementation")
        self.CdgUseCCheckBox.SetValue(settings.CdgUseC)
        # Check that the C implementation is available.
        if not pycdg.aux_c:
            self.CdgUseCCheckBox.SetValue(False)
            self.CdgUseCCheckBox.Enable(False)
        cdgsizer.Add(self.CdgUseCCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        # Scan song information from the file names.
        infoSizer = wx.BoxSizer(wx.VERTICAL)
        # Add checkbox for song-derivation enable/disable
        self.SongInfoCheckBoxID = wx.NewId()
        self.SongInfoCheckBox = wx.CheckBox(panel, self.SongInfoCheckBoxID, "Derive song information from file names?")
        wx.EVT_CHECKBOX(self, self.SongInfoCheckBoxID, self.setSongInfoCheckBox)
        infoSizer.Add(self.SongInfoCheckBox, flag = wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL, border = 7)
        # Add sub-options for song-derivation
        infoOptionsSizer = wx.BoxSizer(wx.VERTICAL)
        # Add combo-box for choosing filename scheme
        infoFormatSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.FileNameStylesText = wx.StaticText(panel, -1, "File naming scheme: ")
        infoFormatSizer.Add(self.FileNameStylesText, flag = wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT, border = 7)
        self.FileNameStyles = wx.ComboBox(panel, -1, choices = settings.FileNameCombinations, style = wx.CB_READONLY)
        infoFormatSizer.Add(self.FileNameStyles, flag = wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, proportion = 1, border = 7)
        infoOptionsSizer.Add(infoFormatSizer, flag = wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, proportion = 1, border = 7)
        # Add checkbox for exclusion of songs from database of files not matching the above scheme
        self.ExcludeNonMatchingCheckBox = wx.CheckBox(panel, -1, "Exclude from search results files not matching naming scheme")
        self.ExcludeNonMatchingCheckBox.SetValue(settings.ExcludeNonMatchingFilenames)
        infoOptionsSizer.Add(self.ExcludeNonMatchingCheckBox, border = 7)
        infoSizer.Add(infoOptionsSizer, flag = wx.ALIGN_RIGHT, border = 7)
        # Add the sizer with all info-related options to the main page sizer
        cdgsizer.Add(infoSizer, flag = wx.EXPAND | wx.ALL, border = 10)

        # Update the display to match whether derivation enabled (grey out options if not)
        if settings.CdgDeriveSongInformation:
            self.SongInfoCheckBox.SetValue(True)
            self.FileNameStyles.Enable(True)
            self.FileNameStylesText.Enable(True)
            self.FileNameStyles.SetSelection(settings.CdgFileNameType)
            self.ExcludeNonMatchingCheckBox.Enable (True)
        else:
            self.FileNameStyles.Enable(False)
            self.FileNameStylesText.Enable(False)
            self.ExcludeNonMatchingCheckBox.Enable (False)

        # Now add final sizer to panel
        panel.SetSizer(cdgsizer)
        self.notebook.AddPage(panel, 'CDG+MP3/OGG')


    def __layoutMpgPage(self):
        """ Creates the page for the mpg-file config options """

        settings = self.KaraokeMgr.SongDB.Settings

        panel = wx.Panel(self.notebook)
        mpgsizer = wx.BoxSizer(wx.VERTICAL)

        self.MpgNativeCheckBox = wx.CheckBox(
            panel, -1, "Use native viewer for mpg files")
        self.MpgNativeCheckBox.SetValue(settings.MpgNative)
        if not pympg.movie:
            self.MpgNativeCheckBox.SetValue(False)
            self.MpgNativeCheckBox.Enable(False)

        mpgsizer.Add(self.MpgNativeCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(panel, -1, "External viewer:")
        hsizer.Add(text, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 5)
        self.MpgExternal = wx.TextCtrl(panel, -1, value = settings.MpgExternal)
        hsizer.Add(self.MpgExternal, flag = wx.EXPAND, proportion = 1)

        b = wx.Button(panel, -1, 'Browse')
        self.Bind(wx.EVT_BUTTON, self.clickedExternalBrowse, b)
        hsizer.Add(b, flag = wx.EXPAND | wx.LEFT, border = 10)
        mpgsizer.Add(hsizer, flag = wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        self.MpgExternalThreadedCheckBox = wx.CheckBox(
            panel, -1, "Use a sub-thread to wait for external viewer")
        self.MpgExternalThreadedCheckBox.SetValue(settings.MpgExternalThreaded)
        mpgsizer.Add(self.MpgExternalThreadedCheckBox, flag = wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

        panel.SetSizer(mpgsizer)
        self.notebook.AddPage(panel, 'MPG/AVI')


    def clickedFontSelect(self, event):
        fontData = wx.FontData()
        if self.KarFont.size:
            font = self.findWxFont(self.KarFont)
            if font:
                fontData.SetInitialFont(font)

        dlg = wx.FontDialog(self, fontData)
        result = dlg.ShowModal()
        if result != wx.ID_OK:
            dlg.Destroy()
            return

        font = dlg.GetFontData().GetChosenFont()
        self.KarFont = pykdb.FontData(font.GetFaceName(),
                                      font.GetPointSize(),
                                      (font.GetWeight() == wx.FONTWEIGHT_BOLD),
                                      (font.GetStyle() == wx.FONTSTYLE_ITALIC))
        dlg.Destroy()

        self.KarFontLabel.SetLabel(self.KarFont.getDescription())

    def clickedFontBrowse(self, event):
        defaultDir = manager.FontPath
        defaultFile = ''
        if not self.KarFont.size:
            defaultDir, defaultFile = os.path.split(self.KarFont.name)
            if defaultDir == '':
                defaultDir = manager.FontPath

        dlg = wx.FileDialog(self, 'Font file',
                            defaultDir = defaultDir, defaultFile = defaultFile,
                            wildcard = 'True Type Fonts (*.ttf)|*.ttf|All files|*')
        result = dlg.ShowModal()
        if result != wx.ID_OK:
            dlg.Destroy()
            return

        filename = dlg.GetPath()
        dlg.Destroy()

        # Is it a file within the font directory?
        pathname, basename = os.path.split(filename)

        if os.path.normcase(os.path.realpath(pathname)) == os.path.normcase(os.path.realpath(manager.FontPath)):
            # Yes, it is a file within the font directory.  In this
            # case, just store the basename.
            filename = basename

        self.KarFont = pykdb.FontData(filename)

        self.KarFontLabel.SetLabel(self.KarFont.getDescription())

    def clickedColourSelect(self, attribName):
        colour = self.Colours[attribName]
        colourData = wx.ColourData()
        colourData.SetColour(colour)

        dlg = wx.ColourDialog(self, colourData)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return

        data = dlg.GetColourData()
        r, g, b = data.GetColour()
        dlg.Destroy()

        colour = (r, g, b)
        self.Colours[attribName] = colour
        sample = self.ColourSamples[attribName]
        sample.SetBackgroundColour(colour)
        sample.ClearBackground()

    def setSongInfoCheckBox(self, event):
        """ This enables and disables the ability to derive song information from file names"""
        if self.SongInfoCheckBox.IsChecked():
            self.FileNameStyles.Enable(True)
            self.FileNameStylesText.Enable(True)
            self.FileNameStyles.SetSelection(0)
            self.ExcludeNonMatchingCheckBox.Enable (True)
        else:
            self.FileNameStyles.Enable(False)
            self.FileNameStylesText.Enable(False)
            self.ExcludeNonMatchingCheckBox.Enable (False)

    def clickedCancel(self, event):
        self.Show(False)
        self.Destroy()

    def clickedDefaultPos(self, event):
        # Changing this checkbox changes the enabled state of the
        # window position fields.
        checked = self.DefaultPosCheckBox.IsChecked()
        self.PlayerPositionX.Enable(not checked)
        self.PlayerPositionY.Enable(not checked)

    def clickedExternalBrowse(self, event):
        # Pop up a file browser to find the appropriate external program.

        if env == ENV_WINDOWS:
            wildcard = 'Executable Programs (*.exe)|*.exe'
        else:
            wildcast = 'All files|*'
        dlg = wx.FileDialog(self, 'External Movie Player',
                            wildcard = wildcard)
        result = dlg.ShowModal()
        if result != wx.ID_OK:
            dlg.Destroy()
            return

        self.MpgExternal.SetValue(dlg.GetPath())
        dlg.Destroy()

    def clickedOK(self, event):
        self.Show(False)
        settings = self.KaraokeMgr.SongDB.Settings

        settings.FullScreen = self.FSCheckBox.IsChecked()
        settings.NoFrame = self.NoFrameCheckBox.IsChecked()
        settings.DoubleBuf = self.DoubleBufCheckBox.IsChecked()
        settings.HardwareSurface = self.HardwareSurfaceCheckBox.IsChecked()
        settings.PlayerPosition = None

        # Save the double-click play option
        if self.DoubleClickPlayCheckBox.IsChecked():
            settings.DoubleClickPlayList = True
        else:
            settings.DoubleClickPlayList = False

        # Save the performer option
        if self.PerformerCheckBox.IsChecked() != settings.UsePerformerName:
            if self.PerformerCheckBox.IsChecked():
                settings.UsePerformerName = True
            else:
                settings.UsePerformerName = False
            # Delete and reinitialise the display columns
            self.parent.PlaylistPanel.DeleteColumns()
            self.parent.PlaylistPanel.CreateColumns()
            self.parent.PlaylistPanel.ReloadData()
 
        # Save the Artist/Title display option
        if self.ArtistTitleCheckBox.IsChecked() != settings.DisplayArtistTitleCols:
            # Store the new setting
            if self.ArtistTitleCheckBox.IsChecked():
                settings.DisplayArtistTitleCols = True
            else:
                settings.DisplayArtistTitleCols = False
            # Delete and reinitialise the display columns
            self.parent.PlaylistPanel.DeleteColumns()
            self.parent.PlaylistPanel.CreateColumns()
            self.parent.PlaylistPanel.ReloadData()

        # Save the search list playing option
        if self.PlayFromSearchListCheckBox.IsChecked():
            settings.PlayFromSearchList = True
        else:
            settings.PlayFromSearchList = False

        if self.DefaultPosCheckBox:
            if not self.DefaultPosCheckBox.IsChecked():
                try:
                    pos_x = int(self.PlayerPositionX.GetValue())
                    pos_y = int(self.PlayerPositionY.GetValue())
                    settings.PlayerPosition = (pos_x, pos_y)
                except:
                    pass

        try:
            size_x = int(self.PlayerSizeX.GetValue())
            size_y = int(self.PlayerSizeY.GetValue())
            settings.PlayerSize = (size_x, size_y)
        except:
            pass

        settings.NumChannels = 1
        if self.StereoCheckBox.IsChecked():
            settings.NumChannels = 2

        settings.UseMp3Settings = self.UseMp3SettingsCheckBox.IsChecked()

        try:
            rate = int(self.SampleRate.GetValue())
            settings.SampleRate = rate
        except:
            pass

        try:
            rate = int(self.MIDISampleRate.GetValue())
            settings.MIDISampleRate = rate
        except:
            pass

        try:
            buffer = int(self.BufferSize.GetValue())
            settings.BufferMs = buffer
        except:
            pass

        try:
            sync = int(self.SyncDelay.GetValue())
            settings.SyncDelayMs = sync
        except:
            pass

        settings.KarEncoding = self.KarEncoding.GetValue()
        settings.KarFont = self.KarFont
        settings.KarReadyColour = self.Colours['Ready']
        settings.KarSweepColour = self.Colours['Sweep']
        settings.KarInfoColour = self.Colours['Info']
        settings.KarTitleColour = self.Colours['Title']
        settings.KarBackgroundColour = self.Colours['Background']

        selection = self.CdgZoom.GetSelection()
        settings.CdgZoom = settings.Zoom[selection]
        settings.CdgUseC = self.CdgUseCCheckBox.IsChecked()
        # Check to see if we will need to update the database
        if ((self.SongInfoCheckBox.IsChecked() == settings.CdgDeriveSongInformation) 
            and (settings.CdgFileNameType == self.FileNameStyles.GetCurrentSelection())
            and (settings.ExcludeNonMatchingFilenames == self.ExcludeNonMatchingCheckBox.IsChecked())):
            needDabaseRescan = False
        else:
            needDabaseRescan = True
            # Update cdg file scanning settings
            if self.SongInfoCheckBox.IsChecked() or (settings.CdgFileNameType != self.FileNameStyles.GetCurrentSelection()):
                settings.CdgDeriveSongInformation = True
                settings.CdgFileNameType = self.FileNameStyles.GetCurrentSelection()
            else:
                settings.CdgDeriveSongInformation = False
                settings.CdgFileNameType = -1
            settings.ExcludeNonMatchingFilenames = self.ExcludeNonMatchingCheckBox.IsChecked()

        settings.MpgNative = self.MpgNativeCheckBox.IsChecked()
        settings.MpgExternal = self.MpgExternal.GetValue()
        settings.MpgExternalThreaded = self.MpgExternalThreadedCheckBox.IsChecked()

        self.KaraokeMgr.SongDB.SaveSettings()
        # Update our song database if we need to.
        if needDabaseRescan:
            if self.reScanDatabase():
                # update our list panel
                self.parent.SearchPanel.UpdateListLayout()
            else: # User cancelled database scan return file name deriving to previous settings
                if self.SongInfoCheckBox.IsChecked():
                    settings.CdgDeriveSongInformation = False
                    settings.CdgFileNameType = -1
                else:
                    settings.CdgDeriveSongInformation = True
                    settings.CdgFileNameType = self.FileNameStyles.GetCurrentSelection()
                self.KaraokeMgr.SongDB.SaveSettings()

        self.Destroy()

    def reScanDatabase(self):
        """ This rescans the database when the CDG naming convention changes. """
        # Create a temporary SongDatabase we can use to initiate the
        # scanning.  This way, if the user cancels out halfway
        # through, we can abandon it instead of being stuck with a
        # halfway-scanned database.
        songDb = pykdb.SongDB()
        songDb.Settings = self.KaraokeMgr.SongDB.Settings
        cancelled = songDb.BuildSearchDatabase(
            wxAppYielder(), wxBusyCancelDialog(self.KaraokeMgr.Frame, "Re-Scanning Database"))
        if not cancelled:
            # The user didn't cancel, so make the new database the
            # effective one.

            self.KaraokeMgr.SongDB = songDb
            pykdb.globalSongDB = songDb
            self.KaraokeMgr.SongDB.SaveDatabase()
            return True
        else:
            return False

    def findWxFont(self, fontData):
        """ Returns a wx.Font selected by this data. """

        size = fontData.size or 10
        family = wx.FONTFAMILY_DEFAULT
        style = wx.FONTSTYLE_NORMAL
        if fontData.italic:
            style = wx.FONTSTYLE_ITALIC
        weight = wx.FONTWEIGHT_NORMAL
        if fontData.bold:
            weight = wx.FONTWEIGHT_BOLD
        name = fontData.name or ''

        font = wx.TheFontList.FindOrCreateFont(
            size, family, style, weight, False, name)

        return font


class Wx26AboutWindow(wx.Frame):

    """ Shows the friendly little "about" window. Wx2.6 version only. """

    def __init__(self, parent):
        wx.Frame.__init__(self, parent, -1, 'About PyKaraoke',
                          style = wx.DEFAULT_FRAME_STYLE|wx.FRAME_FLOAT_ON_PARENT)

        self.parent = parent
        self.__layoutWindow()

        pos = parent.GetPosition()
        parentSize = parent.GetSize()
        thisSize = self.GetSize()
        pos[0] += (parentSize[0] / 2) - (thisSize[0] / 2)
        pos[1] += (parentSize[1] / 2) - (thisSize[1] / 2)
        self.SetPosition(pos)

        self.Show()

    def __layoutWindow(self):
        self.panel = wx.Panel(self)
        vsizer = wx.BoxSizer(wx.VERTICAL)

        font = self.GetFont()
        topFont = wx.TheFontList.FindOrCreateFont(
            24,
            family = font.GetFamily(),
            style = wx.FONTSTYLE_ITALIC,
            weight = wx.FONTWEIGHT_BOLD)
        versionFont = wx.TheFontList.FindOrCreateFont(
            10,
            family = font.GetFamily(),
            style = font.GetStyle(),
            weight = wx.FONTWEIGHT_NORMAL)


        text = wx.StaticText(self.panel, -1, 'PyKaraoke')
        text.SetFont(topFont)
        vsizer.Add(text, flag = wx.ALIGN_CENTER)

        fullpath = self.parent.BigIconPath
        image = wx.Image(fullpath)
        image.ConvertAlphaToMask()
        bitmap = wx.BitmapFromImage(image)

        label = wx.StaticBitmap(self.panel, -1, bitmap)
        vsizer.Add(label, flag = wx.ALIGN_CENTER | wx.TOP, border = 10)

        text = wx.StaticText(self.panel, -1, 'PyKaraoke version %s' % (
            pykversion.PYKARAOKE_VERSION_STRING))
        text.SetFont(versionFont)
        vsizer.Add(text, flag = wx.ALIGN_CENTER | wx.TOP, border = 10)
        text = wx.StaticText(self.panel, -1, 'wxPython version %s' % (
            wx.VERSION_STRING))
        text.SetFont(versionFont)
        vsizer.Add(text, flag = wx.ALIGN_CENTER)

        pyver = sys.version
        if ' ' in pyver:
            pyver = pyver[:pyver.index(' ')]
        text = wx.StaticText(self.panel, -1, 'Python version %s\n' % (pyver))
        text.SetFont(versionFont)
        vsizer.Add(text, flag = wx.ALIGN_CENTER)

        # Add License information
        text = wx.StaticText(self.panel, -1, " PyKaraoke is free software; you can redistribute it and/or modify it under\n the terms of the GNU Lesser General Public License as published by the\n Free Software Foundation; either version 2.1 of the License, or (at your\n option) any later version.\n \n PyKaraoke is distributed in the hope that it will be useful, but WITHOUT\n ANY WARRANTY; without even the implied warranty of MERCHANTABILITY\n or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General\n Public License for more details.\n \n You should have received a copy of the GNU Lesser General Public\n License along with this library; if not, write to the\n Free Software Foundation, Inc.\n 59 Temple Place, Suite 330\n Boston, MA  02111-1307  USA")
        text.SetFont(versionFont)
        vsizer.Add(text, flag = wx.ALIGN_CENTER)

        b = wx.Button(self.panel, wx.ID_OK, 'OK')
        self.Bind(wx.EVT_BUTTON, self.clickedOK, b)
        vsizer.Add(b, flag = wx.ALIGN_CENTER | wx.TOP, border = 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(vsizer, flag = wx.EXPAND | wx.ALL, border = 10,
                   proportion = 1)

        self.panel.SetSizerAndFit(hsizer)
        self.Fit()

    def clickedOK(self, event):
        self.Show(False)
        self.Destroy()


class EditTitlesWindow(wx.Frame):

    """ The dialog that allows the user to edit artists and titles
    on-the-fly. """

    def __init__(self, parent, KaraokeMgr, songs):
        wx.Frame.__init__(self, parent, wx.ID_ANY, 'Edit artists / titles', style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN)
        self.parent = parent
        self.KaraokeMgr = KaraokeMgr
        self.songs = songs

        # Look for a common title and/or artist.
        title = self.songs[0].Title
        artist = self.songs[0].Artist
        for song in self.songs:
            if title != song.Title:
                title = None
            if artist != song.Artist:
                artist = None
        self.commonTitle = title
        self.commonArtist = artist

        self.__layoutWindow()

        pos = parent.GetPosition()
        parentSize = parent.GetSize()
        thisSize = self.GetSize()
        pos[0] += (parentSize[0] / 2) - (thisSize[0] / 2)
        pos[1] += (parentSize[1] / 2) - (thisSize[1] / 2)
        self.SetPosition(pos)

        self.Show()

    def __layoutWindow(self):
        self.panel = wx.Panel(self)
        vsizer = wx.BoxSizer(wx.VERTICAL)

        text = wx.StaticText(self.panel, -1,
                             'This will rewrite the titles.txt file(s) to reflect the changes to title\n'
                             'and/or artist that you indicate.')
        vsizer.Add(text, flag = wx.ALIGN_CENTER | wx.BOTTOM, border = 10)

        text = wx.StaticText(self.panel, -1,
                             '%s song(s) selected.' % (len(self.songs)))
        vsizer.Add(text, flag = wx.ALIGN_CENTER | wx.BOTTOM, border = 10)

        gsizer = wx.FlexGridSizer(0, 2, 2, 0)
        gsizer.AddGrowableCol(1, 1)
        label = wx.StaticText(self.panel, -1, 'Title:')
        gsizer.Add(label, flag = wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border = 5)

        field = wx.TextCtrl(self.panel, -1)
        if self.commonTitle is None:
            field.SetValue('(Varies)')
            field.Enable(False)
        else:
            field.SetValue(self.commonTitle)
        gsizer.Add(field, flag = wx.EXPAND)
        self.titleField = field

        label = wx.StaticText(self.panel, -1, 'Artist:')
        gsizer.Add(label, flag = wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border = 5)

        field = wx.TextCtrl(self.panel, -1)
        if self.commonArtist is None:
            field.SetValue('(Varies)')
            field.Enable(False)
        else:
            field.SetValue(self.commonArtist)
        gsizer.Add(field, flag = wx.EXPAND)
        self.artistField = field

        vsizer.Add(gsizer, flag = wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        b = wx.Button(self.panel, wx.ID_OK, 'OK')
        self.Bind(wx.EVT_BUTTON, self.clickedOK, b)
        hsizer.Add(b, flag = 0)
        if self.commonArtist is None and self.commonTitle is None:
            # Not possible to change anything, so gray out the modify button.
            b.Enable(False)

        b = wx.Button(self.panel, wx.ID_CANCEL, 'Cancel')
        self.Bind(wx.EVT_BUTTON, self.clickedCancel, b)
        hsizer.Add(b, flag = wx.LEFT, border = 10)
        vsizer.Add(hsizer, flag = wx.ALIGN_CENTER | wx.TOP | wx.LEFT | wx.RIGHT, border = 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(vsizer, flag = wx.EXPAND | wx.ALL, border = 10,
                   proportion = 1)

        self.panel.SetSizerAndFit(hsizer)
        self.Fit()

    def clickedOK(self, event):
        title = self.titleField.GetValue()
        artist = self.artistField.GetValue()
        songDb = self.KaraokeMgr.SongDB

        for song in self.songs:
            dirty = False
            if self.commonTitle is not None:
                if song.Title != title:
                    song.Title = title
                    songDb.GotTitles = True
                    dirty = True

            if self.commonArtist is not None:
                if song.Artist != artist:
                    song.Artist = artist
                    songDb.GotArtists = True
                    dirty = True

            if dirty:
                # This song has been changed.  Flag the appropriate
                # titles file for rewrite.
                song.needsRefresh = True
                songDb.chooseTitles(song)
                song.titles.dirty = True
                songDb.databaseDirty = True

        # Refresh the listbox onscreen.
        searchPanel = self.parent.SearchPanel
        listPanel = searchPanel.ListPanel
        for index in range(listPanel.GetItemCount()):
            si = listPanel.GetItemData(index)
            song = searchPanel.SongStructList[si]
            if not getattr(song, 'needsRefresh', False):
                continue

            # Song will no longer need a refresh.
            del song.needsRefresh

            # Update this song in the listbox.
            item = wx.ListItem()
            item.SetId(index)

            item.SetColumn(searchPanel.TitleCol)
            try:
                item.SetText(song.Title)
            except UnicodeError:
                item.SetText(song.Title.encode('UTF-8', 'replace'))
            item.SetData(si)
            searchPanel.ListPanel.SetItem(item)

            item.SetColumn(searchPanel.ArtistCol)
            try:
                item.SetText(song.Artist)
            except UnicodeError:
                item.SetText(song.Artist.encode('UTF-8', 'replace'))
            item.SetData(si)
            searchPanel.ListPanel.SetItem(item)

        self.Destroy()

    def clickedCancel(self, event):
        self.Show(False)
        self.Destroy()


# Generic function for popping up errors
def ErrorPopup (ErrorString):
    wx.MessageBox(ErrorString, "Error", wx.OK | wx.ICON_ERROR)


# This defines a custom "format" for our local drag-and-drop data
# type: a list of SongStruct objects.
songStructListFormat = wx.CustomDataFormat('SongStructList')


class SongStructDataObject(wx.PyDataObjectSimple):
    """This class is used to encapsulate a list of SongStruct objects,
    moving through the drag-and-drop system.  We use a custom
    DataObject class instead of using PyTextDataObject, so wxPython
    will know that we are specifically dragging SongStruct objects
    only, and won't crash if someone tries to drag an arbitrary text
    string into the playlist window. """

    def __init__(self, songs = None, extra_data = None):
        wx.PyDataObjectSimple.__init__(self)
        self.SetFormat(songStructListFormat)

        # Store a list of songs
        self.songs = songs

        # Store any extra data, which may be used to pass performer info
        # or any other additional info.
        self.extra_data = extra_data

        # Pickle both songs and extra_data
        self.data = cPickle.dumps((self.songs, self.extra_data))

    def GetDataSize(self):
        """Returns number of bytes required to store the data in the
        object.  This must be defined so the C++ implementation can
        reserve space before calling GetDataHere()."""
        return len(self.data)

    def GetDataHere(self):
        """Returns the data in the object, encoded as a string. """
        return self.data

    def SetData(self, data):
        """Accepts new data in the object, represented as a string. """

        # Note that this method doesn't appear to be called by the
        # current version of wxPython.  We work around this by also
        # passing the current drag-and-drop object in the variable
        # globalDragObject.

        # Cast the data object explicitly to a str type, in case the
        # drag-and-drop operation elevated it to a unicode string.
        self.data = str(data)
        self.songs, self.extra_data = cPickle.loads(self.data)

# We store the object currently being dragged here, to work around an
# apparent bug in wxPython that does not call
# DataObject.SetData() for custom data object formats.  Or, maybe
# I'm just misunderstanding some key interface, but documentation is
# sparse.  In any case, this works fine, since we are only interested
# in drag-and-drop within this process anyway.
globalDragObject = None


# Drag-and-drop target for lists. Code from WxPython Wiki
class ListDrop(wx.PyDropTarget):

    def __init__(self, setFn):
        wx.PyDropTarget.__init__(self)
        self.setFn = setFn

        # Create a data object to receive drops (and also,
        # incidentally, to specify the kind of data object we can
        # receive).
        self.data = SongStructDataObject()
        self.SetDataObject(self.data)

    # Called when OnDrop returns True.  We need to get the data and
    # do something with it.
    def OnData(self, x, y, drag_result):
        # copy the data from the drag source to our data object
        songs = None
        if self.GetData():
           songs = self.data.songs
           extra_data = self.data.extra_data

        if songs is None:
            # If GetData() failed, copy the data in by hand, working
            # around that wxPython bug.
            if globalDragObject:
                songs = globalDragObject.songs
                extra_data = globalDragObject.extra_data

        if songs:
            self.setFn(x, y, songs, extra_data, drag_result)

        # what is returned signals the source what to do
        # with the original data (move, copy, etc.)  In this
        # case we just return the suggested value given to us.
        return drag_result


class SearchResultsPanel (wx.Panel):
	# Search panel and list box

    def __init__(self, parent, mainWindow, id, KaraokeMgr, x, y):
        wx.Panel.__init__(self, parent, id)
        self.KaraokeMgr = KaraokeMgr

        self.parent = parent
        self.mainWindow = mainWindow

        # Search box text enter
        self.SearchText = wx.TextCtrl(self, -1, style=wx.TE_PROCESS_ENTER)
        self.SearchSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SearchSizer.Add(self.SearchText, 1, wx.EXPAND, 5)

        # Search box event handler
        self.SearchText.Bind(wx.EVT_KEY_UP, self.OnTextEntered)

        # Search results box
        self.ListPanel = wx.ListCtrl(self, -1, style = wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.SUNKEN_BORDER | wx.LC_SORT_ASCENDING)
        self.ListPanel.Show(True)

        # If we have derived the song information display the disc information else use the file name information.
        if self.KaraokeMgr.SongDB.Settings.CdgDeriveSongInformation:
            self.TitleCol = 0
            self.ArtistCol = 1
            self.DiscCol = 2
            self.FilenameCol = None
            self.ListPanel.InsertColumn (self.TitleCol, "Title", width=100)
            self.ListPanel.InsertColumn (self.ArtistCol, "Artist", width=100)
            self.ListPanel.InsertColumn (self.DiscCol, "Disc", width=100)
        else:
            self.FilenameCol = 0
            self.TitleCol = 1
            self.ArtistCol = 2
            self.DiscCol = None
            self.ListPanel.InsertColumn (self.FilenameCol, "Filename", width=100)
            self.ListPanel.InsertColumn (self.TitleCol, "Title", width=100)
            self.ListPanel.InsertColumn (self.ArtistCol, "Artist", width=100)

        pub.sendMessage('statusbar1.update', status = 'No Search Performed')

        # Expand left panel to fill window
        self.VertSizer = wx.BoxSizer(wx.VERTICAL)
        self.InterGap = 0
        self.VertSizer.Add(self.SearchSizer, 0, wx.EXPAND, self.InterGap)
        self.VertSizer.Add(self.ListPanel, 1, wx.EXPAND, self.InterGap)
        self.SetSizer(self.VertSizer)
        self.Show(True)

        wx.EVT_LIST_ITEM_ACTIVATED(self, wx.ID_ANY, self.OnFileSelected)
        
        # Add handlers for right-click in the results box
        self.RightClickedItemIndex = -1
        wx.EVT_LIST_ITEM_RIGHT_CLICK(self.ListPanel, wx.ID_ANY, self.OnRightClick)

        # Resize column width to the same as list width
        wx.EVT_SIZE(self.ListPanel, self.OnResize)

        # Create IDs for popup menu
        self.menuPlayId = wx.NewId()
        self.menuPlaylistEditTitlesId = wx.NewId()
        self.menuFileDetailsId = wx.NewId()

        # Set up drag and drop
        self.Bind(wx.EVT_LIST_BEGIN_DRAG, self._startDrag)

    def UpdateListLayout(self):
        """ This updates the list panel layout when the database settings has been changed."""
        self.ListPanel.ClearAll()
        if self.KaraokeMgr.SongDB.Settings.CdgDeriveSongInformation:
            self.FilenameCol = None
            self.TitleCol = 0
            self.ArtistCol = 1
            self.DiscCol = 2
            self.ListPanel.InsertColumn (self.TitleCol, "Title", width=100)
            self.ListPanel.InsertColumn (self.ArtistCol, "Artist", width=100)
            self.ListPanel.InsertColumn (self.DiscCol, "Disc", width=100)
        else:
            self.DiscCol = None
            self.FilenameCol = 0
            self.TitleCol = 1
            self.ArtistCol = 2
            self.ListPanel.InsertColumn (self.FilenameCol, "Filename", width=100)
            self.ListPanel.InsertColumn (self.TitleCol, "Title", width=100)
            self.ListPanel.InsertColumn (self.ArtistCol, "Artist", width=100)

    def OnFileSelected(self, event):
        """ Handles a file selected event (double-click). Will play directly (not add to playlist) if PlayFromSearchList is true, else it will add the file to the playlist."""
        if self.KaraokeMgr.SongDB.Settings.PlayFromSearchList:
            # The SongStruct is stored as data - get it and pass to karaoke mgr
            selected_index = self.ListPanel.GetItemData(event.GetIndex())
            song = self.SongStructList[selected_index]
            self.KaraokeMgr.PlayWithoutPlaylist(song)
        else:
            # Add song to the playlist
            for song in self.getSelectedSongs():
                self.KaraokeMgr.AddToPlaylist(song, self)

    def OnTextEntered(self, event):
		# Simple filter to prevent searches on control codes
		keycode = event.GetKeyCode()
		
		if keycode > 31:
			if keycode < 127:
				
				# See how manay characters have been entered
				l = self.SearchText.GetLineLength(0)

				if l > 4:
					# Set a minimum number of characters before searching, to limit
					# the number of songs found to a sensible number
					self.SearchText.SetEditable(False)
					self.SearchText.SetBackgroundColour((255,23,23))
					self.OnSearchClicked(event)
					self.SearchText.SetBackgroundColour((255,255,255))
					self.SearchText.SetEditable(True)
			
		
    def OnSearchClicked(self, event):
        """ Handle the search button clicked event """
        # Check to see if it will load the entire database
        if self.SearchText.GetValue() == "":
            return
        elif self.SearchText.GetValue() == "*":
            answer = wx.MessageBox("This will load the entire song database into the search results!\nThis may take a long time to complete depending on the number of songs listed in the database.", "Load Database", wx.YES_NO | wx.ICON_QUESTION)
            self.SearchText.SetValue("")
            # Abort if the user does not wish to load the entire database.
            if answer == wx.NO or answer == wx.CANCEL:
                return
        # Empty the previous results and perform a new search
        pub.sendMessage('statusbar1.update', status = 'Please Wait... Searching')
        songList = self.KaraokeMgr.SongDB.SearchDatabase(
            self.SearchText.GetValue(), wxAppYielder())
        if self.KaraokeMgr.SongDB.GetDatabaseSize() == 0:
            setupString = "You do not have any songs in your database. Would you like to add folders now?"
            answer = wx.MessageBox(setupString, "Setup database now?", wx.YES_NO | wx.ICON_QUESTION)
            if answer == wx.YES:
                # Open up the database setup dialog
                self.DBFrame = DatabaseSetupWindow(self.parent, -1, "Database Setup", self.KaraokeMgr)
                pub.sendMessage('statusbar1.update', status = 'No Search Performed')
            else:
                pub.sendMessage('statusbar1.update', status = 'No Songs In Song Database')
        elif len(songList) == 0:
            pub.sendMessage('statusbar1.update', status = 'No Matches Found')
        else:
            self.ListPanel.DeleteAllItems()
            self.MaxFilenameWidth = 0
            self.MaxTitleWidth = 0
            self.MaxArtistWidth = 0
            index = 0
            for song in songList:
                # Add the three columns to the table.
                if not self.KaraokeMgr.SongDB.Settings.CdgDeriveSongInformation: # Only add the Filename if we have not derived the song information
                    item = wx.ListItem()
                    item.SetId(index)
                    item.SetColumn(self.FilenameCol)
                    try:
                        item.SetText(song.DisplayFilename)
                    except UnicodeError:
                        item.SetText(song.DisplayFilename.encode('UTF-8', 'replace'))
                    item.SetData(index)
                    self.ListPanel.InsertItem(item)
                item = wx.ListItem()
                item.SetId(index)
                item.SetColumn(self.TitleCol)
                try:
                    item.SetText(song.Title)
                except UnicodeError:
                    item.SetText(song.Title.encode('UTF-8', 'replace'))
                item.SetData(index)
                if not self.KaraokeMgr.SongDB.Settings.CdgDeriveSongInformation: # Need to add the item if we have derived the song information.
                    self.ListPanel.SetItem(item)
                else:
                    self.ListPanel.InsertItem(item)

                item = wx.ListItem()
                item.SetId(index)
                item.SetColumn(self.ArtistCol)
                try:
                    item.SetText(song.Artist)
                except UnicodeError:
                    item.SetText(song.Artist.encode('UTF-8', 'replace'))
                item.SetData(index)
                self.ListPanel.SetItem(item)

                if self.KaraokeMgr.SongDB.Settings.CdgDeriveSongInformation: # Add the disc information if we have derived the song information
                    item = wx.ListItem()
                    item.SetId(index)
                    item.SetColumn(self.DiscCol)
                    try:
                        item.SetText(song.Disc)
                    except UnicodeError:
                        item.SetText(song.Disc.encode('UTF-8', 'replace'))
                    item.SetData(index)
                    self.ListPanel.SetItem(item)
                    
                # Nice background colour    
                if index % 2:
                    self.ListPanel.SetItemBackgroundColour(index, "white")
                else:
                    self.ListPanel.SetItemBackgroundColour(index, '#eee8aa')
                    
                index = index + 1

            # Keep a copy of all the SongStructs in a list, accessible via item index
            self.SongStructList = songList
            pub.sendMessage('statusbar1.update', status = '%d Songs Found' % index)            


    def getSelectedSongs(self):
        """ Returns a list of the selected songs. """
        songs = []
        index = self.ListPanel.GetNextItem(-1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
        while index != -1:
            si = self.ListPanel.GetItemData(index)
            song = self.SongStructList[si]
            songs.append(song)
            index = self.ListPanel.GetNextItem(index, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
        return songs

    # Handle right-click on a search results item (show the popup menu)
    def OnRightClick(self, event):
        self.RightClickedItemIndex = event.GetIndex()
        # Doesn't bring up a popup if no items are in the list
        if self.ListPanel.GetItemCount() > 0:
            menu = wx.Menu()
            menu.Append( self.menuPlaylistEditTitlesId, "Edit selected titles / artists" )
            wx.EVT_MENU( menu, self.menuPlaylistEditTitlesId, self.OnMenuSelection )
            menu.Append( self.menuFileDetailsId, "File Details" )
            wx.EVT_MENU( menu, self.menuFileDetailsId, self.OnMenuSelection )
            self.ListPanel.SetItemState(
                    self.RightClickedItemIndex,
                    wx.LIST_STATE_SELECTED|wx.LIST_STATE_FOCUSED,
                    wx.LIST_STATE_SELECTED|wx.LIST_STATE_FOCUSED)
            self.ListPanel.PopupMenu( menu, event.GetPoint() )

    # Handle popup menu selection events
    def OnMenuSelection( self, event ):
        song = self.SongStructList[self.ListPanel.GetItemData(self.RightClickedItemIndex)]

        if event.GetId() == self.menuPlaylistEditTitlesId:
            EditTitlesWindow(self.mainWindow, self.KaraokeMgr, self.getSelectedSongs())
        elif event.GetId() == self.menuFileDetailsId:
            detailsString = ''

            if song.Title:
                detailsString += 'Title: ' + song.Title + '\n'
            if song.Artist:
                detailsString += 'Artist: ' + song.Artist + '\n'
            if song.Title or song.Artist:
                detailsString += '\n'

            if song.ZipStoredName:
                detailsString += 'File: ' + song.ZipStoredName + '\nInside ZIP: ' + song.Filepath + '\n'
            else:
                detailsString += 'File: ' + song.Filepath + '\n'

            if song.titles:
                titles = song.titles
                if titles.ZipStoredName:
                    detailsString += '\nTitles file: ' + titles.ZipStoredName + '\nInside ZIP: ' + titles.Filepath + '\n'
                else:
                    detailsString += '\nTitles file: ' + titles.Filepath + '\n'

            # Display string, handle non-unicode filenames that are byte-strings
            try:
                wx.MessageBox(detailsString, song.DisplayFilename, wx.OK)
            except UnicodeDecodeError:
                wx.MessageBox(detailsString.decode('ascii', 'replace'), song.DisplayFilename, wx.OK)

    def OnResize(self, event):
        event.Skip()
        width = self.ListPanel.GetClientSize().width
        width = width/6
        self.ListPanel.SetColumnWidth(0, width*3)
        self.ListPanel.SetColumnWidth(1, width*2)
        self.ListPanel.SetColumnWidth(2, width)
        

    def GetSelections(self, state =  wx.LIST_STATE_SELECTED):
        indices = []
        found = 1
        lastFound = -1
        while found:
            index = self.ListPanel.GetNextItem(lastFound, wx.LIST_NEXT_ALL, state)
            if index == -1:
                break
            else:
                lastFound = index
                indices.append( index )
        return indices

    # Get the song from the requested index in the song struct list
    def GetSongStruct (self, index):
        return self.SongStructList[index]

    # Put together a data object for drag-and-drop _from_ this list
    # Code from WxPython Wiki
    def _startDrag(self, event):
        # Wrap the songs in a DataObject. We don't pass any
        # extra_data, only the song struct is required.
        songs = self.getSelectedSongs()
        data = SongStructDataObject(songs, None)

        # Also store this data object in the globalDragObject pointer,
        # to work around a wxPython bug.
        global globalDragObject
        globalDragObject = data

        # Create drop source and begin drag-and-drop.
        dropSource = wx.DropSource(self.ListPanel)
        dropSource.SetData(data)

        # The docs say the parameter here should be one of
        # wx.DragCopy/DragMove/etc., but in practice it appears that
        # only wx.DragNone works on Windows.
        if env == ENV_WINDOWS:
            res = dropSource.DoDragDrop(wx.DragNone)
        else:
            res = dropSource.DoDragDrop(wx.DragCopy)

        # Let's not remove items from the search results list, even if
        # the drag-and-drop says the user thought he was "moving" it.

        return True


# Class to manage the playlist panel and list box
class Playlist (wx.Panel):
    def __init__(self, parent, id, KaraokeMgr, x, y):
        wx.Panel.__init__(self, parent, id)
        self.KaraokeMgr = KaraokeMgr
        self.parent = parent

        # Create the playlist control
        self.PlaylistId = wx.NewId()
        self.Playlist = wx.ListCtrl(self, self.PlaylistId, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.SUNKEN_BORDER)

        # Create the columns based on the view configuration
        self.CreateColumns()

        # Create a sizer for the tree view and status bar
        self.InterGap = 0
        self.VertSizer = wx.BoxSizer(wx.VERTICAL)
        self.VertSizer.Add(self.Playlist, 1, wx.EXPAND, self.InterGap)
        self.SetSizer(self.VertSizer)
        self.Show(True)

        # Add handlers for the listbox
        wx.EVT_LIST_ITEM_ACTIVATED(self, wx.ID_ANY, self.OnFileSelected)

        # Resize column width to the same as list width (or max title width, which larger)
        wx.EVT_SIZE(self.Playlist, self.OnResize)

        # Create IDs for popup menu
        self.menuPlayId = wx.NewId()
        self.menuDeleteId = wx.NewId()
        self.menuClearListId = wx.NewId()

        # Store a local list of song_structs associated by index to playlist items.
        # This is a list of tuples of song_struct and performer name.
        # (Cannot store stuff like this associated with an item in a listctrl)
        self.PlaylistSongStructList = []

        # Set up drag and drop
        self.Bind(wx.EVT_LIST_BEGIN_DRAG, self._startDrag)
        dt = ListDrop(self._insert)
        self.Playlist.SetDropTarget(dt)

    # Create all playlist columns (at startup and if changing display mode)
    def CreateColumns (self):

        # Display the Artist/Titles column if configured to do so
        col_cnt = 0
        if self.KaraokeMgr.SongDB.Settings.DisplayArtistTitleCols:
            self.TitleCol = col_cnt
            col_cnt = col_cnt + 1
            self.ArtistCol = col_cnt
            col_cnt = col_cnt + 1
            self.Playlist.InsertColumn(self.TitleCol, PLAY_COL_TITLE, width=100)
            self.Playlist.InsertColumn(self.ArtistCol, PLAY_COL_ARTIST, width=100)
        # Otherwise display the filename column instead
        else:
            self.FilenameCol = col_cnt
            col_cnt = col_cnt + 1
            self.Playlist.InsertColumn(self.FilenameCol, PLAY_COL_FILENAME, width=200)

        # Display the performer's name column if configured to do so
        if self.KaraokeMgr.SongDB.Settings.UsePerformerName:
            self.PerformerCol = col_cnt
            col_cnt = col_cnt + 1
            self.Playlist.InsertColumn(self.PerformerCol, PLAY_COL_PERFORMER, width=100)
        
        # Finished adding columns, show the panel
        self.NumColumns = col_cnt
        self.Playlist.Show(True)

    # Delete all playlist columns, used when changing display mode
    def DeleteColumns (self):

        # Hide the panel while we delete
        self.Playlist.Show(False)

        # Delete all columns
        self.Playlist.DeleteAllColumns()

        # Clear the number of columns
        self.NumColumns = 0

    # Delete and reload all playlist entries, used when changing display mode
    def ReloadData (self):

        # Take a copy of all songs in the list
        song_list = list(self.PlaylistSongStructList)

        # Delete all items
        for index in range (len(song_list)):
             self.DelItem (0)

        # Clear all data
        self.clear()

        # Using our backup copy, reload all the data
        for song in song_list:
            self.AddItem (song[0], song[1])

    # Handle item selected (double-click). Starts the selected track.
    def OnFileSelected(self, event):
        if self.KaraokeMgr.SongDB.Settings.DoubleClickPlayList:
            selected_index = event.GetIndex()
            self.KaraokeMgr.PlaylistStart(selected_index, self)


    # Handle popup menu selection events.
    def OnMenuSelection( self, event ):
        if event.GetId() == self.menuPlayId:
            self.KaraokeMgr.PlaylistStart(self.RightClickedItemIndex)
        elif event.GetId() == self.menuDeleteId:
            for index in self.GetSelections():
                self.DelItem(index)
        elif self.KaraokeMgr.SongDB.Settings.ClearFromPlayList and (event.GetId() == self.menuClearListId):
            self.clear()


    def play(self):
        """ Start the playlist playing. """
        if self.Playlist.GetItemCount() > 0:
            sel = self.Playlist.GetFirstSelected()
            if sel == -1:
				sel = 0
            self.KaraokeMgr.PlaylistStart(sel, self)


    def clear(self):
        sel = self.Playlist.GetFirstSelected()

        if sel != -1:
            self.Playlist.DeleteItem(sel)
            self.PlaylistSongStructList.pop(sel)
		    

    def OnResize(self, event):
        event.Skip()
        width = self.Playlist.GetClientSize().width
        width = width/6
        self.Playlist.SetColumnWidth(0, width*3)
        self.Playlist.SetColumnWidth(1, width*2)
        self.Playlist.SetColumnWidth(2, width)
        
        		
    # Add item to specific index in playlist
    def AddItemAtIndex ( self, index, song, performer="" ):

        # Insert an empty item
        item = wx.ListItem()
        item.SetId(index)
        self.Playlist.InsertItem(item)

        # If there is no title, set it to the filename
        if len(song.Title) == 0:
            song.Title = song.DisplayFilename

        if self.KaraokeMgr.SongDB.Settings.DisplayArtistTitleCols:
            # Add the title column
            item = wx.ListItem()
            item.SetId(index)
            item.SetColumn(self.TitleCol)
            try:
                item.SetText(song.Title)
            except UnicodeError:
                item.SetText(song.Title.encode('UTF-8', 'replace'))
            item.SetData(index)
            self.Playlist.SetItem(item)

            # Add the artist column
            item = wx.ListItem()
            item.SetId(index)
            item.SetColumn(self.ArtistCol)
            try:
                item.SetText(song.Artist)
            except UnicodeError:
                item.SetText(song.Artist.encode('UTF-8', 'replace'))
            item.SetData(index)
            self.Playlist.SetItem(item)
        else:
            # Add the filename column information
            item = wx.ListItem()
            item.SetId(index)
            item.SetColumn(self.FilenameCol)
            try:
                item.SetText(song.DisplayFilename)
            except UnicodeError:
                item.SetText(song.DisplayFilename.encode('UTF-8', 'replace'))
            item.SetData(index)
            self.Playlist.SetItem(item)

        # Add performer name if enabled
        if self.KaraokeMgr.SongDB.Settings.UsePerformerName:
            # Add the performer column information
            item = wx.ListItem()
            item.SetId(index)
            item.SetColumn(self.PerformerCol)
            try:
                item.SetText(performer)
            except UnicodeError:
                item.SetText(performer.encode('UTF-8', 'replace'))
            item.SetData(index)
            self.Playlist.SetItem(item)

        # Create a tuple containing the song_struct ([0]) and performer name ([1])
        song_tuple = (song, performer)
        self.PlaylistSongStructList.insert(index, song_tuple)

        # Nice background colour    
        if index % 2:
            self.Playlist.SetItemBackgroundColour(index, "white")
        else:
            self.Playlist.SetItemBackgroundColour(index, '#eee8aa')    


    # Add item to end of playlist
    def AddItem( self, song_struct, performer ):
        self.AddItemAtIndex (self.Playlist.GetItemCount(), song_struct, performer)


    # Delete item from playlist
    def DelItem( self, item_index ):

        # Delete the item from the listctrl and our local song struct list
        self.Playlist.DeleteItem(item_index)
        self.PlaylistSongStructList.pop(item_index)
        

    # Get number of items in playlist
    def GetItemCount( self ):
        return self.Playlist.GetItemCount()

    # Get the song_struct for an item index
    def GetSongStruct ( self, item_index ):
        return self.PlaylistSongStructList[item_index][0]

    # Set an item as selected
    def SetItemSelected( self, item_index ):
        self.Playlist.SetItemState(
                item_index,
                wx.LIST_STATE_SELECTED|wx.LIST_STATE_FOCUSED,
                wx.LIST_STATE_SELECTED|wx.LIST_STATE_FOCUSED)

    # Return list of selected items.
    def GetSelections(self, state =  wx.LIST_STATE_SELECTED):
        indices = []
        found = 1
        lastFound = -1
        while found:
            index = self.Playlist.GetNextItem(lastFound, wx.LIST_NEXT_ALL, state)
            if index == -1:
                break
            else:
                lastFound = index
                indices.append( index )
        return indices

    # Put together a data object for drag-and-drop _from_ this list
    # Code from WxPython Wiki
    def _startDrag(self, e):
        # Wrap the song_struct in a DataObject. We make use of the
        # extra_data area to also send the performer name. This is
        # only used for drag-drop within the playlist window where
        # we might have performer info.
        song_struct = self.PlaylistSongStructList[e.GetIndex()][0]
        songs = [song_struct]
        performer = self.PlaylistSongStructList[e.GetIndex()][1]
        data = SongStructDataObject(songs, performer)

        # Also store this data object in the globalDragObject pointer,
        # to work around a wxPython bug.
        global globalDragObject
        globalDragObject = data

        # Create drop source and begin drag-and-drop.
        dropSource = wx.DropSource(self.Playlist)
        dropSource.SetData(data)

        # The docs say the parameter here should be one of
        # wx.DragCopy/DragMove/etc., but in practice it appears that
        # only wx.DragNone works on Windows.
        if env == ENV_WINDOWS:
            res = dropSource.DoDragDrop(wx.DragNone)
        else:
            res = dropSource.DoDragDrop(wx.DragMove)

        # If move, we want to remove the item from this list.
        if res == wx.DragMove:
            # It's possible we are dragging/dropping from this
            # list to this list. In which case, the index we are
            # removing may have changed...

            # Find correct position.
            idx = e.GetIndex()
            # Compare the filename if in filename-only mode
            if (not self.KaraokeMgr.SongDB.Settings.DisplayArtistTitleCols):
                if (self.Playlist.GetItem(idx, self.FilenameCol).GetText() == song_struct.DisplayFilename):
                    self.DelItem(idx)
                elif (self.Playlist.GetItem(idx + 1, self.FilenameCol).GetText() == song_struct.DisplayFilename):
                    self.DelItem(idx + 1)
            # Or compare the title if in title/artist mode
            else:
                if (self.Playlist.GetItem(idx, self.TitleCol).GetText() == song_struct.Title):
                    self.DelItem(idx)
                elif (self.Playlist.GetItem(idx + 1, self.TitleCol).GetText() == song_struct.Title):
                    self.DelItem(idx + 1)

    def _insert(self, x, y, songs, extra_data, drag_result):
        """ Insert songs from drag_index in search results, at given x,y coordinates, used with drag-and-drop. Code from WxPython Wiki """

        # Find insertion point.
        index, flags = self.Playlist.HitTest((x, y))
        if index == wx.NOT_FOUND:
            # Note: should only insert if flags & wx.LIST_HITTEST_NOWHERE
            # but for some reason always get flags = 0 even if out of area...
            index = self.Playlist.GetItemCount()
        else:
            # Get bounding rectangle for the item the user is dropping over.
            rect = self.Playlist.GetItemRect(index)

            # If the user is dropping into the lower half of the rect, we want to insert
            # _after_ this item.
            if y > (rect.y + rect.height/2):
                index = index + 1

        # Add it to the list
        for song in songs:
            # Add the performer information if enabled
            performer = ""
            if self.KaraokeMgr.SongDB.Settings.UsePerformerName:
                # If a new song is being added to the playlist pop up a prompt
                if (drag_result != wx.DragMove):
                    dlg = PerformerPrompt.PerformerPrompt(self)
                    if dlg.ShowModal() == wx.ID_OK:
                        performer = dlg.getPerformer()
                    else:
                        return
                # If this is a drag-drop within the playlist (i.e. rearranging), the
                # performer name will be passed to us.
                elif extra_data:
                    performer = extra_data

            self.AddItemAtIndex(index, song, performer)
            index += 1


class TabOne(wx.Panel):
    def __init__(self, parent, KaraokeMgr):
		
        wx.Panel.__init__(self, parent)
        
        self.KaraokeMgr = KaraokeMgr
       
        # Create the splitter window for the panels
        self.splitter = wx.SplitterWindow(self)
        self.panelOne = wx.Panel(self.splitter)
        self.panelTwo = wx.Panel(self.splitter)

        # Panel One
        self.panelOneSizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create panel one buttons
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(self.panelOne, -1, 'Search Results')
        hsizer.Add(text, 0, wx.ALL, 5)
        hsizer.AddStretchSpacer(5)
        bmp = wx.Bitmap("Play.png", wx.BITMAP_TYPE_PNG)
        self.playButton = wx.BitmapButton(self.panelOne, id = wx.ID_ANY, bitmap = bmp, size = (40, 30)) 
        self.Bind(wx.EVT_BUTTON, self.OnPlayClicked, self.playButton)
        hsizer.Add(self.playButton, flag = wx.EXPAND)
        
        bmp = wx.Bitmap("Arrow.png", wx.BITMAP_TYPE_PNG)
        b = wx.BitmapButton(self.panelOne, id = wx.ID_ANY, bitmap = bmp, size = (60, 30)) 
        self.Bind(wx.EVT_BUTTON, self.AddToPlayList, b)
        hsizer.Add(b, flag = wx.EXPAND)

        # Add the row to the main vertical sizer
        self.panelOneSizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Create the search and playlist panels
        self.SearchPanel = SearchResultsPanel(self.panelOne, self, -1, KaraokeMgr, 0, 0)
        self.panelOneSizer.Add(self.SearchPanel, 1, wx.ALL | wx.EXPAND, 5)
        self.panelOne.SetSizer(self.panelOneSizer)

        # Panel Two
        self.panelTwoSizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create panel two buttons
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(self.panelTwo, -1, 'Play list')
        hsizer.Add(text, 0, wx.ALL, 5)
        hsizer.AddStretchSpacer(5)
        bmp = wx.Bitmap("Play.png", wx.BITMAP_TYPE_PNG)
        self.playlistButton = wx.BitmapButton(self.panelTwo, id = wx.ID_ANY, bitmap = bmp, size = (40, 30))         
        self.Bind(wx.EVT_BUTTON, self.OnStartPlaylistClicked, self.playlistButton)
        hsizer.Add(self.playlistButton, flag = wx.EXPAND)

        bmp = wx.Bitmap("Delete.png", wx.BITMAP_TYPE_PNG)
        b = wx.BitmapButton(self.panelTwo, id = wx.ID_ANY, bitmap = bmp, size = (60, 30)) 
        self.Bind(wx.EVT_BUTTON, self.OnClearPlaylistClicked, b)
        hsizer.Add(b, flag = wx.EXPAND)

        # Add the row to the main vertical sizer
        self.panelTwoSizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
                
        # Add progress bar
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.gauge = wx.Gauge(self.panelTwo, -1, 50, (10, 100), (1000, 16))
        hsizer.Add(self.gauge, flag = wx.EXPAND)
        self.panelTwoSizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
                
        # Create play list panel
        self.PlaylistPanel = Playlist(self.panelTwo, -1, KaraokeMgr, 0, 0)
        self.panelTwoSizer.Add(self.PlaylistPanel, 1, wx.ALL | wx.EXPAND, 5)
        self.panelTwo.SetSizer(self.panelTwoSizer)
        
        # Set the initial screen sizes at start up
        self.splitter.SplitVertically(self.panelOne, self.panelTwo)
        
        # Make the two panels equal size by default
        self.splitter.SetSashGravity(0.5)
        
        # Make the two panels a fixed size
        self.splitter.SetSashInvisible(True)
        
        # Put the top level buttons and main panels in a sizer
        self.MainSizer = wx.BoxSizer(wx.VERTICAL)
        self.MainSizer.Add(self.splitter, 1, wx.ALL | wx.EXPAND)
        self.SetAutoLayout(True)
        self.SetSizer(self.MainSizer)

        # Message subscriptions
        pub.subscribe(self.OnGaugeStart, 'gauge.start')
        pub.subscribe(self.OnGaugeUpdate, 'gauge.update')
        
        
    def OnGaugeStart(self, status):
		self.gauge.SetRange(status)
        
        
    def OnGaugeUpdate(self, status):
            self.gauge.SetValue(status)


    def OnPlayClicked(self, event):
		# Play button in panel 1 pressed to play a song
        songs = self.SearchPanel.getSelectedSongs()
        
        if not songs:
            wx.MessageBox("No songs selected.")
            return
            
        self.KaraokeMgr.PlayWithoutPlaylist(songs[0])


    def AddToPlayList(self, event):
		# Add a song to panel 2 the play list panel
        songs = self.SearchPanel.getSelectedSongs()

        if not songs:
            wx.MessageBox("No songs selected.")
            return

        for song in songs:
            self.KaraokeMgr.AddToPlaylist(song, self, 1)

            
    def OnStartPlaylistClicked(self, event):
		# Panel 2 play button pressed
        self.PlaylistPanel.play()


    def OnClearPlaylistClicked(self, event):
		# Delete selected item
        self.PlaylistPanel.clear()


class TabTwo(wx.Panel):
    def __init__(self, parent, KaraokeMgr):
		
        wx.Panel.__init__(self, parent)
        
        self.KaraokeMgr = KaraokeMgr
        
        # Used to store found file
        self.dir_path = ''
        
        # Create the splitter window for the panels
        self.splitter = wx.SplitterWindow(self)
        self.panelOne = wx.Panel(self.splitter)
        self.panelTwo = wx.Panel(self.splitter)

        # Panel One
        self.panelOneSizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create panel one buttons
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(self.panelOne, -1, 'Search Results')
        hsizer.Add(text, 0, wx.ALL, 5)
        hsizer.AddStretchSpacer(5)
        bmp = wx.Bitmap("Music.png", wx.BITMAP_TYPE_PNG)
        btn = wx.BitmapButton(self.panelOne, id = wx.ID_ANY, bitmap = bmp, size = (40, 30)) 
        self.Bind(wx.EVT_BUTTON, self.OnOpenDirectory, btn)
        hsizer.Add(btn, flag = wx.EXPAND)
        
        bmp = wx.Bitmap("Arrow.png", wx.BITMAP_TYPE_PNG)
        b = wx.BitmapButton(self.panelOne, id = wx.ID_ANY, bitmap = bmp, size = (60, 30)) 
        self.Bind(wx.EVT_BUTTON, self.AddToPlayList, b)
        hsizer.Add(b, flag = wx.EXPAND)

        # Add the row to the main vertical sizer
        self.panelOneSizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Create the search and playlist panels
        self.list_ctrl = wx.ListCtrl(self.panelOne, -1, style = wx.LC_REPORT | wx.SUNKEN_BORDER | wx.LC_SORT_ASCENDING)
        self.list_ctrl.InsertColumn(0, 'Filename (cdg, kar, mpg)')
        self.panelOneSizer.Add(self.list_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        self.panelOne.SetSizer(self.panelOneSizer)

        # Resize column width to the same as list width (or max title width, which larger)
        wx.EVT_SIZE(self.list_ctrl, self.OnResize)

        # Panel Two
        self.panelTwoSizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create panel two buttons
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(self.panelTwo, -1, 'Play list')
        hsizer.Add(text, 0, wx.ALL, 5)
        hsizer.AddStretchSpacer(5)
        bmp = wx.Bitmap("Play.png", wx.BITMAP_TYPE_PNG)
        self.playlistButton = wx.BitmapButton(self.panelTwo, id = wx.ID_ANY, bitmap = bmp, size = (40, 30))         
        self.Bind(wx.EVT_BUTTON, self.OnStartPlaylistClicked, self.playlistButton)
        hsizer.Add(self.playlistButton, flag = wx.EXPAND)

        bmp = wx.Bitmap("Delete.png", wx.BITMAP_TYPE_PNG)
        b = wx.BitmapButton(self.panelTwo, id = wx.ID_ANY, bitmap = bmp, size = (60, 30)) 
        self.Bind(wx.EVT_BUTTON, self.OnClearPlaylistClicked, b)
        hsizer.Add(b, flag = wx.EXPAND)

        # Add the row to the main vertical sizer
        self.panelTwoSizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
                
        # Create play list panel
        self.PlaylistPanel = Playlist(self.panelTwo, -1, KaraokeMgr, 0, 0)
        self.panelTwoSizer.Add(self.PlaylistPanel, 1, wx.ALL | wx.EXPAND, 5)
        self.panelTwo.SetSizer(self.panelTwoSizer)
        
        # Set the initial screen sizes at start up
        self.splitter.SplitVertically(self.panelOne, self.panelTwo)
        
        # Make the two panels equal size by default
        self.splitter.SetSashGravity(0.5)
        
        # Make the two panels a fixed size
        self.splitter.SetSashInvisible(True)
        
        # Put the top level buttons and main panels in a sizer
        self.MainSizer = wx.BoxSizer(wx.VERTICAL)
        self.MainSizer.Add(self.splitter, 1, wx.ALL | wx.EXPAND)
        self.SetAutoLayout(True)
        self.SetSizer(self.MainSizer)
        
        # This attempts to play an item in the tab 2 play list
        # three seconds after the previous items stops playing
        # this way it can be made to start some backround music
        # between karaoke singers.
        # Message subscriptions
        pub.subscribe(self.PlaySomething, 'playsomething.update')


    def PlaySomething(self, status):
        self.PlaylistPanel.play()
		
    def OnResize(self, event):
        event.Skip()
        width = self.list_ctrl.GetClientSize().width
        self.list_ctrl.SetColumnWidth(0, width)


    def OnOpenDirectory(self, event):
        # Panel 1 btn pressed
        dlg = wx.DirDialog(self, "Choose a directory:")
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.UpdateDisplay(path)
        dlg.Destroy()
        			

    def UpdateDisplay(self, folder_path):
        # Update the listctrl with the file names in the passed folder
        self.list_ctrl.DeleteAllItems()
        tag = ''
        
        if env == ENV_WINDOWS:
            tag = "\\"
            paths = glob.glob(folder_path + "\\*.*")
        else:
            tag = "/"			
            paths = glob.glob(folder_path + "/*.*")
            
        myindex = 0    
        for index, path in enumerate(paths):
            self.dir_path = os.path.dirname(path) + tag
            root, ext = os.path.splitext(os.path.basename(path))
            
            if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
                self.list_ctrl.InsertStringItem(myindex, os.path.basename(path))
            
                # Nice background colour
                if myindex % 2:
                    self.list_ctrl.SetItemBackgroundColour(myindex, "white")
                else:
                    self.list_ctrl.SetItemBackgroundColour(myindex, '#eee8aa')
                myindex = myindex +1
                
        pub.sendMessage('statusbar1.update', status = '%d Songs Found' % myindex)       
			

    def AddToPlayList(self, event):
		# Add a song to panel 2 the play list panel
        count = self.list_ctrl.GetItemCount()
         
        copied = 0         
        for row in range(count):
            item = self.list_ctrl.GetItem(itemId=row)
            if self.list_ctrl.IsSelected(row):
                copied = copied + 1
                filename = item.GetText()
                location = self.dir_path + filename
            
		        # Create a SongStruct because that's what karaoke mgr wants
                settings = self.KaraokeMgr.SongDB.Settings
                song = pykdb.SongStruct(location, settings, filename)
                self.KaraokeMgr.AddToPlaylist(song, self, 0)
            		
		if copied > 0:
			pub.sendMessage('statusbar1.update', status = '%d Songs Copied' % copied)

        if copied == 0:
            wx.MessageBox("No songs selected.")
            return

            
    def OnStartPlaylistClicked(self, event):
		# Panel 2 play button pressed
        self.PlaylistPanel.play()


    def OnClearPlaylistClicked(self, event):
		# Delete selected item
        self.PlaylistPanel.clear()


#class TabThree(wx.Panel):
#    def __init__(self, parent, KaraokeMgr):
#		
#        wx.Panel.__init__(self, parent)
#        
#        self.KaraokeMgr = KaraokeMgr


class HelpFrame(wx.Frame): 
    def __init__(self, parent, title): 
      wx.Frame.__init__(self, parent, wx.ID_ANY, title, style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN, size = (500,600))
      
      # A very basic html help system with a starting page
      # called pykaraoke.html
      html = wx.html.HtmlWindow(self) 
		
      if "gtk2" in wx.PlatformInfo: 
         html.SetStandardFonts() 
         
      html.LoadPage("pykaraoke.html")
      self.Centre()
      self.Show()


class EffectsConfig(wx.Frame): 
    def __init__(self, parent, KaraokeMgr): 
		
		# A config system to pick effects or music for the ten instant play buttons
        wx.Frame.__init__(self, parent, wx.ID_ANY, "Sound Effects Config", style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN, size = (500,600))

        self.KaraokeMgr = KaraokeMgr
        
        self.wildcard = "Karaoke (*.cdg)|*.cdg|"\
            "Video (*.mpg)|*.mpg|"\
            "Karaoke (*.kar)|*.kar"
        
        # Add a panel so it looks correct on all platforms
        self.panel = wx.Panel(self, wx.ID_ANY)
    
        vsizer = wx.BoxSizer(wx.VERTICAL)
        
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        title = wx.StaticText(self.panel, wx.ID_ANY, 'Select the files for the 10 instant play buttons.')
        hsizer.Add(title, 0, wx.ALL | wx.CENTER, 5)
        vsizer.Add(hsizer, 0, wx.CENTER)
        vsizer.Add(wx.StaticLine(self.panel,), 0, wx.ALL|wx.EXPAND, 5)
        
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        bmp = wx.Bitmap('1.png')
        icon = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp)
        fx1 = wx.TextCtrl(self.panel, wx.ID_ANY, self.KaraokeMgr.SongDB.Settings.FX1, size=(350, 25))
        btn1 = wx.Button(self.panel, wx.ID_ANY, 'Brows')
        hsizer.Add(icon, 0, wx.ALL, 5)
        hsizer.Add(fx1, 1, wx.ALL|wx.EXPAND, 5)
        hsizer.Add(btn1, 0, wx.ALL, 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
        self.Bind(wx.EVT_BUTTON, self.Onbtn1, btn1)
        self.tc1 = fx1
        
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        bmp = wx.Bitmap('2.png')
        icon = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp)
        fx2 = wx.TextCtrl(self.panel, wx.ID_ANY, self.KaraokeMgr.SongDB.Settings.FX2, size=(350, 25))
        btn2 = wx.Button(self.panel, wx.ID_ANY, 'Brows')
        hsizer.Add(icon, 0, wx.ALL, 5)
        hsizer.Add(fx2, 1, wx.ALL|wx.EXPAND, 5)
        hsizer.Add(btn2, 0, wx.ALL, 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
        self.Bind(wx.EVT_BUTTON, self.Onbtn2, btn2)
        self.tc2 = fx2
                
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        bmp = wx.Bitmap('3.png')
        icon = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp)
        fx3 = wx.TextCtrl(self.panel, wx.ID_ANY, self.KaraokeMgr.SongDB.Settings.FX3, size=(350, 25))
        btn3 = wx.Button(self.panel, wx.ID_ANY, 'Brows')
        hsizer.Add(icon, 0, wx.ALL, 5)
        hsizer.Add(fx3, 1, wx.ALL|wx.EXPAND, 5)
        hsizer.Add(btn3, 0, wx.ALL, 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
        self.Bind(wx.EVT_BUTTON, self.Onbtn3, btn3)
        self.tc3 = fx3
                
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        bmp = wx.Bitmap('4.png')
        icon = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp)
        fx4 = wx.TextCtrl(self.panel, wx.ID_ANY, self.KaraokeMgr.SongDB.Settings.FX4, size=(350, 25))
        btn4 = wx.Button(self.panel, wx.ID_ANY, 'Brows')
        hsizer.Add(icon, 0, wx.ALL, 5)
        hsizer.Add(fx4, 1, wx.ALL|wx.EXPAND, 5)
        hsizer.Add(btn4, 0, wx.ALL, 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)        
        self.Bind(wx.EVT_BUTTON, self.Onbtn4, btn4)
        self.tc4 = fx4
        
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        bmp = wx.Bitmap('5.png')
        icon = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp)
        fx5 = wx.TextCtrl(self.panel, wx.ID_ANY, self.KaraokeMgr.SongDB.Settings.FX5, size=(350, 25))
        btn5 = wx.Button(self.panel, wx.ID_ANY, 'Brows')
        hsizer.Add(icon, 0, wx.ALL, 5)
        hsizer.Add(fx5, 1, wx.ALL|wx.EXPAND, 5)
        hsizer.Add(btn5, 0, wx.ALL, 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
        self.Bind(wx.EVT_BUTTON, self.Onbtn5, btn5)
        self.tc5 = fx5
                
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        bmp = wx.Bitmap('6.png')
        icon = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp)
        fx6 = wx.TextCtrl(self.panel, wx.ID_ANY, self.KaraokeMgr.SongDB.Settings.FX6, size=(350, 25))
        btn6 = wx.Button(self.panel, wx.ID_ANY, 'Brows')
        hsizer.Add(icon, 0, wx.ALL, 5)
        hsizer.Add(fx6, 1, wx.ALL|wx.EXPAND, 5)
        hsizer.Add(btn6, 0, wx.ALL, 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
        self.Bind(wx.EVT_BUTTON, self.Onbtn6, btn6)
        self.tc6 = fx6
                
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        bmp = wx.Bitmap('7.png')
        icon = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp)
        fx7 = wx.TextCtrl(self.panel, wx.ID_ANY, self.KaraokeMgr.SongDB.Settings.FX7, size=(350, 25))
        btn7 = wx.Button(self.panel, wx.ID_ANY, 'Brows')
        hsizer.Add(icon, 0, wx.ALL, 5)
        hsizer.Add(fx7, 1, wx.ALL|wx.EXPAND, 5)
        hsizer.Add(btn7, 0, wx.ALL, 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
        self.Bind(wx.EVT_BUTTON, self.Onbtn7, btn7)
        self.tc7 = fx7
        
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        bmp = wx.Bitmap('8.png')
        icon = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp)
        fx8 = wx.TextCtrl(self.panel, wx.ID_ANY, self.KaraokeMgr.SongDB.Settings.FX8, size=(350, 25))
        btn8 = wx.Button(self.panel, wx.ID_ANY, 'Brows')
        hsizer.Add(icon, 0, wx.ALL, 5)
        hsizer.Add(fx8, 1, wx.ALL|wx.EXPAND, 5)
        hsizer.Add(btn8, 0, wx.ALL, 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)     
        self.Bind(wx.EVT_BUTTON, self.Onbtn8, btn8)
        self.tc8 = fx8
                
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        bmp = wx.Bitmap('9.png')
        icon = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp)
        fx9 = wx.TextCtrl(self.panel, wx.ID_ANY, self.KaraokeMgr.SongDB.Settings.FX9, size=(350, 25))
        btn9 = wx.Button(self.panel, wx.ID_ANY, 'Brows')
        hsizer.Add(icon, 0, wx.ALL, 5)
        hsizer.Add(fx9, 1, wx.ALL|wx.EXPAND, 5)
        hsizer.Add(btn9, 0, wx.ALL, 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)
        self.Bind(wx.EVT_BUTTON, self.Onbtn9, btn9)
        self.tc9 = fx9
                
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        bmp = wx.Bitmap('0.png')
        icon = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp)
        fx0 = wx.TextCtrl(self.panel, wx.ID_ANY, self.KaraokeMgr.SongDB.Settings.FX0, size=(350, 25))
        btn0 = wx.Button(self.panel, wx.ID_ANY, 'Brows')
        hsizer.Add(icon, 0, wx.ALL, 5)
        hsizer.Add(fx0, 1, wx.ALL|wx.EXPAND, 5)
        hsizer.Add(btn0, 0, wx.ALL, 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.EXPAND, 5)           
        self.Bind(wx.EVT_BUTTON, self.Onbtn0, btn0)
        self.tc0 = fx0
        
        self.panel.SetSizer(vsizer)
        vsizer.Fit(self)
        
        self.Centre()
        self.Show()
        

    def Onbtn1(self, event):
		
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", self.wildcard, wx.OPEN)
		
        if dlg.ShowModal() == wx.ID_OK: 
            self.tc1.WriteText(dlg.GetPath())
            self.KaraokeMgr.SongDB.Settings.FX1 = dlg.GetPath()
            self.KaraokeMgr.SongDB.SaveSettings()            
             
        dlg.Destroy() 


    def Onbtn2(self, event):
		
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", self.wildcard, wx.OPEN)
		
        if dlg.ShowModal() == wx.ID_OK: 
            self.tc2.WriteText(dlg.GetPath())
            self.KaraokeMgr.SongDB.Settings.FX2 = dlg.GetPath()
            self.KaraokeMgr.SongDB.SaveSettings()            
             
        dlg.Destroy() 


    def Onbtn3(self, event):
		
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", self.wildcard, wx.OPEN)
		
        if dlg.ShowModal() == wx.ID_OK: 
            self.tc3.WriteText(dlg.GetPath())
            self.KaraokeMgr.SongDB.Settings.FX3 = dlg.GetPath()
            self.KaraokeMgr.SongDB.SaveSettings()            
             
        dlg.Destroy() 


    def Onbtn4(self, event):
		
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", self.wildcard, wx.OPEN)
		
        if dlg.ShowModal() == wx.ID_OK: 
            self.tc4.WriteText(dlg.GetPath())
            self.KaraokeMgr.SongDB.Settings.FX4 = dlg.GetPath()
            self.KaraokeMgr.SongDB.SaveSettings()            
             
        dlg.Destroy() 


    def Onbtn5(self, event):
		
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", self.wildcard, wx.OPEN)
		
        if dlg.ShowModal() == wx.ID_OK: 
            self.tc5.WriteText(dlg.GetPath())
            self.KaraokeMgr.SongDB.Settings.FX5 = dlg.GetPath()
            self.KaraokeMgr.SongDB.SaveSettings()            
             
        dlg.Destroy() 


    def Onbtn6(self, event):
		
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", self.wildcard, wx.OPEN)
		
        if dlg.ShowModal() == wx.ID_OK: 
            self.tc6.WriteText(dlg.GetPath())
            self.KaraokeMgr.SongDB.Settings.FX6 = dlg.GetPath()
            self.KaraokeMgr.SongDB.SaveSettings()            
             
        dlg.Destroy() 


    def Onbtn7(self, event):
		
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", self.wildcard, wx.OPEN)
		
        if dlg.ShowModal() == wx.ID_OK: 
            self.tc7.WriteText(dlg.GetPath())
            self.KaraokeMgr.SongDB.Settings.FX7 = dlg.GetPath()
            self.KaraokeMgr.SongDB.SaveSettings()            
             
        dlg.Destroy() 


    def Onbtn8(self, event):
		
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", self.wildcard, wx.OPEN)
		
        if dlg.ShowModal() == wx.ID_OK: 
            self.tc8.WriteText(dlg.GetPath())
            self.KaraokeMgr.SongDB.Settings.FX8 = dlg.GetPath()
            self.KaraokeMgr.SongDB.SaveSettings()            
             
        dlg.Destroy() 


    def Onbtn9(self, event):
		
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", self.wildcard, wx.OPEN)
		
        if dlg.ShowModal() == wx.ID_OK: 
            self.tc9.WriteText(dlg.GetPath())
            self.KaraokeMgr.SongDB.Settings.FX9 = dlg.GetPath()
            self.KaraokeMgr.SongDB.SaveSettings()            
             
        dlg.Destroy() 


    def Onbtn0(self, event):
		
        dlg = wx.FileDialog(self, "Choose a file", os.getcwd(), "", self.wildcard, wx.OPEN)
		
        if dlg.ShowModal() == wx.ID_OK: 
            self.tc0.WriteText(dlg.GetPath())
            self.KaraokeMgr.SongDB.Settings.FX0 = dlg.GetPath()
            self.KaraokeMgr.SongDB.SaveSettings()            
             
        dlg.Destroy() 


class BackgroundSound(wx.Frame): 
    def __init__(self, parent, title, KaraokeMgr): 
        wx.Frame.__init__(self, parent, wx.ID_ANY, title, style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN, size = (500,600))

        self.parent = parent
        self.KaraokeMgr = KaraokeMgr
        settings = self.KaraokeMgr.SongDB.Settings

        # Background config options
        
         # Add a panel so it looks correct on all platforms
        self.panel = wx.Panel(self, wx.ID_ANY)
    
        vsizer = wx.BoxSizer(wx.VERTICAL)
        
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        title = wx.StaticText(self.panel, wx.ID_ANY, 'Background music options.')
        hsizer.Add(title, 0, wx.ALL | wx.CENTER, 5)
        vsizer.Add(hsizer, 0, wx.CENTER)
        vsizer.Add(wx.StaticLine(self.panel,), 0, wx.ALL|wx.EXPAND, 5)
        
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
                      
        # Enables or disables the auto play-list functionality
        self.AutoPlayCheckBox = wx.CheckBox(self.panel, -1, "Enable play-list continuous play")
        self.AutoPlayCheckBox.SetValue(self.KaraokeMgr.SongDB.Settings.AutoPlayList)
        hsizer.Add(self.AutoPlayCheckBox, flag = wx.LEFT, border = 5)
        vsizer.Add(hsizer, 0, wx.ALL | wx.LEFT, 5)
        
        hsizer = wx.BoxSizer(wx.HORIZONTAL)  
        hsizer.Add(wx.StaticText(self.panel, wx.ID_ANY, 'This only applies to the Tab 2 right hand play panel.'), 0, wx.ALL | wx.CENTER, 5)
        vsizer.Add(hsizer, 0, wx.LEFT)
        vsizer.Add(wx.StaticLine(self.panel,), 0, wx.ALL|wx.EXPAND, 5)
        

        # The delay before a song automatically starts to play, if their is one in tab 2 panel 2
        hsizer = wx.BoxSizer(wx.HORIZONTAL)  
        hsizer.Add(wx.StaticText(self.panel, wx.ID_ANY, 'Secs delay to wait before playing a background song.'), 0, wx.ALL | wx.CENTER, 5)
        vsizer.Add(hsizer, 0, wx.CENTER)
        self.sld1 = wx.Slider(self.panel, value = self.KaraokeMgr.SongDB.Settings.Timer, minValue = 1, maxValue = 10, style = wx.SL_HORIZONTAL|wx.SL_LABELS)
        self.sld1.Bind(wx.EVT_SLIDER, self.OnTimerSet) 
        vsizer.Add(self.sld1,1,flag = wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, border = 20)
        vsizer.Add(wx.StaticLine(self.panel,), 0, wx.ALL|wx.EXPAND, 5)

        # The master volume control             
        hsizer = wx.BoxSizer(wx.HORIZONTAL)  
        hsizer.Add(wx.StaticText(self.panel, wx.ID_ANY, 'Master volume control for all output.'), 0, wx.ALL | wx.CENTER, 5)
        vsizer.Add(hsizer, 0, wx.CENTER)
        self.sld2 = wx.Slider(self.panel, value = self.KaraokeMgr.SongDB.Settings.Volume, minValue = 0, maxValue = 100, style = wx.SL_HORIZONTAL|wx.SL_LABELS)
        self.sld2.Bind(wx.EVT_SLIDER, self.OnVolumeSlider) 
        vsizer.Add(self.sld2,1,flag = wx.EXPAND | wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, border = 20)
        vsizer.Add(wx.StaticLine(self.panel,), 0, wx.ALL|wx.EXPAND, 5)
        
        self.panel.SetSizer(vsizer)
        vsizer.Fit(self)

        # Attach on exit handler to store settings
        wx.EVT_CLOSE(self, self.OnClose)        

        self.Centre()
        self.Show()


    def OnClose(self, event):
        # Save the auto play option
        self.KaraokeMgr.SongDB.SaveSettings()
        
        if self.AutoPlayCheckBox.IsChecked():
            self.KaraokeMgr.SongDB.Settings.AutoPlayList = True
        else:
            self.KaraokeMgr.SongDB.Settings.AutoPlayList = False

        self.Destroy()

                    
    def OnTimerSet(self, event): 
        obj = event.GetEventObject() 
        val = obj.GetValue() 
        self.KaraokeMgr.SongDB.Settings.Timer = val

      
    def OnVolumeSlider(self, event): 
        obj = event.GetEventObject() 
        val = obj.GetValue()
        manager.SetVolume(val / 100.0)
        self.KaraokeMgr.SongDB.Settings.Volume = val

                 
# Main window
class PyKaraokeWindow (wx.Frame):
    def __init__(self,parent,id,title,KaraokeMgr):
        wx.Frame.__init__(self,parent,wx.ID_ANY, title, size = (800, 500), #manager.settings.WindowSize,
                            style=wx.DEFAULT_FRAME_STYLE|wx.NO_FULL_REPAINT_ON_RESIZE)

        self.KaraokeMgr = KaraokeMgr
        
        # Create the window icon. Find the correct icons path. If
        # fully installed on Linux this will be
        # sys.prefix/share/pykaraoke/icons. Otherwise look for it
        # in the current directory.
        if (os.path.isfile("icons/pykaraoke.xpm")):
            iconspath = "icons"
        else:
            iconspath = os.path.join(sys.prefix, "share/pykaraoke/icons")
        fullpath = os.path.join(iconspath, "pykaraoke.xpm")
        icon1 = wx.Icon(fullpath, wx.BITMAP_TYPE_XPM)
        self.SetIcon(icon1)

        fullpath = os.path.join(iconspath, "microphone.png")
        self.BigIconPath = fullpath

        self.setupToolBar()
        
        # Create a panel and notebook (tabs holder)
        p = wx.Panel(self)
        nb = wx.Notebook(p)
        
        # Create the tab windows
        tab1 = TabOne(nb, KaraokeMgr)
        tab2 = TabTwo(nb, KaraokeMgr)
#        tab3 = TabThree(nb, KaraokeMgr)
        
        # Add the windows to tabs and name them
        nb.AddPage(tab1, "Search Screen")
        nb.AddPage(tab2, "Music Screen")
#        nb.AddPage(tab3, "Monitor Screen")
        
        # Set notebook in a sizer to create the layout
        sizer = wx.BoxSizer()
        sizer.Add(nb, 1, wx.EXPAND)
        p.SetSizer(sizer)

        # Message subscriptions
        pub.subscribe(self.OnStatusOneUpdate, 'statusbar1.update')
        pub.subscribe(self.OnStatusTwoUpdate, 'statusbar2.update')

        # Create the status bar
        self.CreateStatusBar(2)

        # Send Initial messages
        pub.sendMessage('statusbar1.update', status = 'No Search Performed')
        pub.sendMessage('statusbar2.update', status = 'Currently Not Playing A Song')
        
        # Attach on exit handler to clean up temporary files
        wx.EVT_CLOSE(self, self.OnClose)
        
        self.Centre()
        self.Show(True)

    
    def OnStatusOneUpdate(self, status):
        self.SetStatusText(status, 0)

        
    def OnStatusTwoUpdate(self, status):
        self.SetStatusText(status, 1)
        
        # If nothing playing start time, so that if nothing
        # plays for three seconds background music starts
        if status == 'Currently Not Playing A Song':
            self.Timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.Update, self.Timer)
            self.Timer.Start(self.KaraokeMgr.SongDB.Settings.Timer * 1000)
        else:
            # If something playing stop timer
            if self.Timer.IsRunning():
                self.Timer.Stop()           
        
    def Update(self, event):
		# Stop the timer so it only fires once, not every three seconds
		# and request a background musis files starts playing
        self.Timer.Stop()
        if self.KaraokeMgr.SongDB.Settings.AutoPlayList == True:
            pub.sendMessage('playsomething.update', status = 'Play something')
        
        
    def setupToolBar(self):
		# The ten sound effects buttons
	
        self.toolbar = self.CreateToolBar()
        
        self.play1 = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('1.png'), shortHelp="Play 1", longHelp=os.path.basename(self.KaraokeMgr.SongDB.Settings.FX1))
        self.play2 = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('2.png'), shortHelp="Play 2", longHelp=os.path.basename(self.KaraokeMgr.SongDB.Settings.FX2))
        self.play3 = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('3.png'), shortHelp="Play 3", longHelp=os.path.basename(self.KaraokeMgr.SongDB.Settings.FX3))
        self.play4 = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('4.png'), shortHelp="Play 4", longHelp=os.path.basename(self.KaraokeMgr.SongDB.Settings.FX4))
        self.play5 = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('5.png'), shortHelp="Play 5", longHelp=os.path.basename(self.KaraokeMgr.SongDB.Settings.FX5))
        self.play6 = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('6.png'), shortHelp="Play 6", longHelp=os.path.basename(self.KaraokeMgr.SongDB.Settings.FX6))       
        self.play7 = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('7.png'), shortHelp="Play 7", longHelp=os.path.basename(self.KaraokeMgr.SongDB.Settings.FX7))
        self.play8 = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('8.png'), shortHelp="Play 8", longHelp=os.path.basename(self.KaraokeMgr.SongDB.Settings.FX8))
        self.play9 = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('9.png'), shortHelp="Play 9", longHelp=os.path.basename(self.KaraokeMgr.SongDB.Settings.FX9))
        self.play0 = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('0.png'), shortHelp="Play 0", longHelp=os.path.basename(self.KaraokeMgr.SongDB.Settings.FX0))
        
        self.toolbar.AddStretchableSpace()
        
        # The config buttons moved from the menu bar
        self.A = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('A.png'), shortHelp="About", longHelp="Open about dialog")
        self.B = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('B.png'), shortHelp="Background Music", longHelp="Background music options")
        self.C = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('C.png'), shortHelp="Config", longHelp="Open config menu")
        self.D = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('D.png'), shortHelp="Song Data", longHelp="Add or remove songs in database")
        self.E = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('E.png'), shortHelp="Effects", longHelp="Sound effects options")
        self.H = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('Help.png'), shortHelp="Help", longHelp="Open help menu")
        
        self.toolbar.Realize()

        self.Bind(wx.EVT_TOOL, self.OnPlay1, self.play1)
        self.Bind(wx.EVT_TOOL, self.OnPlay2, self.play2)
        self.Bind(wx.EVT_TOOL, self.OnPlay3, self.play3)
        self.Bind(wx.EVT_TOOL, self.OnPlay4, self.play4)
        self.Bind(wx.EVT_TOOL, self.OnPlay5, self.play5)
        self.Bind(wx.EVT_TOOL, self.OnPlay6, self.play6)
        self.Bind(wx.EVT_TOOL, self.OnPlay7, self.play7)
        self.Bind(wx.EVT_TOOL, self.OnPlay8, self.play8)
        self.Bind(wx.EVT_TOOL, self.OnPlay9, self.play9)
        self.Bind(wx.EVT_TOOL, self.OnPlay0, self.play0)
        self.Bind(wx.EVT_TOOL, self.OnAbout, self.A)
        self.Bind(wx.EVT_TOOL, self.OnBackGround, self.B)
        self.Bind(wx.EVT_TOOL, self.OnConfig, self.C)
        self.Bind(wx.EVT_TOOL, self.OnDataBase, self.D)
        self.Bind(wx.EVT_TOOL, self.OnEffects, self.E)
        self.Bind(wx.EVT_TOOL, self.OnHelp, self.H)


    def OnPlay1(self, event):
        path = self.KaraokeMgr.SongDB.Settings.FX1
        root, ext = os.path.splitext(os.path.basename(path))
             
        if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
            settings = self.KaraokeMgr.SongDB.Settings
            song = pykdb.SongStruct(path, settings, os.path.basename(path))
            self.KaraokeMgr.PlayWithoutPlaylist(song)
		

    def OnPlay2(self, event):
        path = self.KaraokeMgr.SongDB.Settings.FX2
        root, ext = os.path.splitext(os.path.basename(path))
             
        if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
            settings = self.KaraokeMgr.SongDB.Settings
            song = pykdb.SongStruct(path, settings, os.path.basename(path))
            self.KaraokeMgr.PlayWithoutPlaylist(song)
			

    def OnPlay3(self, event):
        path = self.KaraokeMgr.SongDB.Settings.FX3
        root, ext = os.path.splitext(os.path.basename(path))
             
        if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
            settings = self.KaraokeMgr.SongDB.Settings
            song = pykdb.SongStruct(path, settings, os.path.basename(path))
            self.KaraokeMgr.PlayWithoutPlaylist(song)
			

    def OnPlay4(self, event):
        path = self.KaraokeMgr.SongDB.Settings.FX4
        root, ext = os.path.splitext(os.path.basename(path))
             
        if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
            settings = self.KaraokeMgr.SongDB.Settings
            song = pykdb.SongStruct(path, settings, os.path.basename(path))
            self.KaraokeMgr.PlayWithoutPlaylist(song)
			

    def OnPlay5(self, event):
        path = self.KaraokeMgr.SongDB.Settings.FX5
        root, ext = os.path.splitext(os.path.basename(path))
             
        if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
            settings = self.KaraokeMgr.SongDB.Settings
            song = pykdb.SongStruct(path, settings, os.path.basename(path))
            self.KaraokeMgr.PlayWithoutPlaylist(song)
			

    def OnPlay6(self, event):
        path = self.KaraokeMgr.SongDB.Settings.FX6
        root, ext = os.path.splitext(os.path.basename(path))
             
        if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
            settings = self.KaraokeMgr.SongDB.Settings
            song = pykdb.SongStruct(path, settings, os.path.basename(path))
            self.KaraokeMgr.PlayWithoutPlaylist(song)
			

    def OnPlay7(self, event):
        path = self.KaraokeMgr.SongDB.Settings.FX7
        root, ext = os.path.splitext(os.path.basename(path))
             
        if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
            settings = self.KaraokeMgr.SongDB.Settings
            song = pykdb.SongStruct(path, settings, os.path.basename(path))
            self.KaraokeMgr.PlayWithoutPlaylist(song)
			

    def OnPlay8(self, event):
        path = self.KaraokeMgr.SongDB.Settings.FX8
        root, ext = os.path.splitext(os.path.basename(path))
             
        if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
            settings = self.KaraokeMgr.SongDB.Settings
            song = pykdb.SongStruct(path, settings, os.path.basename(path))
            self.KaraokeMgr.PlayWithoutPlaylist(song)
			

    def OnPlay9(self, event):
        path = self.KaraokeMgr.SongDB.Settings.FX9
        root, ext = os.path.splitext(os.path.basename(path))
             
        if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
            settings = self.KaraokeMgr.SongDB.Settings
            song = pykdb.SongStruct(path, settings, os.path.basename(path))
            self.KaraokeMgr.PlayWithoutPlaylist(song)
						

    def OnPlay0(self, event):
        path = self.KaraokeMgr.SongDB.Settings.FX0
        root, ext = os.path.splitext(os.path.basename(path))
             
        if self.KaraokeMgr.SongDB.IsExtensionValid(ext):
            settings = self.KaraokeMgr.SongDB.Settings
            song = pykdb.SongStruct(path, settings, os.path.basename(path))
            self.KaraokeMgr.PlayWithoutPlaylist(song)
	            
            						
    def OnAbout(self, event):
		# Show the appropriate About window (we must use a special About window
        # if using Wx2.6 on which AboutDialogInfo() controls are not available).
        if HasWx26Only() == True:
            self.Frame = Wx26AboutWindow(self)
        else:
            abtnfAbout = wx.AboutDialogInfo()
            abtnfAbout.AddArtist("Kelvin Lawson <kelvinl@users.sf.net>")
            abtnfAbout.AddArtist("Tavmjung Bah")
            abtnfAbout.SetCopyright("(C) 2005-2009 Kelvin Lawson\n(C) 2009 John Schneiderman\n(C) 2006 David Rose\n(C) 2005 William Ferrell")
            abtnfAbout.SetDescription("A karaoke player to play your collection of karaoke songs.")
            abtnfAbout.AddDeveloper("Will Ferrell <willfe@gmail.com>")
            abtnfAbout.AddDeveloper("Andrei Gavrila")
            abtnfAbout.AddDeveloper("Kelvin Lawson <kelvinl@users.sf.net>")
            abtnfAbout.AddDeveloper("Craig Rindy")
            abtnfAbout.AddDeveloper("David Rose <pykar@ddrose.com>")
            abtnfAbout.AddDeveloper("John Schneiderman <JohnMS@member.fsf.org>")
            abtnfAbout.AddDeveloper("Ken Williams GW3TMH <ken@kensmail.uk>")
            #abtnfAbout.AddDocWriter("N/A")
            abtnfAbout.SetIcon(wx.Icon(self.BigIconPath, wx.BITMAP_TYPE_PNG, 64, 64))
            LGPLv2_Notice = "PyKaraoke is free software; you can redistribute it and/or modify it under\n the terms of the GNU Lesser General Public License as published by the\n Free Software Foundation; either version 2.1 of the License, or (at your\n option) any later version.\n \n PyKaraoke is distributed in the hope that it will be useful, but WITHOUT\n ANY WARRANTY; without even the implied warranty of MERCHANTABILITY\n or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General\n Public License for more details.\n \n You should have received a copy of the GNU Lesser General Public\n License along with this library; if not, write to the\n Free Software Foundation, Inc.\n 59 Temple Place, Suite 330\n Boston, MA  02111-1307  USA"
            abtnfAbout.SetLicence(LGPLv2_Notice)
            abtnfAbout.SetName("PyKaraoke")
            #abtnfAbout.AddTranslator("N/A")
            abtnfAbout.SetVersion(pykversion.PYKARAOKE_VERSION_STRING)
            abtnfAbout.SetWebSite("http://www.kibosh.org/pykaraoke/")
            wx.AboutBox(abtnfAbout)

		
    def OnBackGround(self, event):
        self.Frame = BackgroundSound(self, "Background Music Settings", self.KaraokeMgr)		
		

    def OnConfig(self, event):
        # Open up the settings setup dialog
        self.Frame = ConfigWindow(self, -1, "Configuration", self.KaraokeMgr)

							    
    def OnDataBase(self, event):
        # Open up the database setup dialog
        self.Frame = DatabaseSetupWindow(self, -1, "Database Setup", self.KaraokeMgr)
		

    def OnEffects(self, event):
        self.Frame = EffectsConfig(self, self.KaraokeMgr)		
		

    def OnHelp(self, event):
		self.Frame = HelpFrame(self, "PyKaraoke Help")
		

    def OnClose(self, event):
        """ Handle closing pykaraoke (need to delete any temporary files on close) """

        # Save the current window size
        # More work needed here, as window size creeps up with each save
        self.KaraokeMgr.SongDB.Settings.WindowSize = (self.GetSize().GetWidth(), self.GetSize().GetHeight())
        self.KaraokeMgr.SongDB.SaveSettings()
        
        # Hide the window
        self.Show(False)

        if self.KaraokeMgr.SongDB.databaseDirty:
            saveString = "You have made changes, would you like to save your database now?"
            answer = wx.MessageBox(saveString, "Save changes?", wx.YES_NO | wx.ICON_QUESTION)
            if answer == wx.YES:
                self.KaraokeMgr.SongDB.SaveDatabase()
                self.KaraokeMgr.SongDB.SaveSettings()

        self.KaraokeMgr.SongDB.CleanupTempFiles()
        self.Destroy()

        # Normally, destroying the main window is sufficient to exit
        # the application, but sometimes something might have gone
        # wrong and a window or thread might be left hanging.
        # Therefore, close the whole thing down forcefully.
        wx.Exit()

        # We also explicitly close with sys.exit(), since we've forced
        # the MainLoop to keep running.
        sys.exit(0)


# Subclass WxPyEvent to add storage for an extra data pointer
class PyKaraokeEvent(wx.PyEvent):
    def __init__(self, event_id, data):
        wx.PyEvent.__init__(self)
        self.SetEventType(event_id)
        self.data = data


# Main manager class, starts the window and handles the playlist and players
class PyKaraokeManager:
    def __init__(self, gui=True):
        self.SongDB = pykdb.globalSongDB
        self.gui = True
        self.SongDB.LoadSettings(None)

        # Set the global command-line options.
        if manager.options == None:
            parser = self.SetupOptions()
            (manager.options, args) = parser.parse_args()
            manager.ApplyOptions(self.SongDB)

            if (len(args) != 0):
                # If we received filename arguments on the command
                # line, don't start up a gui.
                self.gui = False

                for a in args:
                    # Maybe it's a directory name or a zip name or
                    # something.
                    if os.path.exists(a):
                        self.SongDB.AddFile(a)
                    elif a[-1] == '.' and os.path.exists(a + 'cdg'):
                        self.SongDB.AddFile(a + 'cdg')
                    else:
                        # Maybe it's an embedded file.  Add it anyway.
                        song = self.SongDB.makeSongStruct(a)
                        self.SongDB.addSong(song)

        # Set the default file types that should be displayed
        self.Player = None
        # Used to tell the song finished callback that a song has been
        # requested for playing straight away
        self.DirectPlaySongStruct = None
        # Used to store the currently playing song (if from the playlist)
        self.PlayingIndex = 0

        if self.gui:
            # Set up the WX windows
            if manager.options.validate:
                self.SongDB.LoadDatabase(None)
                manager.ValidateDatabase(self.SongDB)
                sys.exit(0)
            else:
                self.EVT_ERROR_POPUP = wx.NewId()
                self.Frame = PyKaraokeWindow(None, -1, "PyKaraoke ", self) # + pykversion.PYKARAOKE_VERSION_STRING, self)
                self.Frame.Connect(-1, -1, self.EVT_ERROR_POPUP, self.ErrorPopupEventHandler)
                self.SongDB.LoadDatabase(self.ErrorPopupCallback)

        else:
            # Without a GUI, just play all the songs in the database
            # (which is to say, all the songs on the command line.)

            if manager.options.validate:
                manager.ValidateDatabase(self.SongDB)
            else:
                for song_struct in self.SongDB.FullSongList:
                    self.StartPlayer(song_struct)
                    manager.WaitForPlayer()
            sys.exit(0)

    def SetupOptions(self):
        """ Initialise and return optparse OptionParser object,
        suitable for parsing the command line options to this
        application. """

        return manager.SetupOptions("%prog [options]", self.SongDB)


    # Called when a karaoke file is added to the playlist from the
    # file tree or search results for adding to the playlist.
    # Handles adding to the playlist panel, playing if necessary etc.
    # Takes a SongStruct so it has both title and full path details.
    # Stores the SongStruct in the Playlist control and sets the title.
    def AddToPlaylist(self, song_struct, client_win, flag):
        # Add the performer information if enabled
        performer = ""
        if flag == 1:
            if self.SongDB.Settings.UsePerformerName:
                dlg = PerformerPrompt.PerformerPrompt(client_win)
                if dlg.ShowModal() == wx.ID_OK:
                    performer = dlg.getPerformer()
        client_win.PlaylistPanel.AddItem(song_struct, performer)
        

    # Called when a karaoke file is played from the file tree or search
    # results. Does not add to the playlist, just plays directly,
    # cancelling any song currently playing.
    def PlayWithoutPlaylist(self, song_struct):
        if self.Player:
            # If a song is already playing, start closing it. It will be
            # be played directly by the song finished callback.
            self.Player.Close()
            self.DirectPlaySongStruct = song_struct
        else:
            # If no song is already playing, just play this one directly
            self.StartPlayer(song_struct)

    # Called if a song is double-clicked in the playlist.
    # If no song is playing, just start the song at the selected
    # playlist item. If a song is playing, then tell the player to
    # start closing, and set PlayingIndex so that the song finished
    # callback will start playing this one.
    def PlaylistStart(self, song_index, client_win):
        if not self.Player:
            song_struct = client_win.GetSongStruct(song_index)
            self.StartPlayer(song_struct)
            self.PlayingIndex = song_index
            # Show the song as selected in the playlist
            client_win.SetItemSelected(self.PlayingIndex)
            client_win.Playlist.DeleteItem(self.PlayingIndex)
            client_win.PlaylistSongStructList.pop(self.PlayingIndex)
        else:
            # Note that this will be -1 if the first item is playing,
            # but this is a valid index for GetNextItem() - it will
            # get the first song in the list.
            self.PlayingIndex = song_index - 1
            self.Player.Close()


    def SongFinishedCallback(self):
        if not self.gui:
            self.SongDB.CleanupTempFiles()
            return
        manager.CloseDisplay()

        # Set the status bar
        pub.sendMessage('statusbar2.update', status = 'Currently Not Playing A Song')
        pub.sendMessage('gauge.update', status = 0)
        
        self.Player = None
        # Delete any temporary files that may have been unzipped
        self.SongDB.CleanupTempFiles()


    # The callback is in the player thread context, so need to post an event
    # for the GUI thread, actually handled by ErrorPopupEventHandler()
    def ErrorPopupCallback(self, ErrorString):
        if not self.gui:
            print ErrorString
            return
        # We use the extra data storage we got by subclassing WxPyEvent to
        # pass data to the event handler (the error string).
        event = PyKaraokeEvent(self.EVT_ERROR_POPUP, ErrorString)
        wx.PostEvent (self.Frame, event)
        if self.Player != None:
            self.Player.shutdown()
            self.Player = None
        self.SongDB.CleanupTempFiles()


    # Handle the error popup event, runs in the GUI thread.
    def ErrorPopupEventHandler(self, event):
        ErrorPopup(event.data)


    # Takes a SongStruct, which contains any info on ZIPs etc
    def StartPlayer(self, song_struct):
        # Create the necessary player instance for this filetype.
        self.Player = song_struct.MakePlayer(
            self.SongDB, self.ErrorPopupCallback, self.SongFinishedCallback)
        if self.Player == None:
            return
            
        # Set volume    
        manager.SetVolume(self.SongDB.Settings.Volume / 100.0)

        # Start playing
        self.Player.Play()
        
        timeLength = self.Player.GetLength()
        if timeLength > 0:
            pub.sendMessage('gauge.start', status = timeLength + 1)
        else:
			pub.sendMessage('gauge.start', status = 100)    


    def OnIdle(self, event):
        manager.Poll()
        
        if self.Player:
            wx.WakeUpIdle()
            if self.gui:
                # Display the time played and the time remaining
                position = self.Player.GetPos()
                minutes = position / 60000
                seconds = (position % 60000) / 1000
                timeLength = self.Player.GetLength()
                timeLeft = timeLength - (position / 1000)
                
                if timeLeft <= 0:
					# Failed to get actual playing time
                    pub.sendMessage('statusbar2.update', status = '[%02d:%02d] %s - %s' % (minutes, seconds, self.Player.Song.Artist, self.Player.Song.Title))
                else:
					# Got playing time, display it
                    pub.sendMessage('gauge.update', status = timeLeft)					
                    minutesRemaining = timeLeft / 60
                    secondsRemaining = timeLeft % 60
                    pub.sendMessage('statusbar2.update', status = '[%02d:%02d] %s - %s' % (minutesRemaining, secondsRemaining, self.Player.Song.Artist, self.Player.Song.Title))
        

# Decide whether only WxPython v2.6 is available (and no later version).
def HasWx26Only ():
    # Don't do this for py2exe builds, for which we cannot use wxversion
    if not hasattr(sys, 'frozen'):
        # Check whether only Wx2.6 is installed. We know that a minimum of 2.6 is in use,
        # so check whether any later versions are installed.
        wx26_only = True
        vers = wxversion.getInstalled()
        for ver in vers:
            if ('2.6' not in ver) and ('2.4' not in ver):
                wx26_only = False
    else:
        # Py2exe builds: always assume later than Wx2.6
        wx26_only = False

    return wx26_only


# Subclass wx.App so that we can override the normal Wx MainLoop().
# We only have to do this because since Wx 2.8, the MainLoop()
# appears to be stealing all time from Pygame, and we run Pygame
# and Wx in the same process.
class PyKaraokeApp(wx.App):
    def MainLoop(self):

        # Create an event loop and make it active.
        evtloop = wx.EventLoop()
        wx.EventLoop.SetActive(evtloop)

        # Loop forever.
        while True:

            # This inner loop will process any GUI events
            # until there are no more waiting.
            while evtloop.Pending():
                evtloop.Dispatch()

            # Send idle events to idle handlers.  Sleep here to yield
            # the timeslice, but not for any longer than that, since
            # any time spent in sleep() can steal time away from
            # pygame, especially on slower computers.
            time.sleep(0)
            self.ProcessIdle()

    def OnInit(self):
        # On OSX, it's important to initialize pygame first, *before*
        # we create the main menu, since initializing pygame seems to
        # replace whatever menu we've already created.
        manager.Poll()
        
        Mgr = PyKaraokeManager()
        if Mgr.gui:
            self.Bind(wx.EVT_IDLE, Mgr.OnIdle)
        return True

def main():

    MyApp = PyKaraokeApp(False)

    # Normally, MainLoop() should only be called once; it will
    # return when it receives WM_QUIT.  However, since pygame
    # posts WM_QUIT when the user closes the pygame window, we
    # need to keep running MainLoop indefinitely.  This means we
    # need to force-quit the application when we really do intend
    # to exit.
    while True:
        MyApp.MainLoop()

if __name__ == "__main__":
    sys.exit(main())
