### Copyright (C) 2007 Peter Williams <peter_ono@users.sourceforge.net>

### This program is free software; you can redistribute it and/or modify
### it under the terms of the GNU General Public License as published by
### the Free Software Foundation; version 2 of the License only.

### This program is distributed in the hope that it will be useful,
### but WITHOUT ANY WARRANTY; without even the implied warranty of
### MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
### GNU General Public License for more details.

### You should have received a copy of the GNU General Public License
### along with this program; if not, write to the Free Software
### Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import gtk

log = None
SCM = None
PM = None
main_window = None
tooltips = None

def init(ifce_module, console_log, window):
    global log, SCM, PM, main_window, tooltips
    log = console_log
    SCM = ifce_module.SCMInterface()
    PM = ifce_module.PMInterface()
    main_window = window
    tooltips = gtk.Tooltips()
    tooltips.enable()

class BusyIndicator:
    def __init__(self):
        pass
    def show_busy(self):
        if self.window:
            self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
            while gtk.events_pending():
                gtk.main_iteration()
    def unshow_busy(self):
        if self.window:
            self.window.set_cursor(None)

class BusyIndicatorUser:
    def __init__(self, busy_indicator):
        if busy_indicator:
            self._busy_indicator = busy_indicator
        else:
            self._busy_indicator = main_window
    def show_busy(self):
        self._busy_indicator.show_busy()
    def unshow_busy(self):
        self._busy_indicator.unshow_busy()

