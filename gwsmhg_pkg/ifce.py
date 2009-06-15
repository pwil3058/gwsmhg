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

def show_busy():
    if main_window.window:
        main_window.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
        while gtk.events_pending():
            gtk.main_iteration()

def unshow_busy():
    if main_window.window:
        main_window.window.set_cursor(None)

