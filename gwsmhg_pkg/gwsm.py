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

import os, gtk, gobject, sys
from gwsmhg_pkg import console, change_set, file_tree, gutils, utils, patch_mgr

WS_TABLE_DESCR = \
[
    ["Alias", gobject.TYPE_STRING, True, [("editable", True)]],
    ["Path", gobject.TYPE_STRING, True, []],
]

WS_PATH = gutils.find_label_index(WS_TABLE_DESCR, "Path")
WS_ALIAS = gutils.find_label_index(WS_TABLE_DESCR, "Alias")

GSWMHG_D_NAME = os.sep.join([utils.HOME, ".gwsmhg.d"])
SAVED_WS_FILE_NAME = os.sep.join([GSWMHG_D_NAME, "workspaces"]) 

if not os.path.exists(GSWMHG_D_NAME):
    os.mkdir(GSWMHG_D_NAME, 0775)

class WSPathView(gutils.TableView):
    def __init__(self):
        gutils.TableView.__init__(self, WS_TABLE_DESCR,
                                  sel_mode=gtk.SELECTION_SINGLE,
                                  perm_headers=True)
        self._alias_ctr = self.get_column(WS_ALIAS).get_cell_renderers()[0]
        self._alias_ctr.connect("edited", self._edited_cb, self.get_model())
        self.set_size_request(480, 160)
        model = self.get_model()
#        model.set_sort_func(WS_ALIAS, self._sort_func, WS_ALIAS)
#        model.set_sort_func(WS_PATH, self._sort_func, WS_PATH)
        self.read_saved_ws_file()
#        model.set_sort_column_id(WS_ALIAS, gtk.SORT_ASCENDING)
#        self.set_headers_clickable(True)
#    def _sort_func(self, model, iter1, iter2, index):
#        v1 = model.get_value(iter1, index)
#        v2 = model.get_value(iter2, index)
#        if v1 < v2:
#            return -1
#        elif v1 > v2:
#            return 1
#        else:
#            return 0
    def read_saved_ws_file(self):
        valid_ws_list = []
        if not os.path.exists(SAVED_WS_FILE_NAME):
            self.set_contents([])
            return
        file = open(SAVED_WS_FILE_NAME, 'r')
        lines = file.readlines()
        file.close()
        for line in lines:
            data = line.strip().split(os.pathsep, 1)
            if os.path.exists(os.path.expanduser(data[WS_PATH])):
                valid_ws_list.append(data)
        self.set_contents(valid_ws_list)
        self._write_list_to_file(valid_ws_list)
        self.get_selection().unselect_all()
    def _write_list_to_file(self, list):
        file = open(SAVED_WS_FILE_NAME, 'w')
        for ws in list:
            file.write(os.pathsep.join(ws))
            file.write(os.linesep)
        file.close()
    def add_ws(self, path, alias=""):
        if os.path.exists(path):
            store = self.get_model()
            iter = store.get_iter_first()
            while iter:
                if os.path.samefile(os.path.expanduser(store.get_value(iter, WS_PATH)), path):
                    if alias:
                        store.set_value(iter, WS_ALIAS, alias)
                    return
                iter = store.iter_next(iter)
            if not alias:
                alias = os.path.basename(path)
            data = ["",""]
            data[WS_PATH] = utils.path_rel_home(path)
            data[WS_ALIAS] = alias
            store.append(data)
            self.save_to_file()
    def save_to_file(self):
        list = self.get_contents()
        self._write_list_to_file(list)
    def get_selected_ws(self):
        data = self.get_selected_data([WS_PATH, WS_ALIAS])
        return data[0]
    def _edited_cb(self, cell, path, new_text, model):
        model[path][WS_ALIAS] = new_text
        self.save_to_file()

class WSOpenDialog(gtk.Dialog, gutils.BusyIndicator, gutils.BusyIndicatorUser):
    def __init__(self, parent=None):
        gutils.BusyIndicator.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, self)
        gtk.Dialog.__init__(self, title="gwsmg: Select Workspace/Directory", parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        hbox = gtk.HBox()
        self.path_view = WSPathView()
        self.path_view.get_selection().connect("changed", self._selection_cb)
        hbox.pack_start(gutils.wrap_in_scrolled_window(self.path_view))
        self._select_button = gtk.Button(label="_Select")
        self._select_button.connect("clicked", self._select_cb)
        hbox.pack_start(self._select_button, expand=False, fill=False)
        self.vbox.pack_start(hbox)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Directory:"))
        self._path = gutils.EntryWithHistory()
        self._path.set_width_chars(32)
        self._path.connect("activate", self._path_cb)
        hbox.pack_start(self._path, expand=True, fill=True)
        self._browse_button = gtk.Button(label="_Browse")
        self._browse_button.connect("clicked", self._browse_cb)
        hbox.pack_start(self._browse_button, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        self.show_all()
        self.path_view.get_selection().unselect_all()
    def _selection_cb(self, selection=None):
        self._select_button.set_sensitive(selection.count_selected_rows())
    def _select_cb(self, button=None):
        path = self.path_view.get_selected_ws()
        self._path.set_text(path[0])
    def _path_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def _browse_cb(self, button=None):
        dirname = gutils.ask_dir_name("gwsmhg: Browse for Directory", existing=True, parent=self)
        if dirname:
            self._path.set_text(utils.path_rel_home(dirname))
    def get_path(self):
        return os.path.expanduser(self._path.get_text())

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

class gwsm(gtk.Window, gutils.BusyIndicator, gutils.BusyIndicatorUser):
    def __init__(self, ifce):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        gutils.BusyIndicator.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, self)
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
        self._ifce = ifce(busy_indicator=self.get_busy_indicator(), tooltips=self._tooltips)
        # see if we're in a valid work space and if not offer a selection
        rootdir = self._ifce.SCM.get_root()
        if not rootdir:
            open_dialog = WSOpenDialog()
            if open_dialog.run() == gtk.RESPONSE_OK:
                path = open_dialog.get_path()
                if path:
                    try:
                        os.chdir(path)
                        rootdir = self._ifce.SCM.get_root()
                        if rootdir:
                            os.chdir(rootdir)
                            open_dialog.path_view.add_ws(rootdir)
                    except:
                        pass
            else:
                sys.exit()
            open_dialog._show_busy()
        else:
            os.chdir(rootdir)
            open_dialog = None # we need this later
        self._parent_view = change_set.ParentsView(self._ifce)
        self._file_tree_widget = file_tree.ScmCwdFilesWidget(ifce=self._ifce,
            busy_indicator=self.get_busy_indicator(), tooltips=self._tooltips)
        self._notebook = gtk.Notebook()
        self._notebook.set_size_request(640, 360)
        self._patch_mgr = patch_mgr.PatchManagementWidget(ifce=self._ifce,
            busy_indicator=self.get_busy_indicator(), tooltips=self._tooltips)
        self._notebook.append_page(self._patch_mgr, gtk.Label(self._ifce.PM.name))
        self._heads_view = change_set.HeadsView(self._ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._heads_view), gtk.Label("Heads"))
        self._tags_view = change_set.TagsView(self._ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._tags_view), gtk.Label("Tags"))
        self._branches_view = change_set.BranchesView(self._ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._branches_view), gtk.Label("Branches"))
        self._notebook.set_current_page(0)
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
        vpane.add2(self._ifce.log)
        self.add(vbox)
        self.show_all()
        self._update_title()
        self._parent_view.get_selection().unselect_all()
        if open_dialog:
            open_dialog._unshow_busy()
            open_dialog.destroy()
    def _quit(self, widget):
        gtk.main_quit()
    def _update_title(self):
        self.set_title("gwsm%s: %s" % (self._ifce.SCM.name, utils.path_rel_home(os.getcwd())))
    def _change_wd(self, newdir=None):
        if newdir:
            os.chdir(newdir)
        else:
            newdir = os.getcwd()
        # This is where'll we get the appropriate SCM interface in later versions
        newrootdir = self._ifce.SCM.get_root()
        if newrootdir and newrootdir != newdir:
            os.chdir(newrootdir)
    def _reset_after_cd(self):
        self._show_busy()
        self._ifce.log.append_entry("New Working Directory: %s" % os.getcwd())
        self._parent_view.update_for_chdir()
        self._heads_view.update_for_chdir()
        self._tags_view.update_for_chdir()
        self._branches_view.update_for_chdir()
        self._file_tree_widget.update_for_chdir()
        self._patch_mgr.update_for_chdir()
        self._update_title()
        self._unshow_busy()
    def _change_wd_acb(self, action=None):
        open_dialog = WSOpenDialog(parent=self)
        if open_dialog.run() == gtk.RESPONSE_OK:
            path = open_dialog.get_path()
            if not path:
                open_dialog.destroy()
            else:
                old_path = os.getcwd()
                os.chdir(path)
                rootdir = self._ifce.SCM.get_root()
                if rootdir:
                    os.chdir(rootdir)
                    open_dialog.path_view.add_ws(rootdir)
                    path = rootdir
                open_dialog.destroy()
                if not os.path.samefile(old_path, os.path.expanduser(path)):
                    self._reset_after_cd()
        else:
            open_dialog.destroy()

