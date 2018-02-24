#!/usr/bin/env python

# Python karaoke performer prompt

#******************************************************************************
#**** Copyright (C) 2018  Ken Williams GW3TMH (ken@kensmail.uk)            ****
#**** Copyright (C) 2010  Kelvin Lawson (kelvinl@users.sourceforge.net)    ****
#**** Copyright (C) 2010  Python Karaoke Development Team                  ****
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

class PerformerPrompt(wx.Dialog):
    """ An interface for requesting a performer's name. """
    def __init__(self, parent):
        """ Creates the interface. """
        wx.Dialog.__init__(self, parent, -1, "Karaoke Performer ?")

        # Add the performer prompt
        self.PerformerText = wx.StaticText(self, wx.ID_ANY, "Name:")
        self.PerformerID = wx.NewId()
        self.PerformerTxtCtrl = wx.TextCtrl(self, self.PerformerID, "", size=(150, 25), style=wx.TE_PROCESS_ENTER)
        self.PerformerSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.PerformerSizer.Add(self.PerformerText, 0, wx.ALL)
        self.PerformerSizer.Add(self.PerformerTxtCtrl, 0, wx.ALL)

        # Add window buttons
        self.ButtonSizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.Bind(wx.EVT_BUTTON, self.onOK, id = wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.onCANCEL, id = wx.ID_CANCEL)
        self.PerformerTxtCtrl.Bind(wx.EVT_TEXT_ENTER, self.onENTER, id = wx.ID_ANY)

        # Create GUI with Sizers
        self.MainSizer = wx.BoxSizer(wx.VERTICAL)
        self.MainSizer.Add(self.PerformerSizer, 0, wx.ALL, 3)
        self.MainSizer.Add(self.ButtonSizer, 0, wx.ALL, 3)
        self.SetSizerAndFit(self.MainSizer)

        self.performer = ""
        self.PerformerTxtCtrl.SetFocus()
        
    def onENTER(self, event):
        """ Sets the performer entered and closes the dialogue. """
        self.performer = self.PerformerTxtCtrl.GetValue()
        self.EndModal(wx.ID_OK)
        return True

    def onCANCEL(self, event):
        """ Sets the performer entered and closes the dialogue. """
        self.performer = ""
        self.EndModal(wx.ID_OK)
        return False

    def onOK(self, event):
        """ Sets the performer entered and closes the dialogue. """
        self.performer = self.PerformerTxtCtrl.GetValue()
        self.EndModal(wx.ID_OK)
        return True

    def getPerformer(self):
        """ Gives the performer's name """
        return self.performer
