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
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import gtk

from . import gutils
from . import file_tree
from . import patch_list

class TopPatchFilesWidget(gtk.VBox):
    def __init__(self, busy_indicator):
        gtk.VBox.__init__(self)
        # file tree view wrapped in scrolled window
        self.file_tree = file_tree.TopPatchFileTreeView(busy_indicator=busy_indicator)
        scw = gtk.ScrolledWindow()
        scw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.file_tree.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.file_tree.set_headers_visible(False)
        self.file_tree.set_size_request(240, 320)
        scw.add(self.file_tree)
        # file tree menu bar
        self.menu_bar = self.file_tree.ui_manager.get_widget("/files_menubar")
        self.pack_start(self.menu_bar, expand=False)
        self.pack_start(scw, expand=True, fill=True)
        self.show_all()

class PatchManagementWidget(gtk.VBox):
    def __init__(self, busy_indicator=None):
        gtk.VBox.__init__(self)
        self._file_tree = TopPatchFilesWidget(busy_indicator=busy_indicator)
        self._patch_list = patch_list.List(busy_indicator=busy_indicator)
        self._menu_bar = self._patch_list.ui_manager.get_widget("/patches_menubar")
        self._tool_bar = self._patch_list.ui_manager.get_widget("/patches_toolbar")
        #self._tool_bar.set_icon_size(gtk.ICON_SIZE_SMALL_TOOLBAR)
        #self._tool_bar.set_style(gtk.TOOLBAR_BOTH_HORIZ)
        self._tool_bar.set_style(gtk.TOOLBAR_BOTH)
        self.pack_start(self._menu_bar, expand=False)
        self.pack_start(self._tool_bar, expand=False)
        hpane = gtk.HPaned()
        hpane.add1(self._file_tree)
        hpane.add2(self._patch_list)
        self.pack_start(hpane)
