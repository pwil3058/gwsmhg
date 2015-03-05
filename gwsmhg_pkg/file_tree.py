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
import gobject
import collections
import os
import os.path

from gwsmhg_pkg import utils
from gwsmhg_pkg import cmd_result
from gwsmhg_pkg import fsdb

from gwsmhg_pkg import tlview
from gwsmhg_pkg import gutils
from gwsmhg_pkg import ifce
from gwsmhg_pkg import actions
from gwsmhg_pkg import ws_actions
from gwsmhg_pkg import dialogue
from gwsmhg_pkg import ws_event
from gwsmhg_pkg import icons
from gwsmhg_pkg import text_edit
from gwsmhg_pkg import diff
from gwsmhg_pkg import tortoise

from gwsmhg_pkg import patchlib
from gwsmhg_pkg import hg_mq_ifce

class Tree(tlview.TreeView, ws_actions.AGandUIManager, ws_event.Listener, dialogue.BusyIndicatorUser):
    class Model(tlview.TreeView.Model):
        Row = collections.namedtuple('Row', ['name', 'is_dir', 'style', 'foreground', 'icon', 'status', 'related_file_str'])
        types = Row(
            name=gobject.TYPE_STRING,
            is_dir=gobject.TYPE_BOOLEAN,
            style=gobject.TYPE_INT,
            foreground=gobject.TYPE_STRING,
            icon=gobject.TYPE_STRING,
            status=gobject.TYPE_STRING,
            related_file_str=gobject.TYPE_STRING
        )
        def insert_place_holder(self, dir_iter):
            self.append(dir_iter)
        def insert_place_holder_if_needed(self, dir_iter):
            if self.iter_n_children(dir_iter) == 0:
                self.insert_place_holder(dir_iter)
        def recursive_remove(self, fsobj_iter):
            child_iter = self.iter_children(fsobj_iter)
            if child_iter != None:
                while self.recursive_remove(child_iter):
                    pass
            return self.remove(fsobj_iter)
        def remove_place_holder(self, dir_iter):
            child_iter = self.iter_children(dir_iter)
            if child_iter and self.get_value_named(child_iter, "name") is None:
                self.remove(child_iter)
        def fs_path(self, fsobj_iter):
            if fsobj_iter is None:
                return None
            parent_iter = self.iter_parent(fsobj_iter)
            name = self.get_value_named(fsobj_iter, "name")
            if parent_iter is None:
                return name
            else:
                if name is None:
                    return os.path.join(self.fs_path(parent_iter), '')
                return os.path.join(self.fs_path(parent_iter), name)
        def on_row_expanded_cb(self, view, dir_iter, _dummy):
            if not view._populate_all:
                view._update_dir(self.fs_path(dir_iter), dir_iter)
                if self.iter_n_children(dir_iter) > 1:
                    self.remove_place_holder(dir_iter)
        def on_row_collapsed_cb(self, _view, dir_iter, _dummy):
            self.insert_place_holder_if_needed(dir_iter)
        def update_iter_row_tuple(self, fsobj_iter, to_tuple):
            for label in ["style", "foreground", "status", "related_file_str", "icon"]:
                self.set_value_named(fsobj_iter, label, getattr(to_tuple, label))
        def _get_file_paths(self, fsobj_iter, path_list):
            while fsobj_iter != None:
                if not self.get_value_named(fsobj_iter, "is_dir"):
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
    # This is not a method but a function within the Tree namespace
    def _format_file_name_crcb(_column, cell_renderer, store, tree_iter, _arg=None):
        name = store.get_value_named(tree_iter, "name")
        if name is None:
            cell_renderer.set_property("text", _("<empty>"))
            return
        name += store.get_value_named(tree_iter, "related_file_str")
        cell_renderer.set_property("text", name)
    specification = tlview.ViewSpec(
        properties={"headers-visible" : False},
        selection_mode=gtk.SELECTION_MULTIPLE,
        columns=[
            tlview.ColumnSpec(
                title=_("File Name"),
                properties={},
                cells=[
                    tlview.CellSpec(
                        cell_renderer_spec=tlview.CellRendererSpec(
                            cell_renderer=gtk.CellRendererPixbuf,
                            expand=False,
                            start=True
                        ),
                        properties={},
                        cell_data_function_spec=None,
                        attributes={"stock-id" : Model.col_index("icon")}
                    ),
                    tlview.CellSpec(
                        cell_renderer_spec=tlview.CellRendererSpec(
                            cell_renderer=gtk.CellRendererText,
                            expand=False,
                            start=True
                        ),
                        properties={},
                        cell_data_function_spec=None,
                        attributes={"text" : Model.col_index("status"), "style" : Model.col_index("style"), "foreground" : Model.col_index("foreground")}
                    ),
                    tlview.CellSpec(
                        cell_renderer_spec=tlview.CellRendererSpec(
                            cell_renderer=gtk.CellRendererText,
                            expand=False,
                            start=True
                        ),
                        properties={},
                        cell_data_function_spec=tlview.CellDataFunctionSpec(function=_format_file_name_crcb, user_data=None),
                        attributes={"style" : Model.col_index("style"), "foreground" : Model.col_index("foreground")}
                    )
                ]
            )
        ]
    )
    KEYVAL_c = gtk.gdk.keyval_from_name('c')
    KEYVAL_C = gtk.gdk.keyval_from_name('C')
    KEYVAL_ESCAPE = gtk.gdk.keyval_from_name('Escape')
    AUTO_EXPAND = False
    @staticmethod
    def _get_related_file_str(data):
        if data.related_file:
            if isinstance(data.related_file, str):
                return " <- " + data.related_file
            else:
                return " {0} {1}".format(data.related_file.relation, data.related_file.path)
        return ""
    @staticmethod
    def _handle_button_press_cb(widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 2:
                widget.get_selection().unselect_all()
                return True
        return False
    @staticmethod
    def _handle_key_press_cb(widget, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            if event.keyval in [Tree.KEYVAL_c, Tree.KEYVAL_C]:
                widget.add_selected_files_to_clipboard()
                return True
        elif event.keyval == Tree.KEYVAL_ESCAPE:
            widget.get_selection().unselect_all()
            return True
        return False
    @staticmethod
    def search_equal_func(model, column, key, model_iter, _data=None):
        text = model.fs_path(model_iter)
        return text.find(key) == -1
    _FILE_ICON = {True : gtk.STOCK_DIRECTORY, False : gtk.STOCK_FILE}
    @classmethod
    def _get_status_deco(cls, status=None):
        try:
            return ifce.SCM.status_deco_map[status]
        except:
            return ifce.SCM.status_deco_map[None]
    @classmethod
    def _generate_row_tuple(cls, data, isdir):
        deco = cls._get_status_deco(data.status)
        row = cls.Model.Row(
            name=data.name,
            is_dir=isdir,
            icon=cls._FILE_ICON[isdir],
            status=data.status,
            related_file_str=cls._get_related_file_str(data),
            style=deco.style,
            foreground=deco.foreground
        )
        return row
    def __init__(self, show_hidden=False, busy_indicator=None, model=None, show_status=True):
        dialogue.BusyIndicatorUser.__init__(self, busy_indicator=busy_indicator)
        self._file_db = None
        ws_event.Listener.__init__(self)
        self.show_hidden_action = gtk.ToggleAction('show_hidden_files', _('Show Hidden Files'),
                                                   _('Show/hide ignored files and those beginning with "."'), None)
        self.show_hidden_action.set_active(show_hidden)
        self.show_hidden_action.connect('toggled', self._toggle_show_hidden_cb)
        self.show_hidden_action.set_menu_item_type(gtk.CheckMenuItem)
        self.show_hidden_action.set_tool_item_type(gtk.ToggleToolButton)
        tlview.TreeView.__init__(self, model=model)
        if not show_status:
            pass # TODO: hide the status column
        self.set_search_equal_func(self.search_equal_func)
        ws_actions.AGandUIManager.__init__(self, selection=self.get_selection(), popup="/files_popup")
        self.connect("row-expanded", self.model.on_row_expanded_cb)
        self.connect("row-collapsed", self.model.on_row_collapsed_cb)
        self.connect("button_press_event", self._handle_button_press_cb)
        self.connect("key_press_event", self._handle_key_press_cb)
        self.get_selection().set_select_function(self._dirs_not_selectable, full=True)
        self.repopulate()
    def populate_action_groups(self):
        self.action_groups[actions.AC_DONT_CARE].add_action(self.show_hidden_action)
        self.action_groups[actions.AC_DONT_CARE].add_actions(
            [
                ('refresh_files', gtk.STOCK_REFRESH, _('_Refresh Files'), None,
                 _('Refresh/update the file tree display'), self.update),
            ])
    @property
    def _populate_all(self):
        return self.AUTO_EXPAND
    @property
    def show_hidden(self):
        return self.show_hidden_action.get_active()
    @show_hidden.setter
    def show_hidden(self, new_value):
        self.show_hidden_action.set_active(new_value)
        self._update_dir('', None)
    def _dirs_not_selectable(self, selection, model, path, is_selected, _arg=None):
        if not is_selected:
            return not model.get_value_named(model.get_iter(path), 'is_dir')
        return True
    def _toggle_show_hidden_cb(self, toggleaction):
        self.show_busy()
        self._update_dir('', None)
        self.unshow_busy()
    def _get_dir_contents(self, dirpath):
        return self._file_db.dir_contents(dirpath, self.show_hidden_action.get_active())
    def _row_expanded(self, dir_iter):
        return self.row_expanded(self.model.get_path(dir_iter))
    def _populate(self, dirpath, parent_iter):
        dirs, files = self._get_dir_contents(dirpath)
        for dirdata in dirs:
            row_tuple = self._generate_row_tuple(dirdata, True)
            dir_iter = self.model.append(parent_iter, row_tuple)
            if self._populate_all:
                self._populate(os.path.join(dirpath, dirdata.name), dir_iter)
                if self.AUTO_EXPAND:
                    self.expand_row(self.model.get_path(dir_iter), True)
            else:
                self.model.insert_place_holder(dir_iter)
        for filedata in files:
            row_tuple = self._generate_row_tuple(filedata, False)
            dummy = self.model.append(parent_iter, row_tuple)
        if parent_iter is not None:
            self.model.insert_place_holder_if_needed(parent_iter)
    def get_iter_for_filepath(self, filepath):
        pathparts = fsdb.split_path(filepath)
        child_iter = self.model.get_iter_first()
        for index in range(len(pathparts) - 1):
            while child_iter is not None:
                if self.model.get_value_named(child_iter, 'name') == pathparts[index]:
                    tpath = self.model.get_path(child_iter)
                    if not self.row_expanded(tpath):
                        self.expand_row(tpath, False)
                    child_iter = self.model.iter_children(child_iter)
                    break
                child_iter = self.model.iter_next(child_iter)
        while child_iter is not None:
            if self.model.get_value_named(child_iter, 'name') == pathparts[-1]:
                return child_iter
            child_iter = self.model.iter_next(child_iter)
        return None
    def select_filepaths(self, filepaths):
        seln = self.get_selection()
        seln.unselect_all()
        for filepath in filepaths:
            seln.select_iter(self.get_iter_for_filepath(filepath))
    def _update_dir(self, dirpath, parent_iter=None):
        changed = False
        if parent_iter is None:
            child_iter = self.model.get_iter_first()
        else:
            child_iter = self.model.iter_children(parent_iter)
            if child_iter:
                if self.model.get_value_named(child_iter, "name") is None:
                    child_iter = self.model.iter_next(child_iter)
        dirs, files = self._get_dir_contents(dirpath)
        dead_entries = []
        for dirdata in dirs:
            row_tuple = self._generate_row_tuple(dirdata, True)
            while (child_iter is not None) and self.model.get_value_named(child_iter, 'is_dir') and (self.model.get_value_named(child_iter, 'name') < dirdata.name):
                dead_entries.append(child_iter)
                child_iter = self.model.iter_next(child_iter)
            if child_iter is None:
                dir_iter = self.model.append(parent_iter, row_tuple)
                changed = True
                if self._populate_all:
                    self._update_dir(os.path.join(dirpath, dirdata.name), dir_iter)
                    if self.AUTO_EXPAND:
                        self.expand_row(self.model.get_path(dir_iter), True)
                else:
                    self.model.insert_place_holder(dir_iter)
                continue
            name = self.model.get_value_named(child_iter, "name")
            if (not self.model.get_value_named(child_iter, "is_dir")) or (name > dirdata.name):
                dir_iter = self.model.insert_before(parent_iter, child_iter, row_tuple)
                changed = True
                if self._populate_all:
                    self._update_dir(os.path.join(dirpath, dirdata.name), dir_iter)
                    if self.AUTO_EXPAND:
                        self.expand_row(self.model.get_path(dir_iter), True)
                else:
                    self.model.insert_place_holder(dir_iter)
                continue
            changed |= self.model.get_value_named(child_iter, "icon") != row_tuple.icon
            self.model.update_iter_row_tuple(child_iter, row_tuple)
            if self._populate_all or self._row_expanded(child_iter):
                changed |= self._update_dir(os.path.join(dirpath, name), child_iter)
            child_iter = self.model.iter_next(child_iter)
        while (child_iter is not None) and self.model.get_value_named(child_iter, 'is_dir'):
            dead_entries.append(child_iter)
            child_iter = self.model.iter_next(child_iter)
        for filedata in files:
            row_tuple = self._generate_row_tuple(filedata, False)
            while (child_iter is not None) and (self.model.get_value_named(child_iter, 'name') < filedata.name):
                dead_entries.append(child_iter)
                child_iter = self.model.iter_next(child_iter)
            if child_iter is None:
                dummy = self.model.append(parent_iter, row_tuple)
                changed = True
                continue
            if self.model.get_value_named(child_iter, "name") > filedata.name:
                dummy = self.model.insert_before(parent_iter, child_iter, row_tuple)
                changed = True
                continue
            changed |= self.model.get_value_named(child_iter, "icon") != row_tuple.icon
            self.model.update_iter_row_tuple(child_iter, row_tuple)
            child_iter = self.model.iter_next(child_iter)
        while child_iter is not None:
            dead_entries.append(child_iter)
            child_iter = self.model.iter_next(child_iter)
        changed |= len(dead_entries) > 0
        for dead_entry in dead_entries:
            self.model.recursive_remove(dead_entry)
        if parent_iter is not None:
            self.model.insert_place_holder_if_needed(parent_iter)
        return changed
    @staticmethod
    def _get_file_db():
        assert False, '_get_file_db() must be defined in descendants'
    def repopulate(self, _arg=None):
        self.show_busy()
        self._file_db = self._get_file_db()
        self.model.clear()
        self._populate('', self.model.get_iter_first())
        self.unshow_busy()
    def update(self, _arg=None):
        self.show_busy()
        self._file_db = self._get_file_db()
        self._update_dir('', None)
        self.unshow_busy()
    def get_selected_files(self):
        store, selection = self.get_selection().get_selected_rows()
        return [store.fs_path(store.get_iter(x)) for x in selection]
    def add_selected_files_to_clipboard(self, clipboard=None):
        if not clipboard:
            clipboard = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)
        sel = utils.file_list_to_string(self.get_selected_files())
        clipboard.set_text(sel)
    def get_filepaths_in_dir(self, dirname, show_hidden=True, recursive=True):
        subdirs, files = self._file_db.dir_contents(dirname, show_hidden=show_hidden)
        filepaths = [os.path.join(dirname, fdata.name) for fdata in files]
        if recursive:
            for subdir in subdirs:
                filepaths += self.get_filepaths_in_dir(os.path.join(dirname, subdir.name), recursive)
        return filepaths
    def get_file_paths(self):
        return self.model.get_file_paths()

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
    <placeholder name='filter_options'>
    <menuitem action="show_hidden_files"/>
    </placeholder>
  </popup>
</ui>
'''

class CwdFileTreeView(Tree):
    def __init__(self, busy_indicator, model=None, show_hidden=False, show_status=False):
        self._os_file_db = fsdb.OsSnapshotFileDb()
        Tree.__init__(self, busy_indicator=busy_indicator, model=model, show_hidden=show_hidden, show_status=show_status)
        self.ui_manager.add_ui_from_string(CWD_UI_DESCR)
    def populate_action_groups(self):
        Tree.populate_action_groups(self)
        self.action_groups[actions.AC_SELN_MADE].add_actions(
            [
                ("edit_files", gtk.STOCK_EDIT, _('_Edit'), None,
                 _('Edit the selected file(s)'), self.edit_selected_files_acb),
                ("delete_files", gtk.STOCK_DELETE, _('_Delete'), None,
                 _('Delete the selected file(s) from the repository'), self.delete_selected_files_acb),
            ])
        self.action_groups[actions.AC_DONT_CARE].add_actions(
            [
                ("new_file", gtk.STOCK_NEW, _('_New'), None,
                 _('Create a new file and open for editing'), self.create_new_file_acb),
            ])
    def _edit_named_files_extern(self, file_list):
        text_edit.edit_files_extern(file_list)
    def edit_selected_files_acb(self, _menu_item):
        self._edit_named_files_extern(self.get_selected_files())
    def create_new_file(self, new_file_name, open_for_edit=False):
        self.show_busy()
        result = utils.create_file(new_file_name, ifce.log)
        self.unshow_busy()
        dialogue.report_any_problems(result)
        if open_for_edit:
            self._edit_named_files_extern([new_file_name])
        return result
    def create_new_file_acb(self, _menu_item):
        dialog = gtk.FileChooserDialog(_('New File'), dialogue.main_window,
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
            ifce.log.start_cmd(_('Deleting: {0}').format(utils.file_list_to_string(file_list)))
        serr = ""
        for filename in file_list:
            try:
                os.remove(filename)
                if ifce.log:
                    ifce.log.append_stdout(_('Deleted: {0}\n').format(filename))
            except os.error as value:
                errmsg = ("%s: %s" + os.linesep) % (value[1], filename)
                serr += errmsg
                if ifce.log:
                    ifce.log.append_stderr(errmsg)
        if ifce.log:
            ifce.log.end_cmd()
        ws_event.notify_events(ws_event.FILE_DEL)
        if serr:
            return cmd_result.Result(cmd_result.ERROR, "", serr)
        return cmd_result.Result(cmd_result.OK, "", "")
    def _delete_named_files(self, file_list, ask=True):
        if not ask or dialogue.confirm_list_action(file_list, _('About to be deleted. OK?')):
            self.show_busy()
            result = self.delete_files(file_list)
            self.unshow_busy()
            dialogue.report_any_problems(result)
    def delete_selected_files_acb(self, _menu_item):
        self._delete_named_files(self.get_selected_files())
    def _get_file_db(self):
        return self._os_file_db

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
      <menuitem action="scm_extdiff_files_selection"/>
      <menuitem action="scm_move_files_selection"/>
    </placeholder>
    <placeholder name="selection_not_patched">
      <menuitem action="scm_resolve_files_selection"/>
      <menuitem action="scm_mark_resolved_files_selection"/>
      <menuitem action="scm_mark_unresolved_files_selection"/>
      <menuitem action="scm_revert_files_selection"/>
      <menuitem action="scm_commit_files_selection"/>
    </placeholder>
    <placeholder name="unique_selection">
      <menuitem action="scm_rename_file"/>
    </placeholder>
    <placeholder name="no_selection">
      <menuitem action="scm_diff_files_all"/>
      <menuitem action="scm_extdiff_files_all"/>
    </placeholder>
    <placeholder name="no_selection_not_patched">
      <menuitem action="scm_revert_files_all"/>
      <menuitem action="scm_commit_files_all"/>
    </placeholder>
    <separator/>
    <placeholder name='filter_options'>
    <menuitem action="hide_clean_files" position='top'/>
    <menuitem action="show_hidden_files"/>
    </placeholder>
  </popup>
</ui>
'''
def _check_if_force(result):
    return dialogue.ask_force_or_cancel(result) == dialogue.Response.FORCE

class ScmCwdFileTreeView(CwdFileTreeView):
    def __init__(self, busy_indicator=None, show_hidden=False):
        self.hide_clean_action = gtk.ToggleAction('hide_clean_files', _('Hide Clean Files'),
                                                   _('Show/hide "clean" files'), None)
        self.hide_clean_action.set_active(False)
        self.hide_clean_action.connect('toggled', self._toggle_hide_clean_cb)
        self.hide_clean_action.set_menu_item_type(gtk.CheckMenuItem)
        self.hide_clean_action.set_tool_item_type(gtk.ToggleToolButton)
        CwdFileTreeView.__init__(self, busy_indicator=busy_indicator, model=None, show_hidden=show_hidden, show_status=True)
        self.add_notification_cb(ws_event.CHECKOUT|ws_event.FILE_CHANGES, self.update),
        self.add_notification_cb(ws_event.CHANGE_WD, self.update_for_chdir),
        self.add_notification_cb(ws_event.AUTO_UPDATE, self.auto_update)
        self.ui_manager.add_ui_from_string(SCM_CWD_UI_DESCR)
        if not ifce.SCM.get_extension_enabled("extdiff"):
            self.get_conditional_action("scm_extdiff_files_selection").set_visible(False)
            self.get_conditional_action("scm_extdiff_files_all").set_visible(False)
        if tortoise.IS_AVAILABLE:
            self.action_groups[actions.AC_DONT_CARE].add_action(tortoise.FILE_MENU)
            for condition in tortoise.FILE_GROUP_PARTIAL_ACTIONS:
                action_list = []
                for action in tortoise.FILE_GROUP_PARTIAL_ACTIONS[condition]:
                    action_list.append(action + tuple([self._tortoise_tool_acb]))
                self.action_groups[condition].add_actions( action_list)
            self.ui_manager.add_ui_from_string(tortoise.FILES_UI_DESCR)
        self.init_action_states()
        self.repopulate()
    def auto_update(self, _arg=None):
        if not self._file_db.is_current():
            ws_event.notify_events(ws_event.FILE_CHANGES)
    def populate_action_groups(self):
        CwdFileTreeView.populate_action_groups(self)
        self.action_groups[actions.AC_DONT_CARE].add_action(self.hide_clean_action)
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_MADE].add_actions(
            [
                ("scm_remove_files", gtk.STOCK_REMOVE, _('_Remove'), None,
                 _('Remove the selected file(s) from the repository'), self.remove_selected_files_acb),
                ("scm_add_files", gtk.STOCK_ADD, _('_Add'), None,
                 _('Add the selected file(s) to the repository'), self.add_selected_files_to_repo_acb),
                ("scm_copy_files_selection", gtk.STOCK_COPY, _('_Copy'), None,
                 _('Copy the selected file(s)'), self.copy_selected_files_acb),
                ("scm_diff_files_selection", icons.STOCK_DIFF, _('_Diff'), None,
                 _('Display the diff for selected file(s)'), self.diff_selected_files_acb),
                ("scm_extdiff_files_selection", icons.STOCK_DIFF, _('E_xtdiff'), None,
                 _('Launch extdiff for selected file(s)'), self.extdiff_selected_files_acb),
                ("scm_move_files_selection", icons.STOCK_RENAME, _('_Move/Rename'), None,
                 _('Move the selected file(s)'), self.move_selected_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + ws_actions.AC_NOT_PMIC + actions.AC_SELN_MADE].add_actions(
            [
                ("scm_resolve_files_selection", icons.STOCK_RESOLVE, _('Re_solve'), None,
                 _('Resolve merge conflicts in the selected file(s)'), self.resolve_selected_files_acb),
               ("scm_mark_resolved_files_selection", icons.STOCK_MARK_RESOLVE, _('_Mark Resolved'), None,
                 _('Mark the selected file(s) as having had merge conflict resolved'), self.mark_resolved_selected_files_acb),
                ("scm_mark_unresolved_files_selection", icons.STOCK_MARK_UNRESOLVE, _('Mark _Unresolved'), None,
                 _('Mark the selected file(s) as having unresolved merge conflicts'), self.mark_unresolved_selected_files_acb),
                ("scm_revert_files_selection", icons.STOCK_REVERT, _('Rever_t'), None,
                 _('Revert changes in the selected file(s)'), self.revert_selected_files_acb),
                ("scm_commit_files_selection", icons.STOCK_COMMIT, _('_Commit'), None,
                 _('Commit changes for selected file(s)'), self.commit_selected_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_UNIQUE].add_actions(
           [
                ("scm_rename_file", icons.STOCK_RENAME, _('Re_name/Move'), None,
                 _('Rename/move the selected file'), self.move_selected_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_NONE].add_actions(
            [
                ("scm_add_files_all", gtk.STOCK_ADD, _('_Add all'), None,
                 _('Add all files to the repository'), self.add_all_files_to_repo_acb),
                ("scm_diff_files_all", icons.STOCK_DIFF, _('_Diff'), None,
                 _('Display the diff for all changes'), self.diff_selected_files_acb),
                ("scm_extdiff_files_all", icons.STOCK_DIFF, _('E_xtdiff'), None,
                 _('Launch extdiff for all changes'), self.extdiff_selected_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + ws_actions.AC_NOT_PMIC + actions.AC_SELN_NONE].add_actions(
            [
                ("scm_revert_files_all", icons.STOCK_REVERT, _('Rever_t'), None,
                 _('Revert all changes in working directory'), self.revert_all_files_acb),
                ("scm_commit_files_all", icons.STOCK_COMMIT, _('_Commit'), None,
                 _('Commit all changes'), self.commit_all_changes_acb),
            ])
        self.action_groups[actions.AC_DONT_CARE].add_actions(
            [
                ("menu_files", None, _('_Files')),
            ])
    @property
    def _populate_all(self):
        return ifce.in_valid_repo
    def update_for_chdir(self):
        self.show_busy()
        self.repopulate()
        self.unshow_busy()
    def _tortoise_tool_acb(self, action=None):
        tortoise.run_tool_for_files(action, self.get_selected_files())
    def new_file(self, new_file_name):
        result = utils.create_file(new_file_name, ifce.log)
        if result.ecode == 0:
            result = ifce.SCM.do_add_files([new_file_name])
        return result
    def delete_files(self, file_list):
        return ifce.SCM.do_delete_files(file_list)
    def get_scm_name(self):
        return ifce.SCM.name
    def _remove_named_files(self, file_list, ask=True):
        if not ask or dialogue.confirm_list_action(file_list, _('About to be removed. OK?')):
            self.show_busy()
            result = ifce.SCM.do_remove_files(file_list)
            self.unshow_busy()
            if cmd_result.suggests_force(result):
                if _check_if_force(result):
                    self.show_busy()
                    result = ifce.SCM.do_remove_files(file_list, force=True)
                    self.unshow_busy()
                else:
                    return
            dialogue.report_any_problems(result)
    def remove_selected_files_acb(self, _menu_item):
        self._remove_named_files(self.get_selected_files())
    def add_files_to_repo(self, file_list):
        self.show_busy()
        result = ifce.SCM.do_add_files(file_list)
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def add_all_files_to_repo(self):
        operation = ifce.SCM.do_add_files
        self.show_busy()
        result = operation([], dry_run=True)
        self.unshow_busy()
        if result.ecode != cmd_result.OK:
            dialogue.report_any_problems(result)
            return
        if dialogue.confirm_list_action('\n'.join(result[1:]).splitlines(), _('About to be actioned. OK?')):
            self.show_busy()
            result = operation([], dry_run=False)
            self.unshow_busy()
            dialogue.report_any_problems(result)
    def add_selected_files_to_repo_acb(self, _menu_item):
        self.add_files_to_repo(self.get_selected_files())
    def add_all_files_to_repo_acb(self, _menu_item):
        self.add_all_files_to_repo()
    def commit_changes(self, file_list):
        dialog = ScmCommitDialog(parent=dialogue.main_window, filelist=file_list)
        dialog.show()
    def commit_selected_files_acb(self, _menu_item):
        self.commit_changes(self.get_selected_files())
    def commit_all_changes_acb(self, _menu_item):
        self.commit_changes(None)
    def _get_target(self, src_file_list):
        if len(src_file_list) > 1:
            mode = gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER
        else:
            mode = gtk.FILE_CHOOSER_ACTION_SAVE
        dialog = gtk.FileChooserDialog(_('Target'), dialogue.main_window, mode,
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
            assert False, _("Invalid operation requested")
        response, target = self._get_target(file_list)
        if response == gtk.RESPONSE_OK:
            force = False
            if ask:
                while True:
                    self.show_busy()
                    result = operation(file_list, target, force=force, dry_run=True)
                    self.unshow_busy()
                    if cmd_result.is_less_than_error(result):
                        is_ok = dialogue.confirm_list_action(result.stdout.splitlines(), _('About to be actioned. OK?'))
                        break
                    elif not force and cmd_result.suggests_force(result):
                        is_ok = force = _check_if_force(result)
                        if not force:
                            return
                    else:
                        dialogue.report_any_problems(result)
                        return
            if not ask or is_ok:
                while True:
                    self.show_busy()
                    result = operation(file_list, target, force=force)
                    self.unshow_busy()
                    if not force and cmd_result.suggests_force(result):
                        force = _check_if_force(result)
                        if not force:
                            return
                        continue
                    break
                dialogue.report_any_problems(result)
    def copy_files(self, file_list, ask=False):
        self._move_or_copy_files(file_list, "c", ask=ask)
    def copy_selected_files_acb(self, _action=None):
        self.copy_files(self.get_selected_files())
    def move_files(self, file_list, ask=True):
        self._move_or_copy_files(file_list, "m", ask=ask)
    def move_selected_files_acb(self, _action=None):
        self.move_files(self.get_selected_files())
    def diff_selected_files_acb(self, _action=None):
        dialog = diff.ScmDiffTextDialog(parent=dialogue.main_window,
                                     file_list=self.get_selected_files())
        dialog.show()
    def extdiff_selected_files_acb(self, _action=None):
        ifce.SCM.launch_extdiff_for_ws(self.get_selected_files())
    def resolve_selected_files_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_resolve_workspace(self.get_selected_files())
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def mark_resolved_selected_files_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_mark_files_resolved(self.get_selected_files())
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def mark_unresolved_selected_files_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_mark_files_unresolved(self.get_selected_files())
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def revert_named_files(self, file_list, ask=True):
        if ask:
            self.show_busy()
            result = ifce.SCM.do_revert_files(file_list, dry_run=True)
            self.unshow_busy()
            if result.ecode == cmd_result.OK:
                if result.stdout:
                    is_ok = dialogue.confirm_list_action(result.stdout.splitlines(), _('About to be actioned. OK?'))
                else:
                    dialogue.inform_user(_('Nothing to revert'))
                    return
            else:
                dialogue.report_any_problems(result)
                return
        else:
            is_ok = True
        if is_ok:
            self.show_busy()
            result = ifce.SCM.do_revert_files(file_list)
            self.unshow_busy()
            dialogue.report_any_problems(result)
    def revert_selected_files_acb(self, _action=None):
        self.revert_named_files(self.get_selected_files())
    def revert_all_files_acb(self, _action=None):
        self.revert_named_files([])
    @staticmethod
    def _get_file_db():
        if ifce.in_valid_repo:
            return ifce.SCM.get_ws_file_db()
        else:
            return self._os_file_db
    def _toggle_hide_clean_cb(self, toggleaction):
        self._update_dir('', None)
    def _get_dir_contents(self, dirpath):
        if self._file_db is None:
            return ((), ())
        show_hidden = self.show_hidden_action.get_active()
        if not show_hidden and self.hide_clean_action.get_active():
            dirs, files = self._file_db.dir_contents(dirpath, show_hidden)
            return ([ncd for ncd in dirs if ncd.status != hg_mq_ifce.FSTATUS_CLEAN],
                    [ncf for ncf in files if ncf.status != hg_mq_ifce.FSTATUS_CLEAN])
        return self._file_db.dir_contents(dirpath, show_hidden)

class ScmCwdFilesWidget(gtk.VBox):
    def __init__(self, busy_indicator=None, show_hidden=False):
        gtk.VBox.__init__(self)
        # file tree view wrapped in scrolled window
        self.file_tree = ScmCwdFileTreeView(busy_indicator=busy_indicator, show_hidden=show_hidden)
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
        for action_name in ["show_hidden_files", "hide_clean_files"]:
            button = gtk.CheckButton()
            action = self.file_tree.action_groups.get_action(action_name)
            action.connect_proxy(button)
            gutils.set_widget_tooltip_text(button, action.get_property("tooltip"))
            hbox.pack_start(button)
        self.pack_start(hbox, expand=False)
        self.show_all()

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
      <menuitem action="scm_extdiff_files_selection"/>
      <menuitem action="scmch_remove_files"/>
    </placeholder>
    <separator/>
    <placeholder name="unique_selection"/>
    <separator/>
    <placeholder name="no_selection"/>
      <menuitem action="scm_diff_files_all"/>
      <menuitem action="scm_extdiff_files_all"/>
    <separator/>
  </popup>
</ui>
'''

class ScmCommitFileTreeView(Tree):
    class TWSDisplay(diff.TextWidget.TwsLineCountDisplay):
        LABEL = _('File(s) that add TWS: ')
    AUTO_EXPAND = True
    def __init__(self, busy_indicator, show_hidden=True, file_mask=None):
        self.removeds = []
        self._file_mask = [] if file_mask is None else file_mask
        self.tws_display = self.TWSDisplay()
        self.tws_display.set_value(0)
        Tree.__init__(self, busy_indicator=busy_indicator, show_hidden=show_hidden, show_status=True)
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.set_headers_visible(False)
        self.scm_change_merge_id = self.ui_manager.add_ui_from_string(SCM_CHANGE_UI_DESCR)
        self.action_groups.get_action("scmch_undo_remove_files").set_sensitive(False)
        if not ifce.SCM.get_extension_enabled("extdiff"):
            self.action_groups.get_action("scm_extdiff_files_selection").set_visible(False)
            self.action_groups.get_action("scm_extdiff_files_all").set_visible(False)
        self.add_notification_cb(ws_event.AUTO_UPDATE, self.auto_update)
    def auto_update(self, _arg=None):
        if not self._file_db.is_current():
            self.update()
    def populate_action_groups(self):
        Tree.populate_action_groups(self)
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_MADE].add_actions(
            [
                ("scmch_remove_files", gtk.STOCK_DELETE, _('_Remove'), None,
                 _('Remove the selected files from the change set'), self._remove_selected_files_acb),
                ("scm_diff_files_selection", icons.STOCK_DIFF, _('_Diff'), None,
                 _('Display the diff for selected file(s)'), self._diff_selected_files_acb),
                ("scm_extdiff_files_selection", icons.STOCK_DIFF, _('E_xtdiff'), None,
                 _('Launch extdiff for the selected file(s)'), self._extdiff_selected_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO].add_actions(
            [
                ("scmch_undo_remove_files", gtk.STOCK_UNDO, _('_Undo'), None,
                 _('Undo the last remove'), self._undo_last_remove_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_NONE].add_actions(
            [
                ("scm_diff_files_all", icons.STOCK_DIFF, _('_Diff'), None,
                 _('Display the diff for all changes'), self._diff_all_files_acb),
                ("scm_extdiff_files_all", icons.STOCK_DIFF, _('E_xtdiff'), None,
                 _('Launch etxdiff for all changes'), self._extdiff_all_files_acb),
            ])
    def _remove_selected_files_acb(self, _menu_item):
        self.show_busy()
        file_mask = self.file_mask if self.file_mask else self.get_file_paths()
        selected_files = self.get_selected_files()
        for sel_file in selected_files:
            del file_mask[file_mask.index(sel_file)]
        self.file_mask = file_mask
        self.removeds.append(selected_files)
        self.action_groups.get_action("scmch_undo_remove_files").set_sensitive(True)
        self.unshow_busy()
        self.update()
    def _undo_last_remove_acb(self, _menu_item):
        self.show_busy()
        restore_files = self.removeds[-1]
        del self.removeds[-1]
        self.action_groups.get_action("scmch_undo_remove_files").set_sensitive(len(self.removeds) > 0)
        file_mask = self.file_mask
        for res_file in restore_files:
            file_mask.append(res_file)
        self.file_mask = file_mask
        self.unshow_busy()
        self.update()
    def _diff_selected_files_acb(self, _action=None):
        parent = dialogue.main_window
        dialog = diff.ScmDiffTextDialog(parent=parent, file_list=self.get_selected_files())
        dialog.show()
    def _diff_all_files_acb(self, _action=None):
        parent = dialogue.main_window
        dialog = diff.ScmDiffTextDialog(parent=parent, file_list=self.file_mask)
        dialog.show()
    def _extdiff_selected_files_acb(self, _action=None):
        ifce.SCM.launch_extdiff_for_ws(file_list=self.get_selected_files())
    def _extdiff_all_files_acb(self, _action=None):
        ifce.SCM.launch_extdiff_for_ws(file_list=self.file_mask)
    @property
    def file_mask(self):
        return self._file_mask
    @file_mask.setter
    def file_mask(self, file_mask):
        self._file_mask = file_mask
        self.set_tws_file_count()
        self.update()
    def _get_file_db(self):
        return ifce.SCM.get_commit_file_db(self._file_mask)
    def set_tws_file_count(self):
        diff_text = ifce.SCM.get_commit_diff(self._file_mask)
        epatch = patchlib.Patch.parse_text(diff_text)
        self.tws_display.set_value(len(epatch.report_trailing_whitespace()))

class ScmCommitWidget(gtk.VPaned, ws_event.Listener):
    class SummaryWidget(text_edit.MessageWidget):
        UI_DESCR = \
            '''
            <ui>
              <menubar name="change_summary_menubar">
                <menu name="change_summary_menu" action="menu_summary">
                  <menuitem action="text_edit_save_to_file"/>
                  <menuitem action="text_edit_save_as"/>
                  <menuitem action="text_edit_load_fm_file"/>
                  <menuitem action="text_edit_load_from"/>
                  <menuitem action="text_edit_insert_from"/>
                </menu>
              </menubar>
              <toolbar name="change_summary_toolbar">
                <toolitem action="text_edit_ack"/>
                <toolitem action="text_edit_sign_off"/>
                <toolitem action="text_edit_author"/>
                <toolitem action="text_edit_toggle_auto_save"/>
              </toolbar>
            </ui>
            '''
        def __init__(self, save_file_name=None, auto_save=True):
            text_edit.MessageWidget.__init__(self, save_file_name=save_file_name, auto_save=auto_save)
            menubar = self.ui_manager.get_widget("/change_summary_menubar")
            self.top_hbox.pack_start(menubar, fill=True, expand=False)
            toolbar = self.ui_manager.get_widget("/change_summary_toolbar")
            toolbar.set_style(gtk.TOOLBAR_BOTH)
            toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
            self.top_hbox.pack_end(toolbar, fill=False, expand=False)
        def populate_action_groups(self):
            text_edit.MessageWidget.populate_action_groups(self)
            self.action_groups[actions.AC_DONT_CARE].add_action(gtk.Action("menu_summary", _("Summary"), _(""), None))
    def __init__(self, busy_indicator, file_mask=None):
        gtk.VPaned.__init__(self)
        ws_event.Listener.__init__(self)
        # TextView for change message
        self.summary_widget = self.SummaryWidget()
        self.add1(self.summary_widget)
        # TreeView of files in change set
        self.files = ScmCommitFileTreeView(busy_indicator=busy_indicator, show_hidden=True, file_mask=file_mask)
        vbox = gtk.VBox()
        vbox.pack_start(gtk.Label(_('Files')), expand=False)
        x, y = self.files.tree_to_widget_coords(480, 240)
        self.files.set_size_request(x, y)
        vbox.pack_start(gutils.wrap_in_scrolled_window(self.files))
        vbox.show_all()
        self.add2(vbox)
        self.show_all()
        self.set_focus_child(self.summary_widget.view)
    def get_msg(self):
        return self.summary_widget.get_contents()
    @property
    def file_mask(self):
        return self.files.file_mask
    def do_commit(self):
        result = ifce.SCM.do_commit_change(self.get_msg(), self.file_mask)
        dialogue.report_any_problems(result)
        return cmd_result.is_less_than_error(result[0])

class ScmCommitDialog(dialogue.AmodalDialog):
    def __init__(self, parent, filelist=None):
        flags = gtk.DIALOG_DESTROY_WITH_PARENT
        dialogue.AmodalDialog.__init__(self, None, parent, flags)
        self.set_title(_('Commit Changes: %s') % utils.cwd_rel_home())
        self.commit_widget = ScmCommitWidget(busy_indicator=self, file_mask=filelist)
        self.vbox.pack_start(self.commit_widget)
        self.set_focus_child(self.commit_widget.summary_widget.view)
        tws_display = self.commit_widget.files.tws_display
        self.action_area.pack_end(tws_display, expand=False, fill=False)
        self.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                       gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.connect('response', self._handle_response_cb)
    def get_mesg_and_files(self):
        return (self.commit_widget.get_msg(), self.commit_widget.file_mask)
    def update_files(self):
        self.commit_widget.files.update()
    def _finish_up(self, clear_save=False):
        self.show_busy()
        self.commit_widget.summary_widget.finish_up(clear_save)
        self.unshow_busy()
        self.destroy()
    def _handle_response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_OK:
            if self.commit_widget.do_commit():
                self._finish_up(clear_save=True)
            else:
                dialog.update_files()
        elif self.commit_widget.summary_widget.bfr.get_modified():
            if self.commit_widget.summary_widget.get_auto_save():
                self._finish_up()
            else:
                qtn = _('Unsaved changes to summary will be lost.\n\nCancel anyway?')
                if dialogue.ask_yes_no(qtn):
                    self._finish_up()
        else:
            self._finish_up()

class GenericPatchFileTreeView(CwdFileTreeView):
    AUTO_EXPAND = True
    def __init__(self, patch=None, busy_indicator=None, model=None, show_status=True):
        self._patch = patch
        self._null_file_db = fsdb.NullFileDb()
        CwdFileTreeView.__init__(self, busy_indicator=busy_indicator, model=model, show_status=show_status)
    @property
    def patch(self):
        return self._patch
    @patch.setter
    def patch(self, new_patch):
        self._patch = new_patch
        self.repopulate()
    def _get_file_db(self):
        if ifce.in_valid_repo:
            return ifce.PM.get_patch_file_db(self._patch)
        else:
            return self._null_file_db

PATCH_FILES_UI_DESCR = \
'''
<ui>
  <menubar name="files_menubar">
  </menubar>
  <popup name="files_popup">
    <placeholder name="selection_indifferent">
    </placeholder>
    <placeholder name="selection">
      <menuitem action="pm_diff_files_selection"/>
      <menuitem action="pm_extdiff_files_selection"/>
    </placeholder>
    <placeholder name="unique_selection">
    </placeholder>
    <placeholder name="no_selection">
      <menuitem action="pm_diff_files_all"/>
      <menuitem action="pm_extdiff_files_all"/>
    </placeholder>
  </popup>
</ui>
'''

class PatchFileTreeView(GenericPatchFileTreeView):
    def __init__(self, busy_indicator=None, patch=None, model=None):
        GenericPatchFileTreeView.__init__(self, patch=patch, busy_indicator=busy_indicator, model=model, show_status=True)
        if not ifce.SCM.get_extension_enabled("extdiff") or not ifce.PM.get_patch_is_applied(self._patch):
            self.action_groups.get_action("pm_extdiff_files_selection").set_visible(False)
            self.action_groups.get_action("pm_extdiff_files_all").set_visible(False)
        self.show_hidden_action.set_visible(False)
        self.show_hidden_action.set_sensitive(False)
        self.action_groups.get_action("new_file").set_visible(False)
        self.action_groups.get_action("edit_files").set_visible(False)
        self.action_groups.get_action("delete_files").set_visible(False)
        self.repopulate()
        self.ui_manager.add_ui_from_string(PATCH_FILES_UI_DESCR)
    def populate_action_groups(self):
        GenericPatchFileTreeView.populate_action_groups(self)
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_MADE].add_actions(
            [
                ("pm_diff_files_selection", icons.STOCK_DIFF, _('_Diff'), None,
                 _('Display the diff for selected file(s)'), self.diff_selected_files_acb),
                ("pm_extdiff_files_selection", icons.STOCK_DIFF, _('E_xtdiff'), None,
                 _('Launch extdiff for selected file(s)'), self.extdiff_selected_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_NONE].add_actions(
            [
                ("pm_diff_files_all", icons.STOCK_DIFF, _('_Diff'), None,
                 _('Display the diff for all changes'), self.diff_all_files_acb),
                ("pm_extdiff_files_all", icons.STOCK_DIFF, _('E_xtdiff'), None,
                 _('Launch extdiff for all changes'), self.extdiff_all_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO].add_actions(
            [
                ("menu_files", None, _('_Files')),
            ])
    def diff_selected_files_acb(self, _action=None):
        dialog = diff.PmDiffTextDialog(parent=dialogue.main_window,
                                       patch=self._patch,
                                       file_list=self.get_selected_files())
        dialog.show()
    def diff_all_files_acb(self, _action=None):
        dialog = diff.PmDiffTextDialog(parent=dialogue.main_window, patch=self._patch)
        dialog.show()
    def extdiff_selected_files_acb(self, _action=None):
        ifce.PM.launch_extdiff_for_patch(self._patch, self.get_selected_files())
    def extdiff_all_files_acb(self, _action=None):
        ifce.PM.launch_extdiff_for_patch(self._patch)

class PatchFilesDialog(dialogue.AmodalDialog):
    def __init__(self, patch):
        dialogue.AmodalDialog.__init__(self, None, None,
                                       gtk.DIALOG_DESTROY_WITH_PARENT,
                                       (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE))
        self.set_title('patch: %s files: %s' % (patch, utils.cwd_rel_home()))
        # file tree view wrapped in scrolled window
        self.file_tree = PatchFileTreeView(busy_indicator=self, patch=patch)
        self.file_tree.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.file_tree.set_headers_visible(False)
        self.file_tree.set_size_request(240, 320)
        self.vbox.pack_start(gutils.wrap_in_scrolled_window(self.file_tree))
        self.connect("response", self._close_cb)
        self.show_all()
    def _close_cb(self, dialog, response_id):
        self.destroy()

PM_FILES_UI_DESCR = \
'''
<ui>
  <menubar name="files_menubar">
    <menu name="files_menu" action="menu_files">
      <menuitem action="new_file"/>
      <menuitem action="refresh_files"/>
      <separator/>
    </menu>
  </menubar>
  <popup name="files_popup">
    <placeholder name="selection_indifferent"/>
    <placeholder name="selection">
      <menuitem action="edit_files"/>
      <menuitem action="delete_files"/>
      <menuitem action="pm_remove_files"/>
      <menuitem action="pm_copy_files_selection"/>
      <menuitem action="pm_diff_files_selection"/>
      <menuitem action="pm_extdiff_files_selection"/>
      <menuitem action="pm_move_files_selection"/>
      <menuitem action="pm_revert_files_selection"/>
    </placeholder>
    <placeholder name="unique_selection">
      <menuitem action="pm_rename_file"/>
    </placeholder>
    <placeholder name="no_selection">
      <menuitem action="pm_diff_files_all"/>
      <menuitem action="pm_extdiff_files_all"/>
      <menuitem action="pm_revert_files_all"/>
    </placeholder>
  </popup>
</ui>
'''

class TopPatchFileTreeView(GenericPatchFileTreeView):
    def __init__(self, busy_indicator=None):
        GenericPatchFileTreeView.__init__(self, model=None, show_status=True, busy_indicator=busy_indicator)
        self.show_hidden_action.set_visible(False)
        self.show_hidden_action.set_sensitive(False)
        if not ifce.SCM.get_extension_enabled("extdiff"):
            self.action_groups.get_action("pm_extdiff_files_selection").set_visible(False)
            self.action_groups.get_action("pm_extdiff_files_all").set_visible(False)
        self.repopulate()
        self.ui_manager.add_ui_from_string(PM_FILES_UI_DESCR)
        self.add_notification_cb(ws_event.CHECKOUT|ws_event.CHANGE_WD, self.repopulate)
        self.add_notification_cb(ws_event.FILE_CHANGES, self.update)
        self.init_action_states()
    def populate_action_groups(self):
        GenericPatchFileTreeView.populate_action_groups(self)
        self.action_groups.move_action(ws_actions.AC_IN_REPO + ws_actions.AC_PMIC, "new_file")
        self.action_groups[ws_actions.AC_IN_REPO + ws_actions.AC_PMIC + actions.AC_SELN_MADE].add_actions(
            [
                ("pm_remove_files", gtk.STOCK_REMOVE, _('_Remove'), None,
                 _('Remove the selected file(s) from the patch'), self.remove_selected_files_acb),
                ("pm_copy_files_selection", gtk.STOCK_COPY, _('_Copy'), None,
                 _('Copy the selected file(s)'), self.copy_selected_files_acb),
                ("pm_diff_files_selection", icons.STOCK_DIFF, _('_Diff'), None,
                 _('Display the diff for selected file(s)'), self.diff_selected_files_acb),
                ("pm_extdiff_files_selection", icons.STOCK_DIFF, _('E_xtdiff'), None,
                 _('Launch extdiff for selected file(s)'), self.extdiff_selected_files_acb),
                ("pm_move_files_selection", gtk.STOCK_PASTE, _('_Move/Rename'), None,
                 _('Move the selected file(s)'), self.move_selected_files_acb),
                ("pm_revert_files_selection", gtk.STOCK_UNDO, _('Rever_t'), None,
                 _('Revert changes in the selected file(s)'), self.revert_selected_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + ws_actions.AC_PMIC + actions.AC_SELN_UNIQUE].add_actions(
            [
                ("pm_rename_file", gtk.STOCK_PASTE, _('Re_name/Move'), None,
                 _('Rename/move the selected file'), self.move_selected_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + ws_actions.AC_PMIC + actions.AC_SELN_NONE].add_actions(
            [
                ("pm_diff_files_all", icons.STOCK_DIFF, _('_Diff'), None,
                 _('Display the diff for all changes'), self.diff_all_files_acb),
                ("pm_extdiff_files_all", icons.STOCK_DIFF, _('E_xtdiff'), None,
                 _('Launch extdiff for all changes'), self.extdiff_all_files_acb),
                ("pm_revert_files_all", gtk.STOCK_UNDO, _('Rever_t'), None,
                 _('Revert all changes in working directory'), self.revert_all_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO].add_actions(
            [
                ("menu_files", None, _('_Files')),
            ])
    def create_new_file(self, new_file_name, open_for_edit=False):
        result = GenericPatchFileTreeView.create_new_file(self, new_file_name, open_for_edit)
        if not result[0]:
            result = ifce.PM.do_add_files([new_file_name])
            dialogue.report_any_problems(result)
        return result
    def delete_files(self, file_list):
        return ifce.PM.do_delete_files(file_list)
    def _remove_named_files(self, file_list, ask=True):
        if not ask or dialogue.confirm_list_action(file_list, _('About to be removed. OK?')):
            self.show_busy()
            result = ifce.PM.do_remove_files(file_list)
            self.unshow_busy()
            if cmd_result.suggests_force(result):
                if _check_if_force(result):
                    self.show_busy()
                    result = ifce.PM.do_remove_files(file_list, force=True)
                    self.unshow_busy()
                else:
                    return
            dialogue.report_any_problems(result)
    def remove_selected_files_acb(self, _menu_item):
        self._remove_named_files(self.get_selected_files())
    def _get_target(self, src_file_list):
        if len(src_file_list) > 1:
            mode = gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER
        else:
            mode = gtk.FILE_CHOOSER_ACTION_SAVE
        dialog = gtk.FileChooserDialog(_('Target'), dialogue.main_window, mode,
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
        assert reqop in ["c", "m"]
        if reqop == "c":
            operation = ifce.PM.do_copy_files
        else:
            operation = ifce.PM.do_move_files
        response, target = self._get_target(file_list)
        if response == gtk.RESPONSE_OK:
            force = False
            if ask:
                while True:
                    self.show_busy()
                    result = operation(file_list, target, force=force,
                                                dry_run=True)
                    self.unshow_busy()
                    if result.ecode == cmd_result.OK:
                        is_ok = dialogue.confirm_list_action(result.stdout.splitlines(), _('About to be actioned. OK?'))
                        break
                    elif not force and cmd_result.suggests_force(result):
                        is_ok = force = _check_if_force(result)
                        if not force:
                            return
                    else:
                        dialogue.report_any_problems(result)
                        return
            if not ask or is_ok:
                while True:
                    self.show_busy()
                    result = operation(file_list, target, force=force)
                    self.unshow_busy()
                    if not force and cmd_result.suggests_force(result):
                        force = _check_if_force(result)
                        if not force:
                            return
                        continue
                    break
                dialogue.report_any_problems(result)
    def copy_files(self, file_list, ask=False):
        self._move_or_copy_files(file_list, "c", ask=ask)
    def copy_selected_files_acb(self, _action=None):
        self.copy_files(self.get_selected_files())
    def move_files(self, file_list, ask=True):
        self._move_or_copy_files(file_list, "m", ask=ask)
    def move_selected_files_acb(self, _action=None):
        self.move_files(self.get_selected_files())
    def diff_selected_files_acb(self, _action=None):
        dialog = diff.PmDiffTextDialog(parent=dialogue.main_window,
                                       file_list=self.get_selected_files())
        dialog.show()
    def diff_all_files_acb(self, _action=None):
        dialog = diff.PmDiffTextDialog(parent=dialogue.main_window)
        dialog.show()
    def extdiff_selected_files_acb(self, _action=None):
        ifce.PM.launch_extdiff_for_ws(self.get_selected_files())
    def extdiff_all_files_acb(self, _action=None):
        ifce.PM.launch_extdiff_for_ws()
    def revert_named_files(self, file_list, ask=True):
        if ask:
            self.show_busy()
            result = ifce.PM.do_revert_files(file_list, dry_run=True)
            self.unshow_busy()
            if result.ecode == cmd_result.OK:
                if result.stdout:
                    is_ok = dialogue.confirm_list_action(result.stdout.splitlines(), _('About to be actioned. OK?'))
                else:
                    dialogue.inform_user(_('Nothing to revert'))
                    return
            else:
                dialogue.report_any_problems(result)
                return
        else:
            is_ok = True
        if is_ok:
            self.show_busy()
            result = ifce.PM.do_revert_files(file_list)
            self.unshow_busy()
            dialogue.report_any_problems(result)
    def revert_selected_files_acb(self, _action=None):
        self.revert_named_files(self.get_selected_files())
    def revert_all_files_acb(self, _action=None):
        self.revert_named_files([])
