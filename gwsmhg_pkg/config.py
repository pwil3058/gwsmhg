# -*- python -*-

### Copyright (C) 2005 Peter Williams <peter_ono@users.sourceforge.net>

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

import os, gobject, gtk, urlparse, fnmatch, os.path
from gwsmhg_pkg import gutils, utils, icons, table

REPO_TABLE_DESCR = \
[
    ["Alias", gobject.TYPE_STRING, True, [("editable", True)]],
    ["Path", gobject.TYPE_STRING, True, []],
]

REPO_PATH = gutils.find_label_index(REPO_TABLE_DESCR, "Path")
REPO_ALIAS = gutils.find_label_index(REPO_TABLE_DESCR, "Alias")

GSWMHG_D_NAME = os.sep.join([utils.HOME, ".gwsmhg.d"])
SAVED_WS_FILE_NAME = os.sep.join([GSWMHG_D_NAME, "workspaces"])
SAVED_REPO_FILE_NAME = os.sep.join([GSWMHG_D_NAME, "repositories"])

if not os.path.exists(GSWMHG_D_NAME):
    os.mkdir(GSWMHG_D_NAME, 0775)

def append_saved_ws(path, alias=None):
    file = open(SAVED_WS_FILE_NAME, 'a')
    abbr_path = utils.path_rel_home(path)
    if not alias:
        alias = os.path.basename(path)
    file.write(os.pathsep.join([alias, abbr_path]))
    file.write(os.linesep)
    file.close()

class AliasPathView(gutils.TableView):
    def __init__(self, saved_file):
        self._saved_file = saved_file
        gutils.TableView.__init__(self, REPO_TABLE_DESCR,
                                  sel_mode=gtk.SELECTION_SINGLE,
                                  perm_headers=True)
        self._alias_ctr = self.get_column(REPO_ALIAS).get_cell_renderers()[0]
        self._alias_ctr.connect("edited", self._edited_cb, self.get_model())
        self.set_size_request(480, 160)
#        model = self.get_model()
#        model.set_sort_func(REPO_ALIAS, self._sort_func, REPO_ALIAS)
#        model.set_sort_func(REPO_PATH, self._sort_func, REPO_PATH)
        self.read_saved_file()
#        model.set_sort_column_id(REPO_ALIAS, gtk.SORT_ASCENDING)
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
    def _extant_path(self, path):
        return os.path.exists(os.path.expanduser(path))
    def read_saved_file(self):
        extant_ap_list = []
        if not os.path.exists(self._saved_file):
            self.set_contents([])
            return
        file = open(self._saved_file, 'r')
        lines = file.readlines()
        file.close()
        for line in lines:
            data = line.strip().split(os.pathsep, 1)
            if data in extant_ap_list:
                continue
            if self._extant_path(data[REPO_PATH]):
                extant_ap_list.append(data)
        extant_ap_list.sort()
        self.set_contents(extant_ap_list)
        self._write_list_to_file(extant_ap_list)
        self.get_selection().unselect_all()
    def _write_list_to_file(self, list):
        file = open(self._saved_file, 'w')
        for ap in list:
            file.write(os.pathsep.join(ap))
            file.write(os.linesep)
        file.close()
    def _same_paths(self, path1, path2):
        return os.path.samefile(os.path.expanduser(path1), path2)
    def _default_alias(self, path):
        return os.path.basename(path)
    def _abbrev_path(self, path):
        return utils.path_rel_home(path)
    def add_ap(self, path, alias=""):
        if self._extant_path(path):
            store = self.get_model()
            iter = store.get_iter_first()
            while iter:
                if self._same_paths(store.get_value(iter, REPO_PATH), path):
                    if alias:
                        store.set_value(iter, REPO_ALIAS, alias)
                    return
                iter = store.iter_next(iter)
            if not alias:
                alias = self._default_alias(path)
            data = ["",""]
            data[REPO_PATH] = self._abbrev_path(path)
            data[REPO_ALIAS] = alias
            store.append(data)
            self.save_to_file()
    def save_to_file(self):
        list = self.get_contents()
        self._write_list_to_file(list)
    def get_selected_ap(self):
        data = self.get_selected_data([REPO_PATH, REPO_ALIAS])
        return data[0]
    def _edited_cb(self, cell, path, new_text, model):
        model[path][REPO_ALIAS] = new_text
        self.save_to_file()

class WSPathView(AliasPathView):
    def __init__(self):
        AliasPathView.__init__(self, SAVED_WS_FILE_NAME)

class PathSelectDialog(gtk.Dialog, gutils.BusyIndicator, gutils.BusyIndicatorUser):
    def __init__(self, create_view, label, parent=None):
        gtk.Dialog.__init__(self, title="gwsmg: Select %s" % label, parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        hbox = gtk.HBox()
        self.ap_view = create_view()
        self.ap_view.get_selection().connect("changed", self._selection_cb)
        hbox.pack_start(gutils.wrap_in_scrolled_window(self.ap_view))
        self._select_button = gtk.Button(label="_Select")
        self._select_button.connect("clicked", self._select_cb)
        hbox.pack_start(self._select_button, expand=False, fill=False)
        self.vbox.pack_start(hbox)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("%s:" % label))
        self._path = gutils.EntryWithHistory()
        self._path.set_width_chars(32)
        self._path.connect("activate", self._path_cb)
        hbox.pack_start(self._path, expand=True, fill=True)
        self._browse_button = gtk.Button(label="_Browse")
        self._browse_button.connect("clicked", self._browse_cb)
        hbox.pack_start(self._browse_button, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        self.show_all()
        self.ap_view.get_selection().unselect_all()
    def _selection_cb(self, selection=None):
        self._select_button.set_sensitive(selection.count_selected_rows())
    def _select_cb(self, button=None):
        ap = self.ap_view.get_selected_ap()
        self._path.set_text(ap[0])
    def _path_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def _browse_cb(self, button=None):
        dirname = gutils.ask_dir_name("gwsmhg: Browse for Directory", existing=True, parent=self)
        if dirname:
            self._path.set_text(utils.path_rel_home(dirname))
    def get_path(self):
        return os.path.expanduser(self._path.get_text())

class WSOpenDialog(PathSelectDialog, gutils.BusyIndicator, gutils.BusyIndicatorUser):
    def __init__(self, parent=None):
        gutils.BusyIndicator.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, self)
        PathSelectDialog.__init__(self, create_view=WSPathView,
            label="Workspace/Directory", parent=parent)

class RepoPathView(AliasPathView):
    def __init__(self):
        AliasPathView.__init__(self, SAVED_REPO_FILE_NAME)
    def _extant_path(self, path):
        if urlparse.urlparse(path).scheme:
            # for the time being treat all paths expressed as URLs as extant
            return True
        return AliasPathView._extant_path(self, path)
    def _same_paths(self, path1, path2):
        up1 = urlparse.urlparse(path1)
        if up1.scheme:
            up2 = urlparse.urlparse(path2)
            if up2.scheme:
                # compare normalized URLs for better confidence in result
                return up1.get_url() == up2.get_url()
            else:
                return False
        elif urlparse.urlparse(path2).scheme:
            return False
        else:
            return AliasPathView._same_paths(self, path1, path2)
    def _default_alias(self, path):
        up = urlparse.urlparse(path)
        if not up.scheme:
            return AliasPathView._default_alias(self, path)
        else:
            return os.path.basename(up.path)

class RepoSelectDialog(PathSelectDialog):
    def __init__(self, parent=None):
        PathSelectDialog.__init__(self, create_view=RepoPathView,
            label="Repository", parent=parent)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("As:"))
        self._target = gutils.EntryWithHistory()
        self._target.set_width_chars(32)
        self._target.connect("activate", self._target_cb)
        hbox.pack_start(self._target, expand=True, fill=True)
        self._default_button = gtk.Button(label="_Default")
        self._default_button.connect("clicked", self._default_cb)
        hbox.pack_start(self._default_button, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        self.show_all()
    def _target_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def _get_default_target(self):
        rawpath = self.get_path()
        urp = urlparse.urlparse(rawpath)
        if urp.scheme:
            path = urp.path
        else:
            path = rawpath
        return os.path.basename(path)
    def _default_cb(self, button=None):
        dt = self._get_default_target()
        self._target.set_text(dt)
    def get_target(self):
        target = self._target.get_text()
        if not target:
            target = self._get_default_target()
        return target

# Manage external editors

EDITORS_THAT_NEED_A_TERMINAL = ["vi", "joe"]
DEFAULT_EDITOR = "gedit"
DEFAULT_TERMINAL = "gnome-terminal"

for env in ['VISUAL', 'EDITOR']:
    try:
        ed = os.environ[env]
        if ed is not "":
            DEFAULT_EDITOR = ed
            break
    except KeyError:
        pass

for env in ['COLORTERM', 'TERM']:
    try:
        term = os.environ[env]
        if term is not "":
            DEFAULT_TERMINAL = term
            break
    except KeyError:
        pass

EDITOR_GLOB_FILE_NAME = os.sep.join([GSWMHG_D_NAME, "editors"])

editor_defs = []

def _read_editor_defs():
    global editor_defs
    editor_defs = []
    file = open(EDITOR_GLOB_FILE_NAME, 'r')
    for line in file.readlines():
        eqi = line.find('=')
        if eqi < 0:
            continue
        glob = line[:eqi].strip()
        edstr= line[eqi+1:].strip()
        editor_defs.append([glob, edstr])
    file.close()

def _write_editor_defs(edefs=editor_defs):
    file = open(EDITOR_GLOB_FILE_NAME, 'w')
    for edef in edefs:
        file.write('='.join(edef))
        file.write(os.linesep)
    file.close()

if os.path.exists(EDITOR_GLOB_FILE_NAME):
    _read_editor_defs()
else:
    _write_editor_defs([('*', DEFAULT_EDITOR)])

def assign_extern_editors(file_list):
    ed_assignments = {}
    for file in file_list:
        assigned = False
        for globs, edstr in editor_defs:
            for glob in globs.split(os.pathsep):
                if fnmatch.fnmatch(file, glob):
                    if ed_assignments.has_key(edstr):
                        ed_assignments[edstr].append(file)
                    else:
                        ed_assignments[edstr] = [file]
                    assigned = True
                    break
            if assigned:
                break
        if not assigned:
            if ed_assignments.has_key(DEFAULT_EDITOR):
                ed_assignments[DEFAULT_EDITOR].append(file)
            else:
                ed_assignments[DEFAULT_EDITOR] = [file]
    return ed_assignments

EDITOR_GLOB_MODEL_DESCR = \
[ ['globs', gobject.TYPE_STRING],
  ['editor', gobject.TYPE_STRING],
]

EDITOR_GLOB_TABLE_DESCR = \
[ [ ('enable-grid-lines', True), ('reorderable', True) ], # properties
  gtk.SELECTION_MULTIPLE, # selection mode
  [
    [ 'File Pattern(s)', [('expand', True), ], # column name and properties
      [ [ (gtk.CellRendererText, False, True), # renderer
          [ ('editable', True), ], # properties
          None, # cell_renderer_function
          [ ('text', table.model_col(EDITOR_GLOB_MODEL_DESCR, 'globs')), ] # attributes
        ],
      ]
    ],
    [ 'Editor Command', [('expand', True), ], # column
      [ [ (gtk.CellRendererText, False, True), # renderer
          [ ('editable', True), ], # properties
          None, # cell_renderer_function
          [ ('text', table.model_col(EDITOR_GLOB_MODEL_DESCR, 'editor')), ] # attributes
        ],
      ]
    ]
  ]
]

class EditorAllocationTable(table.Table):
    def __init__(self):
        table.Table.__init__(self, EDITOR_GLOB_MODEL_DESCR,
                             EDITOR_GLOB_TABLE_DESCR, (320, 160))
    def _fetch_contents(self):
        return editor_defs
    def apply_changes(self):
        _write_editor_defs(edefs=self.get_contents())
        _read_editor_defs()
        self.set_contents()

class EditorAllocationDialog(gtk.Dialog):
    def __init__(self, parent=None):
        gtk.Dialog.__init__(self, title='gwsmg: Editor Allocation', parent=parent,
                            flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        if parent:
            self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        else:
            self.set_icon_from_file(icons.app_icon_file)
            self.set_position(gtk.WIN_POS_MOUSE)
        self._table = EditorAllocationTable()
        self._buttons = gutils.ActionHButtonBox(self._table.action_groups.values())
        self.vbox.pack_start(self._table)
        self.vbox.pack_start(self._buttons, expand=False)
        self.connect("response", self._handle_response_cb)
        self.show_all()
        self._table.view.get_selection().unselect_all()
    def _handle_response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_OK:
            self._table.apply_changes()
        self.destroy()

