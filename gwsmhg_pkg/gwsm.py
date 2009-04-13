### Copyright (C) 2007 Peter Williams <pwil3058@bigpond.net.au>

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

import os, gtk
from gwsmhg_pkg import console, change_set, file_tree, gutils

GWSM_UI_DESCR = \
'''
<ui>
  <menubar name="gwsm_menubar">
    <menu name="gwsm_wd" action="gwsm_working_directory">
      <menuitem action="gwsm_change_wd"/>
      <menuitem action="gwsm_quit"/>
    </menu>
  </menubar>
</ui>
'''

class gwsm(gtk.Window, gutils.BusyIndicator):
    def __init__(self, scm_ifce):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        gutils.BusyIndicator.__init__(self)
        self.connect("destroy", self._quit)
        self._action_group = gtk.ActionGroup("gwsm")
        self._action_group.add_actions(
            [
                ("gwsm_working_directory", None, "_Working Directory"),
                ("gwsm_change_wd", gtk.STOCK_OPEN, "_Open", "",
                 "Change current working directory", self._change_wd_acb),
                ("gwsm_quit", gtk.STOCK_QUIT, "_Quit", "",
                 "Quit", self._quit),
            ])
        self._ui_manager = gtk.UIManager()
        self._ui_manager.insert_action_group(self._action_group, -1)
        self._ui_manager.add_ui_from_string(GWSM_UI_DESCR)
        self._menubar = self._ui_manager.get_widget("/gwsm_menubar")
        self._tooltips = gtk.Tooltips()
        self._tooltips.enable()
        self._console_log = console.ConsoleLog(scm_ifce, tooltips=self._tooltips)
        self._scm_ifce = self._console_log.get_scm_ifce()
        self._parent_view = change_set.ParentsView(self._scm_ifce)
        self._file_tree_widget = file_tree.ScmCwdFilesWidget(scm_ifce=self._scm_ifce,
            console_log=self._console_log, tooltips=self._tooltips)
        self._notebook = gtk.Notebook()
        self._notebook.set_size_request(640, 240)
        self._heads_view = change_set.HeadsView(self._scm_ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._heads_view), gtk.Label("Heads"))
        self._tags_view = change_set.TagsView(self._scm_ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._tags_view), gtk.Label("Tags"))
        self._branches_view = change_set.BranchesView(self._scm_ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._branches_view), gtk.Label("Branches"))
        self._notebook.append_page(gtk.Label("MQ controls go here"), gtk.Label("MQ"))
        # Now lay the widgets out
        vbox = gtk.VBox()
        vbox.pack_start(self._menubar, expand=False)
        vbox.pack_start(self._parent_view, expand=False)
        hpane = gtk.HPaned()
        vbox.pack_start(hpane, expand=True)
        hpane.add1(self._file_tree_widget)
        vpane = gtk.VPaned()
        hpane.add2(vpane)
        vpane.add1(self._notebook)
        vpane.add2(self._console_log)
        self.add(vbox)
        self.show_all()
        self._update_title()
        self._parent_view.get_selection().unselect_all()
    def _quit(self, widget):
        gtk.main_quit()
    def _update_title(self):
        self.set_title("%s: %s" % (self._scm_ifce.name, os.getcwd()))
    def _change_wd(self, newdir=None):
        self._show_busy()
        if newdir:
            os.chdir(newdir)
        else:
            newdir = os.getcwd()
        # This is where'll we get the appropriate SCM interface in later versions
        newrootdir = self._scm_ifce.get_root()
        if newrootdir and newrootdir != newdir:
            os.chdir(newrootdir)
        self._console_log.append_entry("New Working Directory: %s" % os.getcwd())
        self._parent_view.refresh_after_commit()
        self._heads_view.refresh_after_commit()
        self._tags_view.refresh_after_commit()
        self._branches_view.refresh_after_commit()
        self._file_tree_widget.file_tree.repopulate_tree()
        self._update_title()
        self._unshow_busy()
    def _change_wd_acb(self, action=None):
        dialog = gtk.FileChooserDialog("New Directory", self, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder(os.getcwd())
        response = dialog.run()
        dirname = dialog.get_filename()
        dialog.destroy()
        if response == gtk.RESPONSE_OK:
            self._change_wd(dirname)

