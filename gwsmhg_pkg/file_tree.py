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

import os, os.path, tempfile, gtk, gtk.gdk
from gwsmhg_pkg import ifce, utils, text_edit, cmd_result, diff, gutils, \
    tortoise, icons, ws_event, dialogue

IGNORED = 0
OTHER = 1
MODIFIED = 2

def _is_hidden_file(filename):
    return filename[0] == '.'

def _path_relative_to_dir(dirpath, askpath, validate_dir=True):
    if validate_dir and not os.path.isdir(dirpath):
        return None
    if dirpath == askpath:
        return os.curdir
    lcwd = len(dirpath)
    if len(askpath) <= lcwd + 1 or dirpath != askpath[0:lcwd] or askpath[lcwd] != os.sep:
        return None
    return askpath[lcwd + 1:]

def os_dir_contents(dirpath):
    hfiles = []
    files = []
    hdirs = []
    dirs = []
    for element in os.listdir(dirpath):
        if os.path.isdir(os.path.join(dirpath, element)):
            if _is_hidden_file(element):
                hdirs.append(element)
            else:
                dirs.append(element)
        elif _is_hidden_file(element):
            hfiles.append(element)
        else:
            files.append(element)
    return (hdirs, dirs, hfiles, files)

import gobject, gtk, pango

COLUMNS = (gobject.TYPE_STRING,
           gobject.TYPE_BOOLEAN,
           gobject.TYPE_INT,
           gobject.TYPE_STRING,
           gobject.TYPE_STRING,
           gobject.TYPE_STRING,
           gobject.TYPE_STRING)

NAME, IS_DIR, STYLE, FOREGROUND, ICON, STATUS, EXTRA_INFO = range(len(COLUMNS))

DEFAULT_STATUS_DECO_MAP = {
    None: (pango.STYLE_NORMAL, "black"),
    "-": (pango.STYLE_ITALIC, "red"),
    "?": (pango.STYLE_ITALIC, "grey"),
    "!": (pango.STYLE_NORMAL, "blue"),
}

DEFAULT_EXTRA_INFO_SEP = " <- "
DEFAULT_MODIFIED_DIR_STATUS = "!"
DEFAULT_NONEXISTANT_STATUS = "-"

class FileTreeRowData:
    def __init__(self, status_deco_map=DEFAULT_STATUS_DECO_MAP,
                 extra_info_sep=DEFAULT_EXTRA_INFO_SEP,
                 modified_dir_status=DEFAULT_MODIFIED_DIR_STATUS,
                 default_nonexistant_status=DEFAULT_NONEXISTANT_STATUS):
        self._status_deco_map = status_deco_map
        self._extra_info_sep = extra_info_sep
        self._default_nonexistant_status = default_nonexistant_status
        self.modified_dir_status = modified_dir_status
    def get_status_deco(self, status=None):
        if self._status_deco_map.has_key(status):
            return self._status_deco_map[status]
        else:
            return self._status_deco_map[None]
    def set_status_deco_map_entry(self, status, style=pango.STYLE_NORMAL, foreground="black"):
        self._status_deco_map[status] = (style, foreground)
    def del_status_deco_map_entry(self, status):
        if status is not None and self._status_deco_map.has_key(status):
            del self._status_deco_map[status]
    def set_status_deco_map(self, status_deco_map):
        if not status_deco_map.has_key(None):
            status_deco_map[None] = self._status_deco_map[None]
        self._status_deco_map = status_deco_map
    def generate_row_tuple(self, dirpath, name, isdir=None, status=None, extra_info=None):
        pathname = os.path.join(dirpath, name)
        exists = os.path.exists(pathname)
        row = range(len(COLUMNS))
        row[NAME] = name
        if isdir is None:
            if not exists:
                raise
            row[IS_DIR] = os.path.isdir(pathname)
        else:
            row[IS_DIR] = isdir
        if row[IS_DIR]:
            row[ICON] = gtk.STOCK_DIRECTORY
        else:
            # TODO: do file type icon
            row[ICON] = gtk.STOCK_FILE
        if not exists and not status:
            row[STATUS] = self._default_nonexistant_status
        else:
            row[STATUS] = status
        row[STYLE], row[FOREGROUND] = self.get_status_deco(row[STATUS])
        row[EXTRA_INFO] = extra_info
        return (exists, tuple(row))
    def formatted_file_name(self, store, tree_iter):
        assert store.iter_is_valid(tree_iter)
        name = store.get_value(tree_iter, NAME)
        xinfo = store.get_value(tree_iter, EXTRA_INFO)
        if xinfo:
            return self._extra_info_sep.join([name, xinfo])
        else:
            return name
    def format_file_name_crcb(self, column, cell_renderer, store, tree_iter):
        assert store.iter_is_valid(tree_iter)
        cell_renderer.set_property("text", self.formatted_file_name(store, tree_iter))

DEFAULT_ROW_DATA = FileTreeRowData(DEFAULT_STATUS_DECO_MAP, DEFAULT_EXTRA_INFO_SEP,
                                   DEFAULT_MODIFIED_DIR_STATUS, DEFAULT_NONEXISTANT_STATUS)

class RowDataUser:
    def __init__(self, row_data=DEFAULT_ROW_DATA):
        self._row_data = row_data
    def get_status_deco(self, status=None):
        if self._row_data._status_deco_map.has_key(status):
            return self._row_data._status_deco_map[status]
        else:
            return self._row_data._status_deco_map[None]
    def generate_row_tuple(self, dirpath, name, isdir=None, status=None, extra_info=None):
        pathname = os.path.join(dirpath, name)
        exists = os.path.exists(pathname)
        row = range(len(COLUMNS))
        row[NAME] = name
        if isdir is None:
            if not exists:
                raise
            row[IS_DIR] = os.path.isdir(pathname)
        else:
            row[IS_DIR] = isdir
        if row[IS_DIR]:
            row[ICON] = gtk.STOCK_DIRECTORY
        else:
            # TODO: do file type icon
            row[ICON] = gtk.STOCK_FILE
        if not exists and not status:
            row[STATUS] = self._row_data._default_nonexistant_status
        else:
            row[STATUS] = status
        row[STYLE], row[FOREGROUND] = self.get_status_deco(row[STATUS])
        row[EXTRA_INFO] = extra_info
        return (exists, tuple(row))
    def formatted_file_name(self, store, tree_iter):
        assert store.iter_is_valid(tree_iter)
        name = store.get_value(tree_iter, NAME)
        xinfo = store.get_value(tree_iter, EXTRA_INFO)
        if xinfo:
            return self._row_data._extra_info_sep.join([name, xinfo])
        else:
            return name
    def format_file_name_crcb(self, column, cell_renderer, store, tree_iter):
        assert store.iter_is_valid(tree_iter)
        cell_renderer.set_property("text", self.formatted_file_name(store, tree_iter))

class FileTreeStore(gtk.TreeStore, RowDataUser):
    def __init__(self, show_hidden=False, row_data=DEFAULT_ROW_DATA):
        apply(gtk.TreeStore.__init__, (self,) + COLUMNS)
        RowDataUser.__init__(self, row_data)
        self.show_hidden_action = gtk.ToggleAction("show_hidden_files", "Show Hidden Files",
                                                   "Show/hide files beginning with \".\"", None)
        self.show_hidden_action.set_active(show_hidden)
        self.show_hidden_action.connect("toggled", self._toggle_show_hidden_cb)
        self.show_hidden_action.set_menu_item_type(gtk.CheckMenuItem)
        self.show_hidden_action.set_tool_item_type(gtk.ToggleToolButton)
        # Keep track of nonexistant displayable files so that the "expanded" state set by the
        # user isn't disrupted during multi stage updates
        self._displayable_nonexistants = []
    def _get_data_for_status(self, status):
        return self.get_status_deco(status)
    def _display_this_nonexistant(self, fsobj_iter):
        assert self.iter_is_valid(fsobj_iter)
        return self.fs_path(fsobj_iter) in self._displayable_nonexistants
    def _add_displayable_nonexistant(self, fsobj_iter):
        assert self.iter_is_valid(fsobj_iter)
        fsobj_fspath = self.fs_path(fsobj_iter)
        if fsobj_fspath not in self._displayable_nonexistants:
            self._displayable_nonexistants.append(fsobj_fspath)
    def _del_displayable_nonexistant(self, fsobj_iter):
        assert self.iter_is_valid(fsobj_iter)
        fsobj_fspath = self.get_path(fsobj_iter)
        if fsobj_fspath in self._displayable_nonexistants:
            del self._displayable_nonexistants[self._displayable_nonexistants.index(fsobj_fspath)]
    def del_files_from_displayable_nonexistants(self, file_list=[]):
        if file_list:
            for file_x in file_list:
                if file_x in self._displayable_nonexistants:
                    del self._displayable_nonexistants[self._displayable_nonexistants.index(file_x)]
        else:
            self._displayable_nonexistants = []
    def _generate_row_tuple(self, dirpath, name, isdir=None, status=None, extra_info=None):
        return self.generate_row_tuple(dirpath, name, isdir, status, extra_info)
    def _update_iter_row_tuple(self, fsobj_iter, to_tuple):
        assert self.iter_is_valid(fsobj_iter)
        for index in [STYLE, FOREGROUND, STATUS, EXTRA_INFO]:
            self.set_value(fsobj_iter, index, to_tuple[index])
    def _toggle_show_hidden_cb(self, toggleaction):
        self.update()
    def fs_path(self, fsobj_iter):
        if fsobj_iter is None:
            return None
        assert self.iter_is_valid(fsobj_iter)
        parent_iter = self.iter_parent(fsobj_iter)
        name = self.get_value(fsobj_iter, NAME)
        if parent_iter is None:
            return name
        else:
            if name is None:
                return "name was none"
            assert self.iter_is_valid(parent_iter)
            return os.path.join(self.fs_path(parent_iter), name)
    def fs_path_list(self, iter_list):
        return [self.fs_path(fsobj_iter) for fsobj_iter in iter_list]
    def _find_dir(self, ldirpath, dir_iter):
        while dir_iter != None:
            assert self.iter_is_valid(dir_iter)
            if not self.get_value(dir_iter, IS_DIR):
                return None
            if self.get_value(dir_iter, NAME) == ldirpath[0]:
                if len(ldirpath) == 1:
                    return dir_iter
                return self._find_dir(ldirpath[1:], self.iter_children(dir_iter))
            dir_iter = self.iter_next(dir_iter)
        return dir_iter
    def find_dir(self, dirpath):
        dir_iter = self.get_iter_first()
        ldirpath = dirpath.split(os.sep)
        return self._find_dir(ldirpath, dir_iter)
    def _find_file_in_dir(self, fname, dir_iter):
        if dir_iter is None:
            file_iter = self.get_iter_first()
        else:
            assert self.iter_is_valid(dir_iter)
            file_iter = self.iter_children(dir_iter)
        while file_iter != None:
            assert self.iter_is_valid(file_iter)
            if not self.get_value(file_iter, IS_DIR) and self.get_value(file_iter, NAME) == fname:
                break
            file_iter = self.iter_next(file_iter)
        return file_iter
    def find_file(self, filepath):
        dirpath, fname = os.path.split(filepath)
        if dirpath == "":
            return self._find_file_in_dir(fname, None)
        dir_iter = self.find_dir(dirpath)
        if dir_iter is None:
            return None
        assert self.iter_is_valid(dir_iter)
        return self._find_file_in_dir(fname, dir_iter)
    def _get_file_paths(self, fsobj_iter, path_list):
        while fsobj_iter != None:
            assert self.iter_is_valid(fsobj_iter)
            if not self.get_value(fsobj_iter, IS_DIR):
                path_list.append(self.fs_path(fsobj_iter))
            else:
                child_iter = self.iter_children(fsobj_iter)
                if child_iter != None:
                    assert self.iter_is_valid(child_iter)
                    self._get_file_paths(child_iter, path_list)
            fsobj_iter = self.iter_next(fsobj_iter)
    def get_file_paths(self):
        path_list = []
        self._get_file_paths(self.get_iter_first(), path_list)
        return path_list
    def _recursive_remove(self, fsobj_iter):
        assert self.iter_is_valid(fsobj_iter)
        child_iter = self.iter_children(fsobj_iter)
        if child_iter != None:
            assert self.iter_is_valid(child_iter)
            self._del_displayable_nonexistant(child_iter)
            while self._recursive_remove(child_iter):
                self._del_displayable_nonexistant(child_iter)
        self._del_displayable_nonexistant(fsobj_iter)
        return self.remove(fsobj_iter)
    def _remove_place_holder(self, dir_iter):
        assert self.iter_is_valid(dir_iter)
        child_iter = self.iter_children(dir_iter)
        if child_iter and self.get_value(child_iter, NAME) is None:
            self.remove(child_iter)
    def _insert_place_holder(self, dir_iter):
        assert self.iter_is_valid(dir_iter)
        self.append(dir_iter)
    def _insert_place_holder_if_needed(self, dir_iter):
        assert self.iter_is_valid(dir_iter)
        if self.iter_n_children(dir_iter) == 0:
            self._insert_place_holder(dir_iter)
    def _find_or_insert_dir(self, parent_iter, row_tuple):
        if parent_iter is None:
            dir_iter = self.get_iter_first()
        else:
            assert self.iter_is_valid(parent_iter)
            self._remove_place_holder(parent_iter)
            dir_iter = self.iter_children(parent_iter)
        if dir_iter is None:
            return (False, self.append(parent_iter, row_tuple))
        assert self.iter_is_valid(dir_iter)
        while self.get_value(dir_iter, IS_DIR) and self.get_value(dir_iter, NAME) < row_tuple[NAME]:
            next = self.iter_next(dir_iter)
            if next is None or not self.get_value(next, IS_DIR):
                return (False, self.insert_after(parent_iter, dir_iter, row_tuple))
            dir_iter = next
            assert self.iter_is_valid(dir_iter)
        assert self.iter_is_valid(dir_iter)
        if self.get_value(dir_iter, NAME) == row_tuple[NAME]:
            self._update_iter_row_tuple(dir_iter, row_tuple)
            return (True, dir_iter)
        return (False, self.insert_before(parent_iter, dir_iter, row_tuple))
    def find_or_insert_dir(self, dirpath, status=None, extra_info=None):
        if dirpath == "":
            return (False, None)
        dir_iter = None
        parent_dir_path = ""
        for name in dirpath.split(os.sep):
            exists, row_tuple = self._generate_row_tuple(parent_dir_path, name, isdir=True, status=status, extra_info=extra_info)
            found, dir_iter = self._find_or_insert_dir(dir_iter, row_tuple)
            assert self.iter_is_valid(dir_iter)
            if not exists:
                self._add_displayable_nonexistant(dir_iter)
            parent_dir_path = os.path.join(parent_dir_path, name)
        assert self.iter_is_valid(dir_iter)
        self._insert_place_holder_if_needed(dir_iter)
        return (found, dir_iter)
    def _find_or_insert_file(self, parent_iter, row_tuple):
        if parent_iter is None:
            file_iter = self.get_iter_first()
        else:
            assert self.iter_is_valid(parent_iter)
            self._remove_place_holder(parent_iter)
            file_iter = self.iter_children(parent_iter)
        if file_iter is None:
            return (False, self.append(parent_iter, row_tuple))
        assert self.iter_is_valid(file_iter)
        while self.get_value(file_iter, IS_DIR):
            next = self.iter_next(file_iter)
            if next is None:
                return (False, self.insert_after(parent_iter, file_iter, row_tuple))
            file_iter = next
            assert self.iter_is_valid(file_iter)
        assert self.iter_is_valid(file_iter)
        while self.get_value(file_iter, NAME) < row_tuple[NAME]:
            next = self.iter_next(file_iter)
            if next is None:
                return (False, self.insert_after(parent_iter, file_iter, row_tuple))
            file_iter = next
            assert self.iter_is_valid(file_iter)
        assert self.iter_is_valid(file_iter)
        if self.get_value(file_iter, NAME) == row_tuple[NAME]:
            self._update_iter_row_tuple(file_iter, row_tuple)
            return (True, file_iter)
        return (False, self.insert_before(parent_iter, file_iter, row_tuple))
    def find_or_insert_file(self, filepath, file_status=None, dir_status=None, extra_info=None):
        dirpath, name = os.path.split(filepath)
        exists, row_tuple = self._generate_row_tuple(dirpath, name, isdir=False, status=file_status, extra_info=extra_info)
        dummy, dir_iter = self.find_or_insert_dir(dirpath, status=dir_status)
        #assert self.iter_is_valid(dir_iter), "fts:find_or_insert_file: iter is INVALID"
        found, file_iter = self._find_or_insert_file(dir_iter, row_tuple)
        assert self.iter_is_valid(file_iter)
        if not exists:
            self._add_displayable_nonexistant(file_iter)
        return (found, file_iter)
    def delete_file(self, filepath, leave_extant_dir_parts=True):
        file_iter = self.find_file(filepath)
        if file_iter is None:
            return
        assert self.iter_is_valid(file_iter)
        parent_iter = self.iter_parent(file_iter)
        self._recursive_remove(file_iter)
        while parent_iter is not None:
            assert self.iter_is_valid(parent_iter)
            parent_iter = self.iter_parent(parent_iter)
            if parent_iter:
                assert self.iter_is_valid(parent_iter)
            child_iter = self.iter_children(parent_iter)
            if child_iter is None:
                if leave_extant_dir_parts and os.path.exists(self.fs_path(parent_iter)):
                    self._insert_place_holder(parent_iter)
                    break
                else:
                    self._del_displayable_nonexistant(parent_iter)
                    parent_iter_copy = parent_iter
                    parent_iter = self.iter_parent(parent_iter_copy)
                    self.remove(parent_iter_copy)
            else:
                assert self.iter_is_valid(child_iter)
                break
    def repopulate(self):
        assert 0, "repopulate() must be defined in descendants"
    def update(self, fsobj_iter=None):
        assert 0, "repopulate() must be defined in descendants"
    def on_row_expanded_cb(self, view, dir_iter, dummy):
        assert self.iter_is_valid(dir_iter)
        if self.iter_n_children(dir_iter) > 1:
            self._remove_place_holder(dir_iter)
    def on_row_collapsed_cb(self, view, dir_iter, dummy):
        assert self.iter_is_valid(dir_iter)
        self._insert_place_holder_if_needed(dir_iter)

class CwdFileTreeStore(FileTreeStore):
    def __init__(self, show_hidden=False, row_data=DEFAULT_ROW_DATA):
        FileTreeStore.__init__(self, show_hidden=show_hidden, row_data=row_data)
        # This will be automatically set when the first row is expanded
        self.view = None
        self.repopulate()
    def _row_expanded(self, dir_iter):
        assert self.iter_is_valid(dir_iter)
        # if view isn't set then assume that we aren't connexted to a view
        # so the row can't be expanded
        return self.view and self.view.row_expanded(self.get_path(dir_iter))
    def _dir_contents(self, dirpath):
        hdirs, dirs, hfiles, files = os_dir_contents(dirpath)
        if self.show_hidden_action.get_active():
            return (hdirs + dirs, hfiles + files)
        else:
            return (dirs, files)
    def _populate(self, dirpath, parent_iter):
        dirs, files = self._dir_contents(dirpath)
        dirs.sort()
        for dirname in dirs:
            dummy, row_tuple = self._generate_row_tuple(dirpath, dirname, isdir=True)
            dir_iter = self.append(parent_iter, row_tuple)
            assert self.iter_is_valid(dir_iter)
            self._insert_place_holder(dir_iter)
        files.sort()
        for filename in files:
            dummy, row_tuple = self._generate_row_tuple(dirpath, filename, isdir=False)
            dummy = self.append(parent_iter, row_tuple)
        if parent_iter is not None:
            assert self.iter_is_valid(parent_iter)
            self._insert_place_holder_if_needed(parent_iter)
    def _update_dir(self, dirpath, parent_iter=None):
        if not os.path.exists(dirpath):
            return
        if parent_iter is None:
            child_iter = self.get_iter_first()
        else:
            assert self.iter_is_valid(parent_iter)
            child_iter = self.iter_children(parent_iter)
            if child_iter:
                assert self.iter_is_valid(child_iter)
                if self.get_value(child_iter, NAME) is None:
                    child_iter = self.iter_next(child_iter)
        if child_iter is None:
            self._populate(dirpath, parent_iter)
            return
        assert self.iter_is_valid(child_iter)
        dirs, files = self._dir_contents(dirpath)
        dirs.sort()
        files.sort()
        dead_entries = []
        for dirx in dirs:
            dummy, row_tuple = self._generate_row_tuple(dirpath, dirx, isdir=True)
            while (child_iter is not None) and self.get_value(child_iter, IS_DIR) and (self.get_value(child_iter, NAME) < dirx):
                if not self._display_this_nonexistant(child_iter):
                    dead_entries.append(child_iter)
                child_iter = self.iter_next(child_iter)
                if child_iter:
                    assert self.iter_is_valid(child_iter)
            if child_iter is None:
                dir_iter = self.append(parent_iter, row_tuple)
                assert self.iter_is_valid(dir_iter)
                self._insert_place_holder(dir_iter)
                continue
            name = self.get_value(child_iter, NAME)
            assert self.iter_is_valid(child_iter)
            if (not self.get_value(child_iter, IS_DIR)) or (name > dirx):
                dir_iter = self.insert_before(parent_iter, child_iter, row_tuple)
                assert self.iter_is_valid(dir_iter)
                self._insert_place_holder(dir_iter)
                continue
            self._update_iter_row_tuple(child_iter, row_tuple)
            if self._row_expanded(child_iter):
                self._update_dir(os.path.join(dirpath, name), child_iter)
            child_iter = self.iter_next(child_iter)
            if child_iter:
                assert self.iter_is_valid(child_iter)
        if child_iter:
            assert self.iter_is_valid(child_iter)
        while (child_iter is not None) and self.get_value(child_iter, IS_DIR):
            if not self._display_this_nonexistant(child_iter):
                dead_entries.append(child_iter)
            child_iter = self.iter_next(child_iter)
            if child_iter:
                assert self.iter_is_valid(child_iter)
        for filex in files:
            dummy, row_tuple = self._generate_row_tuple(dirpath, filex, isdir=False)
            while (child_iter is not None) and (self.get_value(child_iter, NAME) < filex):
                if not self._display_this_nonexistant(child_iter):
                    dead_entries.append(child_iter)
                child_iter = self.iter_next(child_iter)
                if child_iter:
                    assert self.iter_is_valid(child_iter)
            if child_iter is None:
                dummy = self.append(parent_iter, row_tuple)
                continue
            assert self.iter_is_valid(child_iter)
            if self.get_value(child_iter, NAME) > filex:
                dummy = self.insert_before(parent_iter, child_iter, row_tuple)
                continue
            self._update_iter_row_tuple(child_iter, row_tuple)
            child_iter = self.iter_next(child_iter)
            if child_iter:
                assert self.iter_is_valid(child_iter)
        while child_iter is not None:
            if not self._display_this_nonexistant(child_iter):
                dead_entries.append(child_iter)
            child_iter = self.iter_next(child_iter)
            if child_iter:
                assert self.iter_is_valid(child_iter)
        for dead_entry in dead_entries:
            self._recursive_remove(dead_entry)
        if parent_iter is not None:
            assert self.iter_is_valid(parent_iter)
            self._insert_place_holder_if_needed(parent_iter)
    def repopulate(self):
        self.clear()
        self._populate(os.curdir, self.get_iter_first())
    def update(self, fsobj_iter=None):
        if fsobj_iter is None:
            self._update_dir(os.curdir, None)
        else:
            assert self.iter_is_valid(fsobj_iter)
            filepath = self.fs_path(fsobj_iter)
            if not os.path.exists(filepath):
                if not self._display_this_nonexistant(fsobj_iter):
                    self._recursive_remove(fsobj_iter)
            elif os.path.isdir(filepath):
                self._update_dir(filepath, fsobj_iter)
                if self.iter_n_children(fsobj_iter) > 1:
                    self._remove_place_holder(fsobj_iter)
    def on_row_expanded_cb(self, view, dir_iter, dummy):
        assert self.iter_is_valid(dir_iter)
        self.view = view
        self._update_dir(self.fs_path(dir_iter), dir_iter)
        FileTreeStore.on_row_expanded_cb(self, view, dir_iter, dummy)

from gwsmhg_pkg import actions

class _ViewWithActionGroups(gtk.TreeView, dialogue.BusyIndicatorUser,
                            actions.AGandUIManager):
    def __init__(self, busy_indicator, model=None):
        gtk.TreeView.__init__(self, model)
        dialogue.BusyIndicatorUser.__init__(self, busy_indicator)
        actions.AGandUIManager.__init__(self, self.get_selection())
        self.add_conditional_action(actions.ON_REPO_INDEP_SELN_INDEP, model.show_hidden_action)
        self.connect('button_press_event', self._handle_button_press_cb)
    def _handle_button_press_cb(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 3:
                menu = self.ui_manager.get_widget('/files_popup')
                menu.popup(None, None, None, event.button, event.time)
                return True
            elif event.button == 2:
                self.get_selection().unselect_all()
                return True
        return False

UI_DESCR = \
'''
<ui>
  <popup name="files_popup">
    <placeholder name="selection_indifferent"/>
    <separator/>
    <placeholder name="selection"/>
    <separator/>
    <placeholder name="selection_not_patched"/>
    <separator/>
    <placeholder name="unique_selection"/>
    <separator/>
    <placeholder name="no_selection"/>
    <separator/>
    <placeholder name="no_selection_not_patched"/>
    <separator/>
  </popup>
  <toolbar name="files_housekeeping_toolbar">
    <toolitem action="refresh_files"/>
    <separator/>
    <toolitem action="show_hidden_files"/>
  </toolbar>
  <toolbar name="files_refresh_toolbar">
    <toolitem action="refresh_files"/>
  </toolbar>
</ui>
'''

_KEYVAL_c = gtk.gdk.keyval_from_name('c')
_KEYVAL_C = gtk.gdk.keyval_from_name('C')
_KEYVAL_ESCAPE = gtk.gdk.keyval_from_name('Escape')

class FileTreeView(_ViewWithActionGroups):
    def __init__(self, busy_indicator, model=None, auto_refresh=False,
                 show_hidden=False, show_status=False):
        if model is None:
            model = FileTreeStore(show_hidden=show_hidden)
        _ViewWithActionGroups.__init__(self, busy_indicator, model=model)
        self._refresh_interval = 60000 # milliseconds
        self._create_column(show_status)
        self.connect("row-expanded", model.on_row_expanded_cb)
        self.connect("row-collapsed", model.on_row_collapsed_cb)
        self.auto_refresh_action = gtk.ToggleAction("auto_refresh_files", "Auto Refresh",
                                                   "Automatically/periodically refresh file display", None)
        self.auto_refresh_action.set_active(auto_refresh)
        self.auto_refresh_action.connect("toggled", self._toggle_auto_refresh_cb)
        self.auto_refresh_action.set_menu_item_type(gtk.CheckMenuItem)
        self.auto_refresh_action.set_tool_item_type(gtk.ToggleToolButton)
        self.add_conditional_action(actions.ON_REPO_INDEP_SELN_INDEP, self.auto_refresh_action)
        self.add_conditional_actions(actions.ON_REPO_INDEP_SELN_INDEP,
            [
                ("refresh_files", gtk.STOCK_REFRESH, "_Refresh", None,
                 "Refresh/update the file tree display", self.update_tree),
            ])
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(UI_DESCR)
        self.connect("key_press_event", self._key_press_cb)
        self._toggle_auto_refresh_cb()
    def _do_auto_refresh(self):
        if self.auto_refresh_action.get_active():
            self.update_tree()
            return True
        else:
            return False
    def _toggle_auto_refresh_cb(self, action=None):
        if self.auto_refresh_action.get_active():
            gobject.timeout_add(self._refresh_interval, self._do_auto_refresh)
    def _create_column(self, show_status):
        tvcolumn = gtk.TreeViewColumn(None)
        tvcolumn.set_expand(False)
        icon_cell = gtk.CellRendererPixbuf()
        tvcolumn.pack_start(icon_cell, False)
        tvcolumn.set_attributes(icon_cell, stock_id=ICON)
        if show_status:
            status_cell = gtk.CellRendererText()
            tvcolumn.pack_start(status_cell, expand=False)
            tvcolumn.set_attributes(status_cell, text=STATUS, style=STYLE, foreground=FOREGROUND)
        text_cell = gtk.CellRendererText()
        tvcolumn.pack_start(text_cell, expand=False)
        tvcolumn.set_attributes(text_cell, style=STYLE, foreground=FOREGROUND)
        tvcolumn.set_cell_data_func(text_cell, self.get_model()._row_data.format_file_name_crcb)
        oldcol = self.get_column(0)
        if oldcol:
            self.remove_column(oldcol)
        self.append_column(tvcolumn)
    def set_refresh_interval(self, refresh_interval):
        self._refresh_interval = refresh_interval
    def set_show_hidden(self, show_hidden):
        model = self.get_model()
        if model.set_show_hidden(show_hidden):
            model.update()
    def get_selected_files(self):
        store, selection = self.get_selection().get_selected_rows()
        return [store.fs_path(store.get_iter(x)) for x in selection]
    def add_selected_files_to_clipboard(self, clipboard=None):
        if not clipboard:
            clipboard = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)
        sel = utils.file_list_to_string(self.get_selected_files()).strip()
        clipboard.set_text(sel)
    def _key_press_cb(self, widget, event):
        if event.state == gtk.gdk.CONTROL_MASK:
            if event.keyval in [_KEYVAL_c, _KEYVAL_C]:
                self.add_selected_files_to_clipboard()
                return True
        elif event.keyval == _KEYVAL_ESCAPE:
            self.get_selection().unselect_all()
            return True
        return False
    def repopulate_tree(self):
        self.show_busy()
        self.get_model().repopulate()
        self.unshow_busy()
    def update_tree(self, action=None):
        self.show_busy()
        self.get_model().update()
        self.unshow_busy()

CWD_UI_DESCR = \
'''
<ui>
  <menubar name="files_menubar">
    <menu name="files_menu" action="menu_files">
      <menuitem action="new_file"/>
    </menu>
  </menubar>
  <popup name="files_popup">
    <placeholder name="selection_indifferent"/>
    <separator/>
    <placeholder name="selection">
      <menuitem action="edit_files"/>
      <menuitem action="delete_files"/>
    </placeholder>
    <separator/>
    <placeholder name="selection_not_patched"/>
    <separator/>
    <placeholder name="unique_selection"/>
    <separator/>
    <placeholder name="no_selection"/>
    <separator/>
    <placeholder name="no_selection_not_patched"/>
    <separator/>
    <menuitem action="show_hidden_files"/>
  </popup>
</ui>
'''

class CwdFileTreeView(FileTreeView):
    def __init__(self, busy_indicator, model=None, auto_refresh=False,
                 show_hidden=False, show_status=False):
        if not model:
            model = CwdFileTreeStore(show_hidden=show_hidden)
        FileTreeView.__init__(self, busy_indicator=busy_indicator, model=model,
            auto_refresh=auto_refresh, show_status=show_status)
        self.add_conditional_actions(actions.ON_REPO_INDEP_SELN,
            [
                ("edit_files", gtk.STOCK_EDIT, "_Edit", None,
                 "Edit the selected file(s)", self.edit_selected_files_acb),
                ("delete_files", gtk.STOCK_DELETE, "_Delete", None,
                 "Delete the selected file(s) from the repository", self.delete_selected_files_acb),
            ])
        self.add_conditional_actions(actions.ON_REPO_INDEP_SELN_INDEP,
            [
                ("new_file", gtk.STOCK_NEW, "_New", None,
                 "Create a new file and open for editing", self.create_new_file_acb),
            ])
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(CWD_UI_DESCR)
    def _confirm_list_action(self, filelist, question):
        msg = os.linesep.join(filelist + [os.linesep, question])
        dialog = gtk.MessageDialog(parent=dialogue.main_window,
                                   flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                                   type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_OK_CANCEL,
                                   message_format=msg)
        response = dialog.run()
        dialog.destroy()
        return response == gtk.RESPONSE_OK
    def _edit_named_files_extern(self, file_list):
        text_edit.edit_files_extern(file_list)
    def edit_selected_files_acb(self, menu_item):
        self._edit_named_files_extern(self.get_selected_files())
    def create_new_file(self, new_file_name, open_for_edit=False):
        model = self.get_model()
        self.show_busy()
        result = utils.create_file(new_file_name, ifce.log)
        self.unshow_busy()
        self.update_tree()
        dialogue.report_any_problems(result)
        if open_for_edit:
            self._edit_named_files_extern([new_file_name])
        return result
    def create_new_file_acb(self, menu_item):
        dialog = gtk.FileChooserDialog("New File", dialogue.main_window,
                                       gtk.FILE_CHOOSER_ACTION_SAVE,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_position(gtk.WIN_POS_MOUSE)
        selected_files = self.get_selected_files()
        if len(selected_files) == 1 and os.path.isdir(selected_files[0]):
            dialog.set_current_folder(os.path.abspath(selected_files[0]))
        else:
            dialog.set_current_folder(os.getcwd())
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            new_file_name = dialog.get_filename()
            dialog.destroy()
            self.create_new_file(new_file_name, True)
        else:
            dialog.destroy()
    def delete_files(self, file_list):
        if ifce.log:
            ifce.log.start_cmd("Deleting: %s" % " ".join(file_list))
        serr = ""
        for filename in file_list:
            try:
                os.remove(filename)
                if ifce.log:
                    ifce.log.append_stdout(("Deleted: %s" + os.linesep) % filename)
            except os.error, value:
                errmsg = ("%s: %s" + os.linesep) % (value[1], filename)
                serr += errmsg
                if ifce.log:
                    ifce.log.append_stderr(errmsg)
        if ifce.log:
            ifce.log.end_cmd()
        if serr:
            return (cmd_result.ERROR, "", serr)
        return (cmd_result.OK, "", "")
    def _delete_named_files(self, file_list, ask=True):
        if not ask or self._confirm_list_action(file_list, "About to be deleted. OK?"):
            model = self.get_model()
            self.show_busy()
            result = self.delete_files(file_list)
            self.unshow_busy()
            self.update_tree()
            dialogue.report_any_problems(result)
    def delete_selected_files_acb(self, menu_item):
        self._delete_named_files(self.get_selected_files())

class ScmCwdFileTreeStore(CwdFileTreeStore):
    def __init__(self, show_hidden=False):
        row_data = apply(FileTreeRowData, ifce.SCM.get_status_row_data())
        CwdFileTreeStore.__init__(self, show_hidden=show_hidden, row_data=row_data)
        self._update_statuses()
    def _update_statuses(self, fspath_list=[]):
        res, dflists, dummy = ifce.SCM.get_file_status_lists(fspath_list)
        if res == 0:
            if self.show_hidden_action.get_active():
                for dfile, status, dummy in dflists[IGNORED]:
                    self.find_or_insert_file(dfile, file_status=status)
            for dfile, status, dummy in dflists[OTHER]:
                self.find_or_insert_file(dfile, file_status=status, dir_status=status)
            for dfile, status, extra_info in dflists[MODIFIED]:
                self.find_or_insert_file(dfile, file_status=status,
                                         dir_status=self._row_data.modified_dir_status,
                                         extra_info=extra_info)
            if not self.show_hidden_action.get_active():
                for dfile, status, dummy in dflists[IGNORED]:
                    self.delete_file(dfile)
    def _update_dir(self, dirpath, parent_iter=None):
        CwdFileTreeStore._update_dir(self, dirpath, parent_iter)
        self._update_statuses([dirpath])
    def repopulate(self):
        CwdFileTreeStore.repopulate(self)
        self._update_statuses()

SCM_CWD_UI_DESCR = \
'''
<ui>
  <menubar name="files_menubar">
    <menu name="files_menu" action="menu_files">
      <menuitem action="new_file"/>
      <menuitem action="scm_add_files_all"/>
      <menuitem action="refresh_files"/>
    </menu>
  </menubar>
  <popup name="files_popup">
    <placeholder name="selection_indifferent"/>
    <placeholder name="selection">
      <menuitem action="edit_files"/>
      <menuitem action="delete_files"/>
      <menuitem action="scm_add_files"/>
      <menuitem action="scm_remove_files"/>
      <menuitem action="scm_copy_files_selection"/>
      <menuitem action="scm_diff_files_selection"/>
      <menuitem action="scm_move_files_selection"/>
    </placeholder>
    <placeholder name="selection_not_patched">
      <menuitem action="scm_revert_files_selection"/>
      <menuitem action="scm_commit_files_selection"/>
    </placeholder>
    <placeholder name="unique_selection">
      <menuitem action="scm_rename_file"/>
    </placeholder>
    <placeholder name="no_selection">
      <menuitem action="scm_diff_files_all"/>
    </placeholder>
    <placeholder name="no_selection_not_patched">
      <menuitem action="scm_revert_files_all"/>
      <menuitem action="scm_commit_files_all"/>
    </placeholder>
    <separator/>
    <menuitem action="show_hidden_files"/>
  </popup>
</ui>
'''

class ScmCwdFileTreeView(CwdFileTreeView):
    def __init__(self, busy_indicator, auto_refresh=False, show_hidden=False):
        model = ScmCwdFileTreeStore(show_hidden=show_hidden)
        CwdFileTreeView.__init__(self, busy_indicator=busy_indicator, model=model,
            auto_refresh=auto_refresh, show_status=True)
        self.add_notification_cb(ws_event.CHECKOUT|ws_event.FILE_CHANGES, self.update_after_commit),
        self.add_notification_cb(ws_event.CHANGE_WD, self.update_for_chdir),
        self.add_conditional_actions(actions.ON_IN_REPO_SELN,
            [
                ("scm_remove_files", gtk.STOCK_REMOVE, "_Remove", None,
                 "Remove the selected file(s) from the repository", self.remove_selected_files_acb),
                ("scm_add_files", gtk.STOCK_ADD, "_Add", None,
                 "Add the selected file(s) to the repository", self.add_selected_files_to_repo_acb),
                ("scm_copy_files_selection", gtk.STOCK_COPY, "_Copy", None,
                 "Copy the selected file(s)", self.copy_selected_files_acb),
                ("scm_diff_files_selection", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for selected file(s)", self.diff_selected_files_acb),
                ("scm_move_files_selection", icons.STOCK_RENAME, "_Move/Rename", None,
                 "Move the selected file(s)", self.move_selected_files_acb),
            ])
        self.add_conditional_actions(actions.ON_IN_REPO_NOT_PMIC_SELN,
            [
                ("scm_revert_files_selection", gtk.STOCK_UNDO, "Rever_t", None,
                 "Revert changes in the selected file(s)", self.revert_selected_files_acb),
                ("scm_commit_files_selection", icons.STOCK_COMMIT, "_Commit", None,
                 "Commit changes for selected file(s)", self.commit_selected_files_acb),
            ])
        self.add_conditional_actions(actions.ON_IN_REPO_UNIQUE_SELN,
           [
                ("scm_rename_file", icons.STOCK_RENAME, "Re_name/Move", None,
                 "Rename/move the selected file", self.move_selected_files_acb),
            ])
        self.add_conditional_actions(actions.ON_IN_REPO_NO_SELN,
            [
                ("scm_add_files_all", gtk.STOCK_ADD, "_Add all", None,
                 "Add all files to the repository", self.add_all_files_to_repo_acb),
                ("scm_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self.diff_selected_files_acb),
            ])
        self.add_conditional_actions(actions.ON_IN_REPO_NOT_PMIC_NO_SELN,
            [
                ("scm_revert_files_all", gtk.STOCK_UNDO, "Rever_t", None,
                 "Revert all changes in working directory", self.revert_all_files_acb),
                ("scm_commit_files_all", icons.STOCK_COMMIT, "_Commit", None,
                 "Commit all changes", self.commit_all_changes_acb),
            ])
        self.add_conditional_actions(actions.ON_REPO_INDEP_SELN_INDEP,
            [
                ("menu_files", None, "_Files"),
            ])
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(SCM_CWD_UI_DESCR)
        if tortoise.is_available:
            self.add_conditional_action(actions.ON_REPO_INDEP_SELN_INDEP, tortoise.file_menu)
            for condition in tortoise.SELN_CONDITIONS:
                action_list = []
                for action in tortoise.file_group_partial_actions[condition]:
                    action_list.append(action + tuple([self._tortoise_tool_acb]))
                self.add_conditional_actions(condition, action_list)
            self.ui_manager.add_ui_from_string(tortoise.FILES_UI_DESCR)
        self._event_cond_change_cb()
    def update_for_chdir(self):
        self.show_busy()
        self.repopulate_tree()
        self.unshow_busy()
    def _tortoise_tool_acb(self, action=None):
        tortoise.run_tool_for_files(action, self.get_selected_files())
    def new_file(self, new_file_name):
        result = utils.create_file(new_file_name, ifce.log)
        if not result[0]:
            res, sout, serr = ifce.SCM.do_add_files([new_file_name])
            if res:
                return (res, sout, serr)
        return result
    def delete_files(self, file_list):
        return ifce.SCM.do_delete_files(file_list)
    def get_scm_name(self):
        return ifce.SCM.name
    def _check_if_force(self, result):
        if (result[0] & cmd_result.SUGGEST_FORCE) == cmd_result.SUGGEST_FORCE:
            dialog = gtk.MessageDialog(parent=dialogue.main_window,
                                   flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                                   type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_NONE,
                                   message_format=result[1]+result[2])
            dialog.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, "Force", gtk.RESPONSE_OK)
            response = dialog.run()
            dialog.destroy()
            return response == gtk.RESPONSE_OK
        else:
            return False
    def _remove_named_files(self, file_list, ask=True):
        if not ask or self._confirm_list_action(file_list, "About to be removed. OK?"):
            model = self.get_model()
            self.show_busy()
            result = ifce.SCM.do_remove_files(file_list)
            self.unshow_busy()
            if self._check_if_force(result):
                result = ifce.SCM.do_remove_files(file_list, force=True)
            self.update_tree()
            dialogue.report_any_problems(result)
    def remove_selected_files_acb(self, menu_item):
        self._remove_named_files(self.get_selected_files())
    def add_files_to_repo(self, file_list):
        self.show_busy()
        result = ifce.SCM.do_add_files(file_list)
        self.unshow_busy()
        self.update_tree()
        dialogue.report_any_problems(result)
    def add_all_files_to_repo(self):
        operation = ifce.SCM.do_add_files
        self.show_busy()
        res, info, serr = operation([], dry_run=True)
        self.unshow_busy()
        if res != cmd_result.OK:
            dialogue.report_any_problems((res, info, serr))
            return
        if self._confirm_list_action((info + serr).splitlines(), "About to be actioned. OK?"):
            self.show_busy()
            result = operation([], dry_run=False)
            self.unshow_busy()
            self.update_tree()
            dialogue.report_any_problems(result)
    def add_selected_files_to_repo_acb(self, menu_item):
        self.add_files_to_repo(self.get_selected_files())
    def add_all_files_to_repo_acb(self, menu_item):
        self.add_all_files_to_repo()
    def update_after_commit(self, files_in_commit=[]):
        self.get_model().del_files_from_displayable_nonexistants(files_in_commit)
        self.update_tree()
    def commit_changes(self, file_list):
        dialog = ScmCommitDialog(parent=dialogue.main_window, filelist=file_list)
        dialog.show()
    def commit_selected_files_acb(self, menu_item):
        self.commit_changes(self.get_selected_files())
    def commit_all_changes_acb(self, menu_item):
        self.commit_changes(None)
    def _get_target(self, src_file_list):
        if len(src_file_list) > 1:
            mode = gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER
        else:
            mode = gtk.FILE_CHOOSER_ACTION_SAVE
        dialog = gtk.FileChooserDialog("Target", dialogue.main_window, mode,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        if mode == gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER:
            dialog.set_current_folder(os.getcwd())
        else:
            dialog.set_current_folder(os.path.abspath(os.path.dirname(src_file_list[0])))
            dialog.set_current_name(os.path.basename(src_file_list[0]))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            target = dialog.get_filename()
        else:
            target = None
        dialog.destroy()
        return (response, target)
    def _move_or_copy_files(self, file_list, reqop, ask=True):
        if reqop == "c":
            operation = ifce.SCM.do_copy_files
        elif reqop == "m":
            operation = ifce.SCM.do_move_files
        else:
            raise "Invalid operation requested"
        response, target = self._get_target(file_list)
        if response == gtk.RESPONSE_OK:
            force = False
            if ask:
                while True:
                    self.show_busy()
                    res, sout, serr = operation(file_list, target, force=force, dry_run=True)
                    self.unshow_busy()
                    if cmd_result.is_less_than_error(res):
                        ok = self._confirm_list_action(sout.splitlines(), "About to be actioned. OK?")
                        break
                    elif not force and (res & cmd_result.SUGGEST_FORCE) == cmd_result.SUGGEST_FORCE:
                        ok = force = self._check_if_force((res, sout, serr))
                        if not force:
                            return
                    else:
                        dialogue.report_any_problems((res, sout, serr))
                        return
            if not ask or ok:
                while True:
                    self.show_busy()
                    response = operation(file_list, target, force=force)
                    self.unshow_busy()
                    if not force and (response[0] & cmd_result.SUGGEST_FORCE) == cmd_result.SUGGEST_FORCE:
                        ok = force = self._check_if_force(response)
                        if not force:
                            return
                        continue
                    break
                self.update_tree()
                dialogue.report_any_problems(response)
    def copy_files(self, file_list, ask=False):
        self._move_or_copy_files(file_list, "c", ask=ask)
    def copy_selected_files_acb(self, action=None):
        self.copy_files(self.get_selected_files())
    def move_files(self, file_list, ask=True):
        self._move_or_copy_files(file_list, "m", ask=ask)
    def move_selected_files_acb(self, action=None):
        self.move_files(self.get_selected_files())
    def diff_selected_files_acb(self, action=None):
        dialog = diff.ScmDiffTextDialog(parent=dialogue.main_window,
                                     file_list=self.get_selected_files())
        dialog.show()
    def revert_named_files(self, file_list, ask=True):
        if ask:
            self.show_busy()
            res, sout, serr = ifce.SCM.do_revert_files(file_list, dry_run=True)
            self.unshow_busy()
            if res == cmd_result.OK:
                if sout:
                    ok = self._confirm_list_action(sout.splitlines(), "About to be actioned. OK?")
                else:
                    self._report_info("Nothing to revert")
                    return
            else:
                dialogue.report_any_problems((res, sout, serr))
                return
        else:
            ok = True
        if ok:
            self.show_busy()
            result = ifce.SCM.do_revert_files(file_list)
            self.get_model().del_files_from_displayable_nonexistants(file_list)
            self.unshow_busy()
            self.update_tree()
            dialogue.report_any_problems(result)
    def revert_selected_files_acb(self, action=None):
        self.revert_named_files(self.get_selected_files())
    def revert_all_files_acb(self, action=None):
        self.revert_named_files([])

class ScmCwdFilesWidget(gtk.VBox):
    def __init__(self, busy_indicator=None, auto_refresh=False, show_hidden=False):
        gtk.VBox.__init__(self)
        # file tree view wrapped in scrolled window
        self.file_tree = ScmCwdFileTreeView(busy_indicator=busy_indicator,
            auto_refresh=auto_refresh, show_hidden=show_hidden)
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
        # Mode selectors
        hbox = gtk.HBox()
        for action_name in ["auto_refresh_files", "show_hidden_files"]:
            button = gtk.CheckButton()
            action = self.file_tree.get_conditional_action(action_name)
            action.connect_proxy(button)
            dialogue.tooltips.set_tip(button, action.get_property("tooltip"))
            hbox.pack_start(button)
        self.pack_start(hbox, expand=False)
        self.show_all()

class ScmChangeFileTreeStore(FileTreeStore):
    def __init__(self, show_hidden=True, view=None, file_mask=[]):
        self._file_mask = file_mask
        row_data = apply(FileTreeRowData, ifce.SCM.get_status_row_data())
        FileTreeStore.__init__(self, show_hidden=show_hidden, row_data=row_data)
        # if this is set to the associated view then the view will expand
        # to show new files without disturbing other expansion states
        self._view = view
        self.repopulate()
    def set_view(self, view):
        self._view = view
    def set_file_mask(self, file_mask):
        self._file_mask = file_mask
        self.update()
    def get_file_mask(self):
        return self._file_mask
    def update(self, fsobj_iter=None):
        res, dflists, dummy = ifce.SCM.get_file_status_lists(self._file_mask)
        if res == 0:
            files = [tmpx[0] for tmpx in dflists[MODIFIED]] 
            for f in self.get_file_paths():
                try:
                    i = files.index(f)
                except:
                    self.delete_file(f)
            for dfile, status, extra_info in dflists[MODIFIED]:
                found, file_iter = self.find_or_insert_file(dfile, file_status=status, extra_info=extra_info)
                assert self.iter_is_valid(file_iter)
                if not found and self._view:
                    self._view.expand_to_path(self.get_path(file_iter))
    def repopulate(self):
        self.clear()
        self.update()

SCM_CHANGE_UI_DESCR = \
'''
<ui>
  <popup name="files_popup">
    <placeholder name="selection_indifferent">
      <menuitem action="scmch_undo_remove_files"/>
    </placeholder>
    <separator/>
    <placeholder name="selection">
      <menuitem action="scm_diff_files_selection"/>
      <menuitem action="scmch_remove_files"/>
    </placeholder>
    <separator/>
    <placeholder name="unique_selection"/>
    <separator/>
    <placeholder name="no_selection"/>
      <menuitem action="scm_diff_files_all"/>
    <separator/>
  </popup>
</ui>
'''

class ScmChangeFileTreeView(FileTreeView):
    def __init__(self, busy_indicator, auto_refresh=False, show_hidden=True, file_mask=[]):
        self.removeds = []
        self.model = ScmChangeFileTreeStore(show_hidden=show_hidden, file_mask=file_mask)
        self.model.set_view(self)
        FileTreeView.__init__(self, model=self.model, busy_indicator=busy_indicator,
                              auto_refresh=auto_refresh, show_status=True)
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.set_headers_visible(False)
        self.add_conditional_actions(actions.ON_IN_REPO_SELN,
            [
                ("scmch_remove_files", gtk.STOCK_DELETE, "_Remove", None,
                 "Remove the selected files from the change set", self._remove_selected_files_acb),
                ("scm_diff_files_selection", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for selected file(s)", self._diff_selected_files_acb),
            ])
        self.add_conditional_actions(actions.ON_IN_REPO_SELN_INDEP,
            [
                ("scmch_undo_remove_files", gtk.STOCK_UNDO, "_Undo", None,
                 "Undo the last remove", self._undo_last_remove_acb),
            ])
        self.add_conditional_actions(actions.ON_IN_REPO_NO_SELN,
            [
                ("scm_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self._diff_all_files_acb),
            ])
        self.scm_change_merge_id = self.ui_manager.add_ui_from_string(SCM_CHANGE_UI_DESCR)
        self.get_conditional_action("scmch_undo_remove_files").set_sensitive(False)
    def set_file_mask(self, file_mask):
        self.model.set_file_mask(file_mask)
    def get_file_mask(self):
        return self.model.get_file_mask()
    def _remove_selected_files_acb(self, menu_item):
        self.show_busy()
        file_mask = self.model.get_file_mask()
        if not file_mask:
            file_mask = self.model.get_file_paths()
        selected_files = self.get_selected_files()
        for sel_file in selected_files:
            del file_mask[file_mask.index(sel_file)]
        self.model.set_file_mask(file_mask)
        self.removeds.append(selected_files)
        self.get_conditional_action("scmch_undo_remove_files").set_sensitive(True)
        self.unshow_busy()
        self.update_tree()
    def _undo_last_remove_acb(self, menu_item):
        self.show_busy()
        restore_files = self.removeds[-1]
        del self.removeds[-1]
        self.get_conditional_action("scmch_undo_remove_files").set_sensitive(len(self.removeds) > 0)
        file_mask = self.model.get_file_mask()
        for res_file in restore_files:
            file_mask.append(res_file)
        self.model.set_file_mask(file_mask)
        self.unshow_busy()
        self.update_tree()
    def _diff_selected_files_acb(self, action=None):
        parent = dialogue.main_window
        dialog = diff.ScmDiffTextDialog(parent=parent, file_list=self.get_selected_files())
        dialog.show()
    def _diff_all_files_acb(self, action=None):
        parent = dialogue.main_window
        dialog = diff.ScmDiffTextDialog(parent=parent, file_list=self.get_file_mask())
        dialog.show()

class ScmCommitWidget(gtk.VPaned, ws_event.Listener):
    def __init__(self, busy_indicator, file_mask=[]):
        gtk.VPaned.__init__(self)
        ws_event.Listener.__init__(self)
        # TextView for change message
        self.view = text_edit.ChangeSummaryView()
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        menubar = self.view.ui_manager.get_widget("/change_summary_menubar")
        hbox.pack_start(menubar, fill=True, expand=False)
        toolbar = self.view.ui_manager.get_widget("/change_summary_toolbar")
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        hbox.pack_end(toolbar, fill=False, expand=False)
        vbox.pack_start(hbox, expand=False)
        vbox.pack_start(gutils.wrap_in_scrolled_window(self.view))
        self.add1(vbox)
        # TreeView of files in change set
        self.files = ScmChangeFileTreeView(busy_indicator=busy_indicator,
                                           auto_refresh=False,
                                           show_hidden=True,
                                           file_mask=file_mask)
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Files"), fill=True, expand=False)
        toolbar = self.files.ui_manager.get_widget("/files_refresh_toolbar")
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        hbox.pack_end(toolbar, fill=False, expand=False)
        vbox.pack_start(hbox, expand=False)
        x, y = self.files.tree_to_widget_coords(480, 240)
        self.files.set_size_request(x, y)
        self.files.expand_all()
        vbox.pack_start(gutils.wrap_in_scrolled_window(self.files))
        vbox.show_all()
        self.add2(vbox)
        self.show_all()
        self.set_focus_child(self.view)
    def get_msg(self):
        return self.view.get_msg()
    def get_file_mask(self):
        return self.files.get_file_mask()
    def do_commit(self):
        result = ifce.SCM.do_commit_change(self.get_msg(), self.get_file_mask())
        dialogue.report_any_problems(result)
        return cmd_result.is_less_than_error(result[0])

class ScmCommitDialog(dialogue.AmodalDialog):
    def __init__(self, parent, filelist=None):
        flags = gtk.DIALOG_DESTROY_WITH_PARENT
        dialogue.AmodalDialog.__init__(self, None, parent, flags,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                       gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.set_title('Commit Changes: %s' % utils.cwd_rel_home())
        self.commit_widget = ScmCommitWidget(busy_indicator=self, file_mask=filelist)
        self.vbox.pack_start(self.commit_widget)
        self.connect('response', self._handle_response_cb)
        self.set_focus_child(self.commit_widget.view)
    def get_mesg_and_files(self):
        return (self.commit_widget.get_msg(), self.commit_widget.get_file_mask())
    def update_files(self):
        self.commit_widget.files.update_tree()
    def _finish_up(self, clear_save=False):
        self.show_busy()
        self.commit_widget.view.get_buffer().finish_up(clear_save)
        self.unshow_busy()
        self.destroy()
    def _handle_response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_OK:
            if self.commit_widget.do_commit():
                self._finish_up(clear_save=True)
            else:
                dialog.update_files()
        elif self.commit_widget.view.get_buffer().get_modified():
            if self.commit_widget.view.get_auto_save():
                self._finish_up()
            else:
                qn = 'Unsaved changes to summary will be lost.\n\nCancel anyway?'
                if dialogue.ask_yes_no(qn):
                    self._finish_up()
        else:
            self._finish_up()
