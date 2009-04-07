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

import os, os.path, tempfile, gtk, gtk.gdk
from gwsmhg_pkg import utils, text_edit, cmd_result, diff, console, gutils
import gtksourceview

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
        name = store.get_value(tree_iter, NAME)
        xinfo = store.get_value(tree_iter, EXTRA_INFO)
        if xinfo:
            return self._extra_info_sep.join([name, xinfo])
        else:
            return name
    def format_file_name_crcb(self, column, cell_renderer, store, tree_iter):
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
        name = store.get_value(tree_iter, NAME)
        xinfo = store.get_value(tree_iter, EXTRA_INFO)
        if xinfo:
            return self._row_data._extra_info_sep.join([name, xinfo])
        else:
            return name
    def format_file_name_crcb(self, column, cell_renderer, store, tree_iter):
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
        return self.fs_path(fsobj_iter) in self._displayable_nonexistants
    def _add_displayable_nonexistant(self, fsobj_iter):
        fsobj_fspath = self.fs_path(fsobj_iter)
        if fsobj_fspath not in self._displayable_nonexistants:
            self._displayable_nonexistants.append(fsobj_fspath)
    def _del_displayable_nonexistant(self, fsobj_iter):
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
        for index in [STYLE, FOREGROUND, STATUS, EXTRA_INFO]:
            self.set_value(fsobj_iter, index, to_tuple[index])
    def _toggle_show_hidden_cb(self, toggleaction):
        self.update()
    def fs_path(self, fsobj_iter):
        if fsobj_iter is None:
            return None
        parent_iter = self.iter_parent(fsobj_iter)
        name = self.get_value(fsobj_iter, NAME)
        if parent_iter is None:
            return name
        else:
            return os.path.join(self.fs_path(parent_iter), name)
    def fs_path_list(self, iter_list):
        return [self.fs_path(fsobj_iter) for fsobj_iter in iter_list]
    def _find_dir(self, ldirpath, dir_iter):
        while dir_iter != None:
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
            file_iter = self.iter_children(dir_iter)
        while file_iter != None:
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
        return self._find_file_in_dir(fname, dir_iter)
    def _get_file_paths(self, fsobj_iter, path_list):
        while fsobj_iter != None:
            if not self.get_value(fsobj_iter, IS_DIR):
                path_list.append(self.fs_path(fsobj_iter))
            else:
                child_iter = self.iter_children(fsobj_iter)
                if child_iter != None:
                    self._get_file_paths(child_iter, path_list)
            fsobj_iter = self.iter_next(fsobj_iter)
    def get_file_paths(self):
        path_list = []
        self._get_file_paths(self.get_iter_first(), path_list)
        return path_list
    def _recursive_remove(self, fsobj_iter):
        child_iter = self.iter_children(fsobj_iter)
        if child_iter != None:
            self._del_displayable_nonexistant(child_iter)
            while self._recursive_remove(child_iter):
                self._del_displayable_nonexistant(child_iter)
        self._del_displayable_nonexistant(fsobj_iter)
        return self.remove(fsobj_iter)
    def _remove_place_holder(self, dir_iter):
        child_iter = self.iter_children(dir_iter)
        if child_iter and self.get_value(child_iter, NAME) is None:
            self.remove(child_iter)
    def _insert_place_holder(self, dir_iter):
        self.append(dir_iter)
    def _insert_place_holder_if_needed(self, dir_iter):
        if self.iter_n_children(dir_iter) == 0:
            self._insert_place_holder(dir_iter)
    def _find_or_insert_dir(self, parent_iter, row_tuple):
        if parent_iter is None:
            dir_iter = self.get_iter_first()
        else:
            self._remove_place_holder(parent_iter)
            dir_iter = self.iter_children(parent_iter)
        if dir_iter is None:
            return (False, self.append(parent_iter, row_tuple))
        while self.get_value(dir_iter, IS_DIR) and self.get_value(dir_iter, NAME) < row_tuple[NAME]:
            next = self.iter_next(dir_iter)
            if next is None or not self.get_value(next, IS_DIR):
                return (False, self.insert_after(parent_iter, dir_iter, row_tuple))
            dir_iter = next
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
            if not exists:
                self._add_displayable_nonexistant(dir_iter)
            parent_dir_path = os.path.join(parent_dir_path, name)
        self._insert_place_holder_if_needed(dir_iter)
        return (found, dir_iter)
    def _find_or_insert_file(self, parent_iter, row_tuple):
        if parent_iter is None:
            file_iter = self.get_iter_first()
        else:
            self._remove_place_holder(parent_iter)
            file_iter = self.iter_children(parent_iter)
        if file_iter is None:
            return (False, self.append(parent_iter, row_tuple))
        while self.get_value(file_iter, IS_DIR):
            next = self.iter_next(file_iter)
            if next is None:
                return (False, self.insert_after(parent_iter, file_iter, row_tuple))
            file_iter = next
        while self.get_value(file_iter, NAME) < row_tuple[NAME]:
            next = self.iter_next(file_iter)
            if next is None:
                return (False, self.insert_after(parent_iter, file_iter, row_tuple))
            file_iter = next
        if self.get_value(file_iter, NAME) == row_tuple[NAME]:
            self._update_iter_row_tuple(file_iter, row_tuple)
            return (True, file_iter)
        return (False, self.insert_before(parent_iter, file_iter, row_tuple))
    def find_or_insert_file(self, filepath, file_status=None, dir_status=None, extra_info=None):
        dirpath, name = os.path.split(filepath)
        exists, row_tuple = self._generate_row_tuple(dirpath, name, isdir=False, status=file_status, extra_info=extra_info)
        dummy, dir_iter = self.find_or_insert_dir(dirpath, status=dir_status)
        found, file_iter = self._find_or_insert_file(dir_iter, row_tuple)
        if not exists:
            self._add_displayable_nonexistant(file_iter)
        return (found, file_iter)
    def delete_file(self, filepath, leave_extant_dir_parts=True):
        file_iter = self.find_file(filepath)
        if file_iter is None:
            return
        parent_iter = self.iter_parent(file_iter)
        self._recursive_remove(file_iter)
        while parent_iter is not None:
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
                break
    def repopulate(self):
        assert 0, "repopulate() must be defined in descendants"
    def update(self, fsobj_iter=None):
        assert 0, "repopulate() must be defined in descendants"
    def on_row_expanded_cb(self, view, dir_iter, dummy):
        if self.iter_n_children(dir_iter) > 1:
            self._remove_place_holder(dir_iter)
    def on_row_collapsed_cb(self, view, dir_iter, dummy):
        self._insert_place_holder_if_needed(dir_iter)

class CwdFileTreeStore(FileTreeStore):
    def __init__(self, show_hidden=False, row_data=DEFAULT_ROW_DATA):
        FileTreeStore.__init__(self, show_hidden=show_hidden, row_data=row_data)
        # This will be automatically set when the first row is expanded
        self.view = None
        self.repopulate()
    def _row_expanded(self, dir_iter):
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
            self._insert_place_holder(dir_iter)
        files.sort()
        for filename in files:
            dummy, row_tuple = self._generate_row_tuple(dirpath, filename, isdir=False)
            dummy = self.append(parent_iter, row_tuple)
        if parent_iter is not None:
            self._insert_place_holder_if_needed(parent_iter)
    def _update_dir(self, dirpath, parent_iter=None):
        if not os.path.exists(dirpath):
            return
        if parent_iter is None:
            child_iter = self.get_iter_first()
        else:
            child_iter = self.iter_children(parent_iter)
            if child_iter and self.get_value(child_iter, NAME) is None:
                child_iter = self.iter_next(child_iter)
        if child_iter is None:
            self._populate(dirpath, parent_iter)
            return
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
            if child_iter is None:
                dir_iter = self.append(parent_iter, row_tuple)
                self._insert_place_holder(dir_iter)
                continue
            name = self.get_value(child_iter, NAME)
            if (not self.get_value(child_iter, IS_DIR)) or (name > dirx):
                dir_iter = self.insert_before(parent_iter, child_iter, row_tuple)
                self._insert_place_holder(dir_iter)
                continue
            self._update_iter_row_tuple(child_iter, row_tuple)
            if self._row_expanded(child_iter):
                self._update_dir(os.path.join(dirpath, name), child_iter)
            child_iter = self.iter_next(child_iter)
        while (child_iter is not None) and self.get_value(child_iter, IS_DIR):
            if not self._display_this_nonexistant(child_iter):
                dead_entries.append(child_iter)
            child_iter = self.iter_next(child_iter)
        for filex in files:
            dummy, row_tuple = self._generate_row_tuple(dirpath, filex, isdir=False)
            while (child_iter is not None) and (self.get_value(child_iter, NAME) < filex):
                if not self._display_this_nonexistant(child_iter):
                    dead_entries.append(child_iter)
                child_iter = self.iter_next(child_iter)
            if child_iter is None:
                dummy = self.append(parent_iter, row_tuple)
                continue
            if self.get_value(child_iter, NAME) > filex:
                dummy = self.insert_before(parent_iter, child_iter, row_tuple)
                continue
            self._update_iter_row_tuple(child_iter, row_tuple)
            child_iter = self.iter_next(child_iter)
        while child_iter is not None:
            if not self._display_this_nonexistant(child_iter):
                dead_entries.append(child_iter)
            child_iter = self.iter_next(child_iter)
        for dead_entry in dead_entries:
            self._recursive_remove(dead_entry)
        if parent_iter is not None:
            self._insert_place_holder_if_needed(parent_iter)
    def repopulate(self):
        self.clear()
        self._populate(os.curdir, self.get_iter_first())
    def update(self, fsobj_iter=None):
        if fsobj_iter is None:
            self._update_dir(os.curdir, None)
        else:
            filepath = self.fs_path(fsobj_iter)
            if not os.path.exists(filepath):
                if not self._display_this_nonexistant(fsobj_iter):
                    self._recursive_remove(fsobj_iter)
            elif os.path.isdir(filepath):
                self._update_dir(filepath, fsobj_iter)
                if self.iter_n_children(fsobj_iter) > 1:
                    self._remove_place_holder(fsobj_iter)
    def on_row_expanded_cb(self, view, dir_iter, dummy):
        self.view = view
        self._update_dir(self.fs_path(dir_iter), dir_iter)
        FileTreeStore.on_row_expanded_cb(self, view, dir_iter, dummy)

class ConditionalSensitivity:
    def __init__(self, cond_func=None, cond_arg=None):
        self._cond_func = cond_func
        self._cond_arg = cond_arg
    def conditional_set_sensitive(self, sensitive):
        if sensitive and self._cond_func:
            self.set_sensitive(self._cond_func(self._cond_arg))
        else:
            self.set_sensitive(sensitive)
    def set_condition(self, cond_func=None, cond_arg=None):
        self._cond_func = cond_func
        self._cond_arg = cond_arg

class ConditionalMenuItem(gtk.MenuItem, ConditionalSensitivity):
    def __init__(self, label, cond_func=None, cond_arg=None):
        ConditionalSensitivity.__init__(self, cond_func=cond_func, cond_arg=cond_arg)
        gtk.ImageMenuItem.__init__(self, label)

class ConditionalImageMenuItem(gtk.ImageMenuItem, ConditionalSensitivity):
    def __init__(self, label, image_id, cond_func=None, cond_arg=None):
        ConditionalSensitivity.__init__(self, cond_func=cond_func, cond_arg=cond_arg)
        gtk.ImageMenuItem.__init__(self, label)
        if image_id is not None:
            img = gtk.Image()
            img.set_from_stock(image_id, gtk.ICON_SIZE_MENU)
            self.set_image(img)

NO_SELECTION = "sel_none"
UNIQUE_SELECTION = "sel_unique"
SELECTION = "sel_made"
SELECTION_AGNOSTIC = "sel_agnostic"

class _ViewWithActionGroups(gtk.TreeView, gutils.BusyIndicator, gutils.TooltipsUser):
    def __init__(self, model=None, tooltips=None):
        gutils.TooltipsUser.__init__(self, tooltips)
        gutils.BusyIndicator.__init__(self)
        gtk.TreeView.__init__(self, model)
        self._ui_manager = gtk.UIManager()
        self._action_group = {}
        for sel_condition in NO_SELECTION, UNIQUE_SELECTION, SELECTION, SELECTION_AGNOSTIC:
            self._action_group[sel_condition] = gtk.ActionGroup(sel_condition)
            self._ui_manager.insert_action_group(self._action_group[sel_condition], -1)
        self._action_group[SELECTION_AGNOSTIC].add_action(model.show_hidden_action)
        self.get_selection().connect("changed", self._selection_changed_cb)
        self.connect("button_press_event", self._handle_button_press_cb)
        # Initialize the action groups sensitivity
        self._selection_changed_cb(self.get_selection())
    def _selection_changed_cb(self, selection):
        sel_sz = selection.count_selected_rows()
        self._action_group[NO_SELECTION].set_sensitive(sel_sz == 0)
        self._action_group[UNIQUE_SELECTION].set_sensitive(sel_sz == 1)
        self._action_group[SELECTION].set_sensitive(sel_sz > 0)
    def get_action_group(self, sel_cond):
        return self._action_group[self-cond]
    def get_action_groups(self):
        return self._ui_manager.get_action_groups()
    def get_action(self, action_name):
        for action_group in self._ui_manager.get_action_groups():
            action = action_group.get_action(action_name)
            if action:
                return action
        return None
    def get_ui_manager(self):
        return self._ui_manager
    def get_ui_widget(self, path):
        return self._ui_manager.get_widget(path)
    def get_accel_group(self):
        return self._ui_manager.get_accel_group()
    def _handle_button_press_cb(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 3:
                menu = self._ui_manager.get_widget("/files_popup")
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
    <placeholder name="selection_agnostic"/>
    <separator/>
    <placeholder name="selection"/>
    <separator/>
    <placeholder name="unique_selection"/>
    <separator/>
    <placeholder name="no_selection"/>
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

class FileTreeView(_ViewWithActionGroups, gutils.PopupUser):
    def __init__(self, model=None, tooltips=None, auto_refresh=False, show_hidden=False, show_status=False):
        if model is None:
            model = FileTreeStore(show_hidden=show_hidden)
        _ViewWithActionGroups.__init__(self, model=model, tooltips=tooltips)
        gutils.PopupUser.__init__(self)
        self._refresh_interval = 10000 # milliseconds
        self._create_column(show_status)
        self.connect("row-expanded", model.on_row_expanded_cb)
        self.connect("row-collapsed", model.on_row_collapsed_cb)
        self.auto_refresh_action = gtk.ToggleAction("auto_refresh_files", "Auto Refresh",
                                                   "Automatically/periodically refresh file display", None)
        self.auto_refresh_action.set_active(auto_refresh)
        self.auto_refresh_action.connect("toggled", self._toggle_auto_refresh_cb)
        self.auto_refresh_action.set_menu_item_type(gtk.CheckMenuItem)
        self.auto_refresh_action.set_tool_item_type(gtk.ToggleToolButton)
        self._action_group[SELECTION_AGNOSTIC].add_action(self.auto_refresh_action)
        self._action_group[SELECTION_AGNOSTIC].add_actions(
            [
                ("refresh_files", gtk.STOCK_REFRESH, "_Refresh", None,
                 "Refresh/update the file tree display", self.update_tree),
            ])
        self.cwd_merge_id = self._ui_manager.add_ui_from_string(UI_DESCR)
        self._toggle_auto_refresh_cb()
        self.connect("key_press_event", self._key_press_cb)
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
    def add_selected_files_to_keyboard(self, clipboard=None):
        if not clipboard:
            clipboard = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)
        sel = " ".join(self.get_selected_files())
        clipboard.set_text(sel)
    def _key_press_cb(self, widget, event):
        if event.state == gtk.gdk.CONTROL_MASK:
            if event.keyval in [_KEYVAL_c, _KEYVAL_C]:
                self.add_selected_files_to_keyboard()
                return True
        return False
    def repopulate_tree(self):
        self._show_busy()
        self.get_model().repopulate()
        self._unshow_busy()
    def update_tree(self, action=None):
        self._show_busy()
        self.get_model().update()
        self._unshow_busy()

CWD_UI_DESCR = \
'''
<ui>
  <popup name="files_popup">
    <placeholder name="selection_agnostic">
      <menuitem action="new_file"/>
    </placeholder>
    <separator/>
    <placeholder name="selection">
      <menuitem action="edit_files"/>
      <menuitem action="delete_files"/>
    </placeholder>
    <separator/>
    <placeholder name="unique_selection"/>
    <separator/>
    <placeholder name="no_selection"/>
    <separator/>
    <menuitem action="show_hidden_files"/>
  </popup>
</ui>
'''

class CwdFileTreeView(FileTreeView, cmd_result.ProblemReporter, console.ConsoleLogUser):
    def __init__(self, model=None, tooltips=None, auto_refresh=False, show_hidden=False, show_status=False, console_log=None):
        console.ConsoleLogUser.__init__(self, console_log)
        if not model:
            model = CwdFileTreeStore(show_hidden=show_hidden)
        FileTreeView.__init__(self, model=model, tooltips=tooltips, auto_refresh=auto_refresh, show_status=show_status)
        self._action_group[SELECTION].add_actions(
            [
                ("edit_files", gtk.STOCK_EDIT, "_Edit", None,
                 "Edit the selected file(s)", self.edit_selected_files_acb),
                ("delete_files", gtk.STOCK_DELETE, "_Delete", None,
                 "Delete the selected file(s) from the repository", self.delete_selected_files_acb),
            ])
        self._action_group[SELECTION_AGNOSTIC].add_actions(
            [
                ("new_file", gtk.STOCK_NEW, "_New", None,
                 "Create a new file and open for editing", self.create_new_file_acb),
            ])
        self.cwd_merge_id = self._ui_manager.add_ui_from_string(CWD_UI_DESCR)
    def _confirm_list_action(self, filelist, question):
        msg = os.linesep.join(filelist + [os.linesep, question])
        dialog = gtk.MessageDialog(parent=self._get_gtk_window(),
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
    def new_file(self, new_file_name):
        if os.path.exists(new_file_name):
            serr_xtra = ("File \"%s\" already exists" + os.linesep) % new_file_name
        else:
            serr_xtra = ""
        res, sout, serr = self._run_cmd_on_console("touch %s" % new_file_name)
        return (res, sout, serr_xtra + serr)
    def create_new_file(self, new_file_name, open_for_edit=False):
        model = self.get_model()
        self._show_busy()
        result = self.new_file(new_file_name)
        self._unshow_busy()
        self.update_tree()
        self._report_any_problems(result)
        if open_for_edit:
            self._edit_named_files_extern([new_file_name])
    def create_new_file_acb(self, menu_item):
        dialog = gtk.FileChooserDialog("New File", self._get_gtk_window(),
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
        if self._console_log:
            self._console_log.start_cmd("Deleting: %s" % " ".join(file_list))
        serr = ""
        for filename in file_list:
            try:
                os.remove(filename)
                if self._console_log:
                    self._console_log.append_stdout(("Deleted: %s" + os.linesep) % filename)
            except os.error, value:
                errmsg = ("%s: %s" + os.linesep) % (value[1], filename)
                serr += errmsg
                if self._console_log:
                    self._console_log.append_stderr(errmsg)
        if self._console_log:
            self._console_log.end_cmd()
        if serr:
            return (cmd_result.ERROR, "", serr)
        return (cmd_result.OK, "", "")
    def _delete_named_files(self, file_list, ask=True):
        if not ask or self._confirm_list_action(file_list, "About to be deleted. OK?"):
            model = self.get_model()
            self._show_busy()
            result = self.delete_files(file_list)
            self._unshow_busy()
            self.update_tree()
            self._report_any_problems(result)
    def delete_selected_files_acb(self, menu_item):
        self._delete_named_files(self.get_selected_files())

class ScmCwdFileTreeStore(CwdFileTreeStore):
    def __init__(self, scm_ifce, show_hidden=False):
        self._scm_ifce = scm_ifce
        row_data = apply(FileTreeRowData, self._scm_ifce.get_status_row_data())
        CwdFileTreeStore.__init__(self, show_hidden=show_hidden, row_data=row_data)
        self._update_statuses()
    def _update_statuses(self, fspath_list=[]):
        res, dflists, dummy = self._scm_ifce.get_file_status_lists(fspath_list)
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
    def get_scm_ifce(self):
        return self._scm_ifce
    def set_scm_ifce(self, scm_ifce):
        self._scm_ifce = scm_ifce
        self._row_data = self._scm_ifce.row_data
        self.update()

SCM_CWD_UI_DESCR = \
'''
<ui>
  <menubar name="files_menubar">
    <menu name="files_menu" action="menu_files">
      <menuitem action="scm_add_files_all"/>
      <menuitem action="refresh_files"/>
    </menu>
  </menubar>
  <popup name="files_popup">
    <placeholder name="selection_agnostic">
      <menuitem action="new_file"/>
    </placeholder>
    <placeholder name="selection">
      <menuitem action="edit_files"/>
      <menuitem action="delete_files"/>
      <menuitem action="scm_add_files"/>
      <menuitem action="scm_remove_files"/>
      <menuitem action="scm_commit_files_selection"/>
      <menuitem action="scm_copy_files_selection"/>
      <menuitem action="scm_diff_files_selection"/>
      <menuitem action="scm_move_files_selection"/>
      <menuitem action="scm_revert_files_selection"/>
    </placeholder>
    <placeholder name="unique_selection">
      <menuitem action="scm_rename_file"/>
    </placeholder>
    <placeholder name="no_selection">
      <menuitem action="scm_commit_files_all"/>
      <menuitem action="scm_diff_files_all"/>
      <menuitem action="scm_revert_files_all"/>
    </placeholder>
  </popup>
</ui>
'''

class ScmCwdFileTreeView(CwdFileTreeView):
    def __init__(self, scm_ifce, tooltips=None, auto_refresh=False, show_hidden=False, console_log=None):
        scm_ifce.set_console_log(console_log)
        model = ScmCwdFileTreeStore(scm_ifce=scm_ifce, show_hidden=show_hidden)
        model.get_scm_ifce().add_commit_notification_cb(self.update_after_commit)
        CwdFileTreeView.__init__(self, model=model, tooltips=tooltips, auto_refresh=auto_refresh, console_log=console_log, show_status=True)
        self._action_group[SELECTION].add_actions(
            [
                ("scm_remove_files", gtk.STOCK_REMOVE, "_Remove", None,
                 "Remove the selected file(s) from the repository", self.remove_selected_files_acb),
                ("scm_add_files", gtk.STOCK_ADD, "_Add", None,
                 "Add the selected file(s) to the repository", self.add_selected_files_to_repo_acb),
                ("scm_commit_files_selection", gtk.STOCK_APPLY, "_Commit", None,
                 "Commit changes for selected file(s)", self.commit_selected_files_acb),
                ("scm_copy_files_selection", gtk.STOCK_COPY, "_Copy", None,
                 "Copy the selected file(s)", self.copy_selected_files_acb),
                ("scm_diff_files_selection", gtk.STOCK_APPLY, "_Diff", None,
                 "Display the diff for selected file(s)", self.diff_selected_files_acb),
                ("scm_move_files_selection", gtk.STOCK_PASTE, "_Move/Rename", None,
                 "Move the selected file(s)", self.move_selected_files_acb),
                ("scm_revert_files_selection", gtk.STOCK_UNDO, "Rever_t", None,
                 "Revert changes in the selected file(s)", self.revert_selected_files_acb),
            ])
        self._action_group[UNIQUE_SELECTION].add_actions(
            [
                ("scm_rename_file", gtk.STOCK_PASTE, "Re_name/Move", None,
                 "Rename/move the selected file", self.move_selected_files_acb),
            ])
        self._action_group[NO_SELECTION].add_actions(
            [
                ("scm_add_files_all", gtk.STOCK_ADD, "_Add all", None,
                 "Add all files to the repository", self.add_all_files_to_repo_acb),
                ("scm_commit_files_all", gtk.STOCK_APPLY, "_Commit", None,
                 "Commit all changes", self.commit_all_changes_acb),
                ("scm_diff_files_all", gtk.STOCK_APPLY, "_Diff", None,
                 "Display the diff for all changes", self.diff_selected_files_acb),
                ("scm_revert_files_all", gtk.STOCK_UNDO, "Rever_t", None,
                 "Revert all changes in working directory", self.revert_all_files_acb),
            ])
        self._action_group[SELECTION_AGNOSTIC].add_actions(
            [
                ("menu_files", None, "_Files"),
            ])
        self.cwd_merge_id = self._ui_manager.add_ui_from_string(SCM_CWD_UI_DESCR)
    def get_scm_name(self):
        return self.get_model().get_scm_ifce().name
    def get_scm_ifce(self):
        return self.get_model().get_scm_ifce()
    def set_scm_ifce(self, scm_ifce):
        old_scm_ifce = self.get_scm_ifce()
        if old_scm_ifce:
            old_scm_ifce.del_commit_notification_cb(self.update_after_commit)
        self.get_model().set_scm_ifce(scm_ifce)
        new_scm_ifce = self.get_scm_ifce()
        if new_scm_ifce:
            new_scm_ifce.add_commit_notification_cb(self.update_after_commit)
    def _busy_run_cmd_on_console(self, cmd):
        self._show_busy()
        result = self._run_cmd_on_console(cmd)
        self._unshow_busy()
        return result
    def _check_if_force(self, result):
        if (result[0] & cmd_result.SUGGEST_FORCE) == cmd_result.SUGGEST_FORCE:
            dialog = gtk.MessageDialog(parent=self._get_gtk_window(),
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
            self._show_busy()
            result = model.get_scm_ifce().remove_files(file_list)
            self._show_busy()
            if self._check_if_force(result):
                result = model.get_scm_ifce().remove_files(file_list, force=True)
            self.update_tree()
            self._report_any_problems(result)
    def remove_selected_files_acb(self, menu_item):
        self._remove_named_files(self.get_selected_files())
    def add_files_to_repo(self, file_list):
        self._show_busy()
        result = self.get_scm_ifce().add_files(file_list)
        self._unshow_busy()
        self.update_tree()
        self._report_any_problems(result)
    def add_all_files_to_repo(self):
        operation = self.get_scm_ifce().add_files
        self._show_busy()
        res, info, serr = operation([], dry_run=True)
        self._unshow_busy()
        if res != cmd_result.OK:
            self._report_any_problems((res, info, serr))
            return
        if self._confirm_list_action((info + serr).splitlines(), "About to be actioned. OK?"):
            self._show_busy()
            result = operation([], dry_run=False)
            self._unshow_busy()
            self.update_tree()
            self._report_any_problems(result)
    def add_selected_files_to_repo_acb(self, menu_item):
        self.add_files_to_repo(self.get_selected_files())
    def add_all_files_to_repo_acb(self, menu_item):
        self.add_all_files_to_repo()
    def update_after_commit(self, files_in_commit):
        self.get_model().del_files_from_displayable_nonexistants(files_in_commit)
        self.update_tree()
    def commit_changes(self, file_list):
        dialog = ScmCommitDialog(parent=self._get_gtk_window(), scm_ifce=self.get_scm_ifce(), filelist=file_list)
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
        dialog = gtk.FileChooserDialog("Target", self._get_gtk_window(), mode,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        if mode == gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER:
            dialog.set_current_folder(os.getcwd())
        else:
            dialog.set_current_folder(os.path.dirname(src_file_list[0]))
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
            operation = self.get_scm_ifce().copy_files
        elif reqop == "m":
            operation = self.get_scm_ifce().move_files
        else:
            raise "Invalid operation requested"
        response, target = self._get_target(file_list)
        if response == gtk.RESPONSE_OK:
            force = False
            if ask:
                while True:
                    self._show_busy()
                    res, sout, serr = operation(file_list, target, force=force, dry_run=True)
                    self._unshow_busy()
                    if res == cmd_result.OK:
                        ok = self._confirm_list_action(sout.splitlines(), "About to be actioned. OK?")
                        break
                    elif not force and (res & cmd_result.SUGGEST_FORCE) == cmd_result.SUGGEST_FORCE:
                        ok = force = self._check_if_force((res, sout, serr))
                        if not force:
                            return
                    else:
                        self._report_any_problems((res, sout, serr))
                        return
            if not ask or ok:
                while True:
                    self._show_busy()
                    response = operation(file_list, target, force=force)
                    self._unshow_busy()
                    if not force and (response[0] & cmd_result.SUGGEST_FORCE) == cmd_result.SUGGEST_FORCE:
                        ok = force = self._check_if_force(response)
                        if not force:
                            return
                        continue
                    break
                self.update_tree()
                self._report_any_problems(response)
    def copy_files(self, file_list, ask=False):
        self._move_or_copy_files(file_list, "c", ask=ask)
    def copy_selected_files_acb(self, action=None):
        self.copy_files(self.get_selected_files())
    def move_files(self, file_list, ask=True):
        self._move_or_copy_files(file_list, "m", ask=ask)
    def move_selected_files_acb(self, action=None):
        self.move_files(self.get_selected_files())
    def diff_selected_files_acb(self, action=None):
        dialog = diff.DiffTextDialog(parent=self._get_gtk_window(),
                                     scm_ifce=self.get_scm_ifce(),
                                     file_list=self.get_selected_files(), modal=False)
        dialog.show()
    def revert_named_files(self, file_list, ask=True):
        if ask:
            self._show_busy()
            res, sout, serr = self.get_scm_ifce().revert_files(file_list, dry_run=True)
            self._unshow_busy()
            if res == cmd_result.OK:
                if sout:
                    ok = self._confirm_list_action(sout.splitlines(), "About to be actioned. OK?")
                else:
                    self._report_info("Nothing to revert")
                    return
            else:
                self._report_any_problems((res, sout, serr))
                return
        else:
            ok = True
        if ok:
            self._show_busy()
            result = self.get_scm_ifce().revert_files(file_list)
            self.get_model().del_files_from_displayable_nonexistants(file_list)
            self._show_busy()
            self.update_tree()
            self._report_any_problems(result)
    def revert_selected_files_acb(self, action=None):
        self.revert_named_files(self.get_selected_files())
    def revert_all_files_acb(self, action=None):
        self.revert_named_files([])

class ScmCwdFilesWidget(gtk.VBox):
    def __init__(self, scm_ifce, tooltips=None, auto_refresh=False, show_hidden=False, console_log=None):
        gtk.VBox.__init__(self)
        self._tooltips = tooltips
        # file tree view wrapped in scrolled window
        self.file_tree = ScmCwdFileTreeView(scm_ifce=scm_ifce, tooltips=tooltips, auto_refresh=auto_refresh,
                                            show_hidden=show_hidden, console_log=console_log)
        scw = gtk.ScrolledWindow()
        scw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.file_tree.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.file_tree.set_headers_visible(False)
        self.file_tree.set_size_request(240, 320)
        scw.add(self.file_tree)
        # file tree menu bar
        self.menu_bar = self.file_tree.get_ui_widget("/files_menubar")
        self.pack_start(self.menu_bar, expand=False)
        self.pack_start(scw, expand=True, fill=True)
        # Mode selectors
        hbox = gtk.HBox()
        for action_name in ["show_hidden_files", "auto_refresh_files"]:
            button = gtk.CheckButton()
            action = self.file_tree.get_action(action_name)
            action.connect_proxy(button)
            if self._tooltips:
                self._tooltips.set_tip(button, action.get_property("tooltip"))
            hbox.pack_start(button)
        self.pack_start(hbox, expand=False)
        self.show_all()

class ScmChangeFileTreeStore(FileTreeStore):
    def __init__(self, scm_ifce, show_hidden=True, view=None, file_mask=None):
        self._file_mask = file_mask
        self._scm_ifce = scm_ifce
        row_data = apply(FileTreeRowData, self._scm_ifce.get_status_row_data())
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
        res, dflists, dummy = self._scm_ifce.get_file_status_lists(self._file_mask)
        if res == 0:
            files = [tmpx[0] for tmpx in dflists[MODIFIED]] 
            for f in self.get_file_paths():
                try:
                    i = files.index(f)
                except:
                    self.delete_file(f)
            for dfile, status, extra_info in dflists[MODIFIED]:
                found, file_iter = self.find_or_insert_file(dfile, file_status=status, extra_info=extra_info)
                if not found and self._view:
                    self._view.expand_to_path(self.get_path(file_iter))
    def repopulate(self):
        self.clear()
        self.update()
    def get_scm_ifce(self):
        return self._scm_ifce
    def set_scm_ifce(self, scm_ifce):
        self._scm_ifce = scm_ifce
        self.update()

SCM_CHANGE_UI_DESCR = \
'''
<ui>
  <popup name="files_popup">
    <placeholder name="selection_agnostic">
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
    def __init__(self, scm_ifce, tooltips=None, auto_refresh=False, show_hidden=True, file_mask=None):
        self.removeds = []
        self.model = ScmChangeFileTreeStore(scm_ifce, show_hidden=show_hidden, file_mask=file_mask)
        self.model.set_view(self)
        FileTreeView.__init__(self, model=self.model, tooltips=tooltips, auto_refresh=auto_refresh, show_status=True)
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.set_headers_visible(False)
        self._action_group[SELECTION].add_actions(
            [
                ("scmch_remove_files", gtk.STOCK_DELETE, "_Remove", None,
                 "Remove the selected files from the change set", self._remove_selected_files_acb),
                ("scm_diff_files_selection", gtk.STOCK_APPLY, "_Diff", None,
                 "Display the diff for selected file(s)", self._diff_selected_files_acb),
            ])
        self._action_group[SELECTION_AGNOSTIC].add_actions(
            [
                ("scmch_undo_remove_files", gtk.STOCK_UNDO, "_Undo", None,
                 "Undo the last remove", self._undo_last_remove_acb),
            ])
        self._action_group[NO_SELECTION].add_actions(
            [
                ("scm_diff_files_all", gtk.STOCK_APPLY, "_Diff", None,
                 "Display the diff for all changes", self._diff_all_files_acb),
            ])
        self._action_group[SELECTION_AGNOSTIC].get_action("scmch_undo_remove_files").set_sensitive(False)
        self.scm_change_merge_id = self._ui_manager.add_ui_from_string(SCM_CHANGE_UI_DESCR)
    def set_file_mask(self, file_mask):
        self.model.set_file_mask(file_mask)
    def get_file_mask(self):
        return self.model.get_file_mask()
    def _remove_selected_files_acb(self, menu_item):
        self._show_busy()
        file_mask = self.model.get_file_mask()
        if not file_mask:
            file_mask = self.model.get_file_paths()
        selected_files = self.get_selected_files()
        for sel_file in selected_files:
            del file_mask[file_mask.index(sel_file)]
        self.model.set_file_mask(file_mask)
        self.removeds.append(selected_files)
        self._action_group[SELECTION_AGNOSTIC].get_action("scmch_undo_remove_files").set_sensitive(True)
        self._unshow_busy()
        self.update_tree()
    def _undo_last_remove_acb(self, menu_item):
        self._show_busy()
        restore_files = self.removeds[-1]
        del self.removeds[-1]
        self._action_group[SELECTION_AGNOSTIC].get_action("scmch_undo_remove_files").set_sensitive(len(self.removeds) > 0)
        file_mask = self.model.get_file_mask()
        for res_file in restore_files:
            file_mask.append(res_file)
        self.model.set_file_mask(file_mask)
        self._unshow_busy()
        self.update_tree()
    def _diff_selected_files_acb(self, action=None):
        parent = self._get_gtk_window()
        dialog = diff.DiffTextDialog(parent=parent,
                                     scm_ifce=self.get_model().get_scm_ifce(),
                                     file_list=self.get_selected_files(),
                                     modal=False)
        dialog.show()
    def _diff_all_files_acb(self, action=None):
        parent = self._get_gtk_window()
        dialog = diff.DiffTextDialog(parent=parent,
                                     scm_ifce=self.get_model().get_scm_ifce(),
                                     file_list=self.get_file_mask(),
                                     modal=False)
        dialog.show()

import gutils

class ScmCommitWidget(gtk.VPaned, cmd_result.ProblemReporter):
    def __init__(self, scm_ifce, tooltips=None, file_mask=None):
        gtk.VPaned.__init__(self)
        cmd_result.ProblemReporter.__init__(self)
        self._scm_ifce = scm_ifce
        # TextView for change message
        self.view = text_edit.ChangeSummaryView(scm_ifce=self._scm_ifce)
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        menubar = self.view.get_ui_widget("/change_summary_menubar")
        hbox.pack_start(menubar, fill=True, expand=False)
        toolbar = self.view.get_ui_widget("/change_summary_toolbar")
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        hbox.pack_end(toolbar, fill=False, expand=False)
        vbox.pack_start(hbox, expand=False)
        vbox.pack_start(gutils.wrap_in_scrolled_window(self.view))
        self.add1(vbox)
        # TreeView of files in change set
        self.files = ScmChangeFileTreeView(scm_ifce=self._scm_ifce,
                                          tooltips=tooltips,
                                          auto_refresh=False,
                                          show_hidden=True,
                                          file_mask=file_mask)
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Files"), fill=True, expand=False)
        toolbar = self.files.get_ui_widget("/files_refresh_toolbar")
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
        result = self._scm_ifce.commit_change(self.get_msg(), self.get_file_mask())
        self._report_any_problems(result)
        return result[0] == cmd_result.OK

class ScmCommitDialog(gtk.Dialog):
    def __init__(self, parent, scm_ifce, filelist=None, modal=False):
        if modal or (parent and parent.get_modal()):
            flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
        else:
            flags = gtk.DIALOG_DESTROY_WITH_PARENT
        gtk.Dialog.__init__(self, "Commit Changes: %s" % os.getcwd(), parent, flags,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.commit_widget = ScmCommitWidget(scm_ifce=scm_ifce, tooltips=None, file_mask=filelist)
        self.vbox.pack_start(self.commit_widget)
        self.connect("response", self._handle_response_cb)
        self.set_focus_child(self.commit_widget.view)
    def get_mesg_and_files(self):
        return (self.commit_widget.get_msg(), self.commit_widget.get_file_mask())
    def update_files(self):
        self.commit_widget.files.update_tree()
    def _finish_up(self):
        self.commit_widget.view.get_buffer().finish_up()
        self.destroy()
    def _handle_response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_OK:
            if self.commit_widget.do_commit():
                self._finish_up()
            else:
                dialog.update_files()
        elif self.commit_widget.view.get_buffer().get_modified():
            if self.commit_widget.view.get_auto_save():
                self._finish_up()
            else:
                qn = os.linesep.join(["Unsaved changes to summary will be lost.", "Cancel anyway?"])
                if gutils.ask_yes_no(qn):
                    self._finish_up()
        else:
            self._finish_up()

