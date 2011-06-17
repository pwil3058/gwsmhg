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

import os, os.path, gtk, gobject, collections

from gwsmhg_pkg import ifce, utils, text_edit, cmd_result, diff, gutils
from gwsmhg_pkg import tortoise, icons, ws_event, dialogue, tlview
from gwsmhg_pkg import actions, fsdb, hg_mq_ifce

Row = collections.namedtuple('Row',
    ['name', 'is_dir', 'style', 'foreground', 'icon', 'status', 'origin'])

_MODEL_TEMPLATE = Row(
    name=gobject.TYPE_STRING,
    is_dir=gobject.TYPE_BOOLEAN,
    style=gobject.TYPE_INT,
    foreground=gobject.TYPE_STRING,
    icon=gobject.TYPE_STRING,
    status=gobject.TYPE_STRING,
    origin=gobject.TYPE_STRING
)

_NAME = tlview.model_col(_MODEL_TEMPLATE, 'name')
_IS_DIR = tlview.model_col(_MODEL_TEMPLATE, 'is_dir')
_STYLE = tlview.model_col(_MODEL_TEMPLATE, 'style')
_FOREGROUND = tlview.model_col(_MODEL_TEMPLATE, 'foreground')
_ICON = tlview.model_col(_MODEL_TEMPLATE, 'icon')
_STATUS = tlview.model_col(_MODEL_TEMPLATE, 'status')
_ORIGIN = tlview.model_col(_MODEL_TEMPLATE, 'origin')

_FILE_ICON = {True : gtk.STOCK_DIRECTORY, False : gtk.STOCK_FILE}

def _get_status_deco(status=None):
    try:
        return ifce.SCM.status_deco_map[status]
    except:
        return ifce.SCM.status_deco_map[None]

def _generate_row_tuple(data, isdir=None):
    deco = _get_status_deco(data.status)
    row = Row(
        name=data.name,
        is_dir=isdir,
        icon=_FILE_ICON[isdir],
        status=data.status,
        origin=data.origin,
        style=deco.style,
        foreground=deco.foreground
    )
    return row

class FileTreeStore(tlview.TreeStore):
    def __init__(self, show_hidden=False, populate_all=False, auto_expand=False, view=None):
        tlview.TreeStore.__init__(self, _MODEL_TEMPLATE)
        self._file_db = None
        # If 'view' this isn't set explicitly it will be set automatically
        # when any row is expanded
        self.view = view
        self._populate_all = populate_all
        self._auto_expand = auto_expand
        self.show_hidden_action = gtk.ToggleAction('show_hidden_files', 'Show Hidden Files',
                                                   'Show/hide ignored files and those beginning with "."', None)
        self.show_hidden_action.set_active(show_hidden)
        self.show_hidden_action.connect('toggled', self._toggle_show_hidden_cb)
        self.show_hidden_action.set_menu_item_type(gtk.CheckMenuItem)
        self.show_hidden_action.set_tool_item_type(gtk.ToggleToolButton)
    def set_view(self, view):
        self.view = view
        if self._expand_new_rows():
            self.view.expand_all()
    def _expand_new_rows(self):
        return self._auto_expand and self.view is not None
    def _row_expanded(self, dir_iter):
        # if view isn't set then assume that we aren't connexted to a view
        # so the row can't be expanded
        if self.view is None:
            return False
        else:
            return self.view.row_expanded(self.get_path(dir_iter))
    def _update_iter_row_tuple(self, fsobj_iter, to_tuple):
        for index in [_STYLE, _FOREGROUND, _STATUS, _ORIGIN]:
            self.set_value(fsobj_iter, index, to_tuple[index])
    def _toggle_show_hidden_cb(self, toggleaction):
        self._update_dir('', None)
    def fs_path(self, fsobj_iter):
        if fsobj_iter is None:
            return None
        parent_iter = self.iter_parent(fsobj_iter)
        name = self.get_value(fsobj_iter, _NAME)
        if parent_iter is None:
            return name
        else:
            if name is None:
                return os.path.join(self.fs_path(parent_iter), '')
            return os.path.join(self.fs_path(parent_iter), name)
    def fs_path_list(self, iter_list):
        return [self.fs_path(fsobj_iter) for fsobj_iter in iter_list]
    def _get_file_paths(self, fsobj_iter, path_list):
        while fsobj_iter != None:
            if not self.get_value(fsobj_iter, _IS_DIR):
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
            while self._recursive_remove(child_iter):
                pass
        return self.remove(fsobj_iter)
    def _remove_place_holder(self, dir_iter):
        child_iter = self.iter_children(dir_iter)
        if child_iter and self.get_value(child_iter, _NAME) is None:
            self.remove(child_iter)
    def _insert_place_holder(self, dir_iter):
        self.append(dir_iter)
    def _insert_place_holder_if_needed(self, dir_iter):
        if self.iter_n_children(dir_iter) == 0:
            self._insert_place_holder(dir_iter)
    def _get_dir_contents(self, dirpath):
        return self._file_db.dir_contents(dirpath, self.show_hidden_action.get_active())
    def _populate(self, dirpath, parent_iter):
        dirs, files = self._get_dir_contents(dirpath)
        for dirdata in dirs:
            row_tuple = _generate_row_tuple(dirdata, True)
            dir_iter = self.append(parent_iter, row_tuple)
            if self._populate_all:
                self._populate(os.path.join(dirpath, dirdata.name), dir_iter)
                if self._expand_new_rows():
                    self.view.expand_row(self.get_path(dir_iter), True)
            else:
                self._insert_place_holder(dir_iter)
        for filedata in files:
            row_tuple = _generate_row_tuple(filedata, False)
            dummy = self.append(parent_iter, row_tuple)
        if parent_iter is not None:
            self._insert_place_holder_if_needed(parent_iter)
    def _update_dir(self, dirpath, parent_iter=None):
        if parent_iter is None:
            child_iter = self.get_iter_first()
        else:
            child_iter = self.iter_children(parent_iter)
            if child_iter:
                if self.get_value(child_iter, _NAME) is None:
                    child_iter = self.iter_next(child_iter)
        dirs, files = self._get_dir_contents(dirpath)
        dead_entries = []
        for dirdata in dirs:
            row_tuple = _generate_row_tuple(dirdata, True)
            while (child_iter is not None) and self.get_value(child_iter, _IS_DIR) and (self.get_value(child_iter, _NAME) < dirdata.name):
                dead_entries.append(child_iter)
                child_iter = self.iter_next(child_iter)
            if child_iter is None:
                dir_iter = self.append(parent_iter, row_tuple)
                if self._populate_all:
                    self._update_dir(os.path.join(dirpath, dirdata.name), dir_iter)
                    if self._expand_new_rows():
                        self.view.expand_row(self.get_path(dir_iter), True)
                else:
                    self._insert_place_holder(dir_iter)
                continue
            name = self.get_value(child_iter, _NAME)
            if (not self.get_value(child_iter, _IS_DIR)) or (name > dirdata.name):
                dir_iter = self.insert_before(parent_iter, child_iter, row_tuple)
                if self._populate_all:
                    self._update_dir(os.path.join(dirpath, dirdata.name), dir_iter)
                    if self._expand_new_rows():
                        self.view.expand_row(self.get_path(dir_iter), True)
                else:
                    self._insert_place_holder(dir_iter)
                continue
            self._update_iter_row_tuple(child_iter, row_tuple)
            if self._populate_all or self._row_expanded(child_iter):
                self._update_dir(os.path.join(dirpath, name), child_iter)
            child_iter = self.iter_next(child_iter)
        while (child_iter is not None) and self.get_value(child_iter, _IS_DIR):
            dead_entries.append(child_iter)
            child_iter = self.iter_next(child_iter)
        for filedata in files:
            row_tuple = _generate_row_tuple(filedata, False)
            while (child_iter is not None) and (self.get_value(child_iter, _NAME) < filedata.name):
                dead_entries.append(child_iter)
                child_iter = self.iter_next(child_iter)
            if child_iter is None:
                dummy = self.append(parent_iter, row_tuple)
                continue
            if self.get_value(child_iter, _NAME) > filedata.name:
                dummy = self.insert_before(parent_iter, child_iter, row_tuple)
                continue
            self._update_iter_row_tuple(child_iter, row_tuple)
            child_iter = self.iter_next(child_iter)
        while child_iter is not None:
            dead_entries.append(child_iter)
            child_iter = self.iter_next(child_iter)
        for dead_entry in dead_entries:
            self._recursive_remove(dead_entry)
        if parent_iter is not None:
            self._insert_place_holder_if_needed(parent_iter)
    def _get_file_db(self):
        assert 0, '_get_file_db() must be defined in descendants'
    def repopulate(self):
        self._file_db = self._get_file_db()
        self.clear()
        self._populate('', self.get_iter_first())
    def update(self):
        self._file_db = self._get_file_db()
        self._update_dir('', None)
    def on_row_expanded_cb(self, view, dir_iter, dummy):
        self.view = view
        if not self._populate_all:
            self._update_dir(self.fs_path(dir_iter), dir_iter)
            if self.iter_n_children(dir_iter) > 1:
                self._remove_place_holder(dir_iter)
    def on_row_collapsed_cb(self, view, dir_iter, dummy):
        self._insert_place_holder_if_needed(dir_iter)

def _format_file_name_crcb(_column, cell_renderer, store, tree_iter, _arg=None):
    name = store.get_value(tree_iter, _NAME)
    xinfo = store.get_value(tree_iter, _ORIGIN)
    if xinfo:
        name += ' <- %s' % xinfo
    cell_renderer.set_property('text', name)

_VIEW_TEMPLATE = tlview.ViewTemplate(
    properties={'headers-visible' : False},
    selection_mode=gtk.SELECTION_MULTIPLE,
    columns=[
        tlview.Column(
            title='File Name',
            properties={},
            cells=[
                tlview.Cell(
                    creator=tlview.CellCreator(
                        function=gtk.CellRendererPixbuf,
                        expand=False,
                        start=True
                    ),
                    properties={},
                    renderer=None,
                    attributes={'stock-id' : _ICON}
                ),
                tlview.Cell(
                    creator=tlview.CellCreator(
                        function=gtk.CellRendererText,
                        expand=False,
                        start=True
                    ),
                    properties={},
                    renderer=None,
                    attributes={'text' : _STATUS, 'style' : _STYLE, 'foreground' : _FOREGROUND}
                ),
                tlview.Cell(
                    creator=tlview.CellCreator(
                        function=gtk.CellRendererText,
                        expand=False,
                        start=True
                    ),
                    properties={},
                    renderer=tlview.Renderer(function=_format_file_name_crcb, user_data=None),
                    attributes={'style' : _STYLE, 'foreground' : _FOREGROUND}
                )
            ]
        )
    ]
)

class CwdFileTreeStore(FileTreeStore):
    def __init__(self, show_hidden=False):
        FileTreeStore.__init__(self, show_hidden=show_hidden)
        self._os_file_db = fsdb.OsFileDb()
    def _get_file_db(self):
        return self._os_file_db

class _ViewWithActionGroups(tlview.View, dialogue.BusyIndicatorUser,
                            actions.AGandUIManager):
    def __init__(self, template, busy_indicator, model=None):
        tlview.View.__init__(self, template, model)
        dialogue.BusyIndicatorUser.__init__(self, busy_indicator)
        actions.AGandUIManager.__init__(self, self.get_selection())
        self.add_conditional_action(actions.Condns.DONT_CARE, model.show_hidden_action)
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
        _ViewWithActionGroups.__init__(self, _VIEW_TEMPLATE, busy_indicator, model=model)
        if not show_status:
            pass # TODO: hide the status column
        model.set_view(self)
        self._refresh_interval = 60000 # milliseconds
        self.connect("row-expanded", model.on_row_expanded_cb)
        self.connect("row-collapsed", model.on_row_collapsed_cb)
        self.auto_refresh_action = gtk.ToggleAction("auto_refresh_files", "Auto Refresh",
                                                   "Automatically/periodically refresh file display", None)
        self.auto_refresh_action.set_active(auto_refresh)
        self.auto_refresh_action.connect("toggled", self._toggle_auto_refresh_cb)
        self.auto_refresh_action.set_menu_item_type(gtk.CheckMenuItem)
        self.auto_refresh_action.set_tool_item_type(gtk.ToggleToolButton)
        self.add_conditional_action(actions.Condns.DONT_CARE, self.auto_refresh_action)
        self.add_conditional_actions(actions.Condns.DONT_CARE,
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
            clipboard = gtk.clipboard_get()
        sel = utils.file_list_to_string(self.get_selected_files())
        clipboard.set_text(sel)
    def _key_press_cb(self, widget, event):
        if event.state & gtk.gdk.CONTROL_MASK:
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
    def update_tree(self, _action=None):
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
    <placeholder name='filter_options'>
    <menuitem action="show_hidden_files"/>
    </placeholder>
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
        self.add_conditional_actions(actions.Condns.SELN,
            [
                ("edit_files", gtk.STOCK_EDIT, "_Edit", None,
                 "Edit the selected file(s)", self.edit_selected_files_acb),
                ("delete_files", gtk.STOCK_DELETE, "_Delete", None,
                 "Delete the selected file(s) from the repository", self.delete_selected_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.DONT_CARE,
            [
                ("new_file", gtk.STOCK_NEW, "_New", None,
                 "Create a new file and open for editing", self.create_new_file_acb),
            ])
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(CWD_UI_DESCR)
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
            ifce.log.start_cmd('Deleting: %s' % utils.file_list_to_string(file_list))
        serr = ""
        for filename in file_list:
            try:
                os.remove(filename)
                if ifce.log:
                    ifce.log.append_stdout(("Deleted: %s" + os.linesep) % filename)
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
        if not ask or dialogue.confirm_list_action(file_list, 'About to be deleted. OK?'):
            self.show_busy()
            result = self.delete_files(file_list)
            self.unshow_busy()
            dialogue.report_any_problems(result)
    def delete_selected_files_acb(self, _menu_item):
        self._delete_named_files(self.get_selected_files())

class ScmCwdFileTreeStore(CwdFileTreeStore):
    def __init__(self, show_hidden=False):
        CwdFileTreeStore.__init__(self, show_hidden=show_hidden)
        self.hide_clean_action = gtk.ToggleAction('hide_clean_files', 'Hide Clean Files',
                                                   'Show/hide "clean" files', None)
        self.hide_clean_action.set_active(False)
        self.hide_clean_action.connect('toggled', self._toggle_hide_clean_cb)
        self.hide_clean_action.set_menu_item_type(gtk.CheckMenuItem)
        self.hide_clean_action.set_tool_item_type(gtk.ToggleToolButton)
    def _get_file_db(self):
        if ifce.in_valid_repo:
            self._populate_all = True
            return ifce.SCM.get_ws_file_db()
        else:
            self._populate_all = False
            return self._os_file_db
    def _toggle_hide_clean_cb(self, toggleaction):
        self._update_dir('', None)
    def _get_dir_contents(self, dirpath):
        show_hidden = self.show_hidden_action.get_active()
        if not show_hidden and self.hide_clean_action.get_active():
            dirs, files = self._file_db.dir_contents(dirpath, show_hidden)
            return ([ncd for ncd in dirs if ncd.status != hg_mq_ifce.FSTATUS_CLEAN],
                    [ncf for ncf in files if ncf.status != hg_mq_ifce.FSTATUS_CLEAN])
        return self._file_db.dir_contents(dirpath, show_hidden)

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
    return dialogue.ask_force_or_cancel(result) == dialogue.RESPONSE_FORCE

class ScmCwdFileTreeView(CwdFileTreeView):
    def __init__(self, busy_indicator, auto_refresh=False, show_hidden=False):
        model = ScmCwdFileTreeStore(show_hidden=show_hidden)
        CwdFileTreeView.__init__(self, busy_indicator=busy_indicator, model=model,
            auto_refresh=auto_refresh, show_status=True)
        self.add_notification_cb(ws_event.CHECKOUT|ws_event.FILE_CHANGES, self.update_tree),
        self.add_notification_cb(ws_event.CHANGE_WD, self.update_for_chdir),
        self.add_conditional_action(actions.Condns.DONT_CARE, model.hide_clean_action)
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.SELN,
            [
                ("scm_remove_files", gtk.STOCK_REMOVE, "_Remove", None,
                 "Remove the selected file(s) from the repository", self.remove_selected_files_acb),
                ("scm_add_files", gtk.STOCK_ADD, "_Add", None,
                 "Add the selected file(s) to the repository", self.add_selected_files_to_repo_acb),
                ("scm_copy_files_selection", gtk.STOCK_COPY, "_Copy", None,
                 "Copy the selected file(s)", self.copy_selected_files_acb),
                ("scm_diff_files_selection", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for selected file(s)", self.diff_selected_files_acb),
                ("scm_extdiff_files_selection", icons.STOCK_DIFF, "E_xtdiff", None,
                 "Launch extdiff for selected file(s)", self.extdiff_selected_files_acb),
                ("scm_move_files_selection", icons.STOCK_RENAME, "_Move/Rename", None,
                 "Move the selected file(s)", self.move_selected_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.NOT_PMIC + actions.Condns.SELN,
            [
                ("scm_resolve_files_selection", icons.STOCK_RESOLVE, "Re_solve", None,
                 "Resolve merge conflicts in the selected file(s)", self.resolve_selected_files_acb),
               ("scm_mark_resolved_files_selection", icons.STOCK_MARK_RESOLVE, "_Mark Resolved", None,
                 "Mark the selected file(s) as having had merge conflict resolved", self.mark_resolved_selected_files_acb),
                ("scm_mark_unresolved_files_selection", icons.STOCK_MARK_UNRESOLVE, "Mark _Unresolved", None,
                 "Mark the selected file(s) as having unresolved merge conflicts", self.mark_unresolved_selected_files_acb),
                ("scm_revert_files_selection", icons.STOCK_REVERT, "Rever_t", None,
                 "Revert changes in the selected file(s)", self.revert_selected_files_acb),
                ("scm_commit_files_selection", icons.STOCK_COMMIT, "_Commit", None,
                 "Commit changes for selected file(s)", self.commit_selected_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.UNIQUE_SELN,
           [
                ("scm_rename_file", icons.STOCK_RENAME, "Re_name/Move", None,
                 "Rename/move the selected file", self.move_selected_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.NO_SELN,
            [
                ("scm_add_files_all", gtk.STOCK_ADD, "_Add all", None,
                 "Add all files to the repository", self.add_all_files_to_repo_acb),
                ("scm_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self.diff_selected_files_acb),
                ("scm_extdiff_files_all", icons.STOCK_DIFF, "E_xtdiff", None,
                 "Launch extdiff for all changes", self.extdiff_selected_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.NOT_PMIC + actions.Condns.NO_SELN,
            [
                ("scm_revert_files_all", icons.STOCK_REVERT, "Rever_t", None,
                 "Revert all changes in working directory", self.revert_all_files_acb),
                ("scm_commit_files_all", icons.STOCK_COMMIT, "_Commit", None,
                 "Commit all changes", self.commit_all_changes_acb),
            ])
        self.add_conditional_actions(actions.Condns.DONT_CARE,
            [
                ("menu_files", None, "_Files"),
            ])
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(SCM_CWD_UI_DESCR)
        if not ifce.SCM.get_extension_enabled("extdiff"):
            self.get_conditional_action("scm_extdiff_files_selection").set_visible(False)
            self.get_conditional_action("scm_extdiff_files_all").set_visible(False)
        if tortoise.IS_AVAILABLE:
            self.add_conditional_action(actions.Condns.DONT_CARE, tortoise.FILE_MENU)
            for condition in tortoise.FILE_GROUP_PARTIAL_ACTIONS:
                action_list = []
                for action in tortoise.FILE_GROUP_PARTIAL_ACTIONS[condition]:
                    action_list.append(action + tuple([self._tortoise_tool_acb]))
                self.add_conditional_actions(condition, action_list)
            self.ui_manager.add_ui_from_string(tortoise.FILES_UI_DESCR)
        self.init_action_states()
        model.repopulate()
    def update_for_chdir(self):
        self.show_busy()
        self.repopulate_tree()
        self.unshow_busy()
    def _tortoise_tool_acb(self, action=None):
        tortoise.run_tool_for_files(action, self.get_selected_files())
    def new_file(self, new_file_name):
        result = utils.create_file(new_file_name, ifce.log)
        if result.eflags == 0:
            result = ifce.SCM.do_add_files([new_file_name])
        return result
    def delete_files(self, file_list):
        return ifce.SCM.do_delete_files(file_list)
    def get_scm_name(self):
        return ifce.SCM.name
    def _remove_named_files(self, file_list, ask=True):
        if not ask or dialogue.confirm_list_action(file_list, 'About to be removed. OK?'):
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
        if result.eflags != cmd_result.OK:
            dialogue.report_any_problems(result)
            return
        if dialogue.confirm_list_action('\n'.join(result[1:]).splitlines(), 'About to be actioned. OK?'):
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
            assert False, "Invalid operation requested"
        response, target = self._get_target(file_list)
        if response == gtk.RESPONSE_OK:
            force = False
            if ask:
                while True:
                    self.show_busy()
                    result = operation(file_list, target, force=force, dry_run=True)
                    self.unshow_busy()
                    if cmd_result.is_less_than_error(result):
                        is_ok = dialogue.confirm_list_action(result.stdout.splitlines(), 'About to be actioned. OK?')
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
            if result.eflags == cmd_result.OK:
                if result.stdout:
                    is_ok = dialogue.confirm_list_action(result.stdout.splitlines(), 'About to be actioned. OK?')
                else:
                    dialogue.inform_user('Nothing to revert')
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
            gutils.set_widget_tooltip_text(button, action.get_property("tooltip"))
            hbox.pack_start(button)
        self.pack_start(hbox, expand=False)
        self.show_all()

class ScmCommitFileTreeStore(FileTreeStore):
    def __init__(self, show_hidden=True, view=None, file_mask=None):
        if file_mask is None:
            self._file_mask = []
        else:
            self._file_mask = file_mask
        FileTreeStore.__init__(self, show_hidden=show_hidden, populate_all=True,
                               auto_expand=True, view=view)
        self.repopulate()
    def set_file_mask(self, file_mask):
        self._file_mask = file_mask
        self.update()
    def get_file_mask(self):
        return self._file_mask
    def _get_file_db(self):
        return ifce.SCM.get_commit_file_db(self._file_mask)

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

class ScmCommitFileTreeView(FileTreeView):
    def __init__(self, busy_indicator, auto_refresh=False, show_hidden=True, file_mask=None):
        self.removeds = []
        self.model = ScmCommitFileTreeStore(show_hidden=show_hidden, file_mask=file_mask)
        FileTreeView.__init__(self, model=self.model, busy_indicator=busy_indicator,
                              auto_refresh=auto_refresh, show_status=True)
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.set_headers_visible(False)
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.SELN,
            [
                ("scmch_remove_files", gtk.STOCK_DELETE, "_Remove", None,
                 "Remove the selected files from the change set", self._remove_selected_files_acb),
                ("scm_diff_files_selection", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for selected file(s)", self._diff_selected_files_acb),
                ("scm_extdiff_files_selection", icons.STOCK_DIFF, "E_xtdiff", None,
                 "Launch extdiff for the selected file(s)", self._extdiff_selected_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO,
            [
                ("scmch_undo_remove_files", gtk.STOCK_UNDO, "_Undo", None,
                 "Undo the last remove", self._undo_last_remove_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.NO_SELN,
            [
                ("scm_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self._diff_all_files_acb),
                ("scm_extdiff_files_all", icons.STOCK_DIFF, "E_xtdiff", None,
                 "Launch etxdiff for all changes", self._extdiff_all_files_acb),
            ])
        self.scm_change_merge_id = self.ui_manager.add_ui_from_string(SCM_CHANGE_UI_DESCR)
        self.get_conditional_action("scmch_undo_remove_files").set_sensitive(False)
        if not ifce.SCM.get_extension_enabled("extdiff"):
            self.get_conditional_action("scm_extdiff_files_selection").set_visible(False)
            self.get_conditional_action("scm_extdiff_files_all").set_visible(False)
    def set_file_mask(self, file_mask):
        self.model.set_file_mask(file_mask)
    def get_file_mask(self):
        return self.model.get_file_mask()
    def _remove_selected_files_acb(self, _menu_item):
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
    def _undo_last_remove_acb(self, _menu_item):
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
    def _diff_selected_files_acb(self, _action=None):
        parent = dialogue.main_window
        dialog = diff.ScmDiffTextDialog(parent=parent, file_list=self.get_selected_files())
        dialog.show()
    def _diff_all_files_acb(self, _action=None):
        parent = dialogue.main_window
        dialog = diff.ScmDiffTextDialog(parent=parent, file_list=self.get_file_mask())
        dialog.show()
    def _extdiff_selected_files_acb(self, _action=None):
        ifce.SCM.launch_extdiff_for_ws(file_list=self.get_selected_files())
    def _extdiff_all_files_acb(self, _action=None):
        ifce.SCM.launch_extdiff_for_ws(file_list=self.get_file_mask())

class ScmCommitWidget(gtk.VPaned, ws_event.Listener):
    def __init__(self, busy_indicator, file_mask=None):
        gtk.VPaned.__init__(self)
        ws_event.Listener.__init__(self)
        # TextView for change message
        self.view = text_edit.ChangeSummaryView()
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        menubar = self.view.ui_manager.get_widget("/change_summary_menubar")
        hbox.pack_start(menubar, fill=True, expand=False)
        toolbar = self.view.ui_manager.get_widget("/change_summary_toolbar")
        toolbar.set_style(gtk.TOOLBAR_BOTH)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        hbox.pack_end(toolbar, fill=False, expand=False)
        vbox.pack_start(hbox, expand=False)
        vbox.pack_start(gutils.wrap_in_scrolled_window(self.view))
        self.add1(vbox)
        # TreeView of files in change set
        self.files = ScmCommitFileTreeView(busy_indicator=busy_indicator,
                                           auto_refresh=False,
                                           show_hidden=True,
                                           file_mask=file_mask)
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Files"), fill=True, expand=False)
        toolbar = self.files.ui_manager.get_widget("/files_refresh_toolbar")
        toolbar.set_style(gtk.TOOLBAR_BOTH)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        hbox.pack_end(toolbar, fill=False, expand=False)
        vbox.pack_start(hbox, expand=False)
        x, y = self.files.tree_to_widget_coords(480, 240)
        self.files.set_size_request(x, y)
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
                qtn = 'Unsaved changes to summary will be lost.\n\nCancel anyway?'
                if dialogue.ask_yes_no(qtn):
                    self._finish_up()
        else:
            self._finish_up()

class PatchFileTreeStore(FileTreeStore):
    def __init__(self, patch=None, view=None):
        self._patch = patch
        FileTreeStore.__init__(self, show_hidden=True, populate_all=True,
                                         auto_expand=True, view=view)
        self.view = view
        self._null_file_db = fsdb.NullFileDb()
    def _get_file_db(self):
        if ifce.in_valid_repo:
            return ifce.PM.get_patch_file_db(self._patch)
        else:
            return self._null_file_db
    def repopulate(self):
        FileTreeStore.repopulate(self)

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

class PatchFileTreeView(CwdFileTreeView):
    def __init__(self, busy_indicator, patch=None):
        self._patch = patch
        model = PatchFileTreeStore(patch=patch)
        CwdFileTreeView.__init__(self, busy_indicator=busy_indicator, model=model,
             auto_refresh=False, show_status=True)
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.SELN,
            [
                ("pm_diff_files_selection", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for selected file(s)", self.diff_selected_files_acb),
                ("pm_extdiff_files_selection", icons.STOCK_DIFF, "E_xtdiff", None,
                 "Launch extdiff for selected file(s)", self.extdiff_selected_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.NO_SELN,
            [
                ("pm_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self.diff_all_files_acb),
                ("pm_extdiff_files_all", icons.STOCK_DIFF, "E_xtdiff", None,
                 "Launch extdiff for all changes", self.extdiff_all_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO,
            [
                ("menu_files", None, "_Files"),
            ])
        if not ifce.SCM.get_extension_enabled("extdiff") or not ifce.PM.get_patch_is_applied(self._patch):
            self.get_conditional_action("pm_extdiff_files_selection").set_visible(False)
            self.get_conditional_action("pm_extdiff_files_all").set_visible(False)
        model.show_hidden_action.set_visible(False)
        model.show_hidden_action.set_sensitive(False)
        self.get_conditional_action("new_file").set_visible(False)
        self.get_conditional_action("edit_files").set_visible(False)
        self.get_conditional_action("delete_files").set_visible(False)
        model.repopulate()
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(PATCH_FILES_UI_DESCR)
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
      <menuitem action="auto_refresh_files"/>
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

class TopPatchFileTreeView(CwdFileTreeView):
    def __init__(self, busy_indicator, auto_refresh=False):
        model = PatchFileTreeStore()
        CwdFileTreeView.__init__(self, busy_indicator=busy_indicator,
            model=model, auto_refresh=auto_refresh, show_status=True)
        self.move_conditional_action('new_file', actions.Condns.IN_REPO + actions.Condns.PMIC)
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.PMIC + actions.Condns.SELN,
            [
                ("pm_remove_files", gtk.STOCK_REMOVE, "_Remove", None,
                 "Remove the selected file(s) from the patch", self.remove_selected_files_acb),
                ("pm_copy_files_selection", gtk.STOCK_COPY, "_Copy", None,
                 "Copy the selected file(s)", self.copy_selected_files_acb),
                ("pm_diff_files_selection", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for selected file(s)", self.diff_selected_files_acb),
                ("pm_extdiff_files_selection", icons.STOCK_DIFF, "E_xtdiff", None,
                 "Launch extdiff for selected file(s)", self.extdiff_selected_files_acb),
                ("pm_move_files_selection", gtk.STOCK_PASTE, "_Move/Rename", None,
                 "Move the selected file(s)", self.move_selected_files_acb),
                ("pm_revert_files_selection", gtk.STOCK_UNDO, "Rever_t", None,
                 "Revert changes in the selected file(s)", self.revert_selected_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.PMIC + actions.Condns.UNIQUE_SELN,
            [
                ("pm_rename_file", gtk.STOCK_PASTE, "Re_name/Move", None,
                 "Rename/move the selected file", self.move_selected_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO + actions.Condns.PMIC + actions.Condns.NO_SELN,
            [
                ("pm_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self.diff_all_files_acb),
                ("pm_extdiff_files_all", icons.STOCK_DIFF, "E_xtdiff", None,
                 "Launch extdiff for all changes", self.extdiff_all_files_acb),
                ("pm_revert_files_all", gtk.STOCK_UNDO, "Rever_t", None,
                 "Revert all changes in working directory", self.revert_all_files_acb),
            ])
        self.add_conditional_actions(actions.Condns.IN_REPO,
            [
                ("menu_files", None, "_Files"),
            ])
        model.show_hidden_action.set_visible(False)
        model.show_hidden_action.set_sensitive(False)
        if not ifce.SCM.get_extension_enabled("extdiff"):
            self.get_conditional_action("pm_extdiff_files_selection").set_visible(False)
            self.get_conditional_action("pm_extdiff_files_all").set_visible(False)
        model.repopulate()
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(PM_FILES_UI_DESCR)
        self.add_notification_cb(ws_event.CHECKOUT|ws_event.CHANGE_WD, self.repopulate_tree)
        self.add_notification_cb(ws_event.FILE_CHANGES, self.update_tree)
        self.init_action_states()
    def create_new_file(self, new_file_name, open_for_edit=False):
        result = CwdFileTreeView.create_new_file(self, new_file_name, open_for_edit)
        if not result[0]:
            result = ifce.PM.do_add_files([new_file_name])
            dialogue.report_any_problems(result)
        return result
    def delete_files(self, file_list):
        return ifce.PM.do_delete_files(file_list)
    def _remove_named_files(self, file_list, ask=True):
        if not ask or dialogue.confirm_list_action(file_list, 'About to be removed. OK?'):
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
        dialog = gtk.FileChooserDialog("Target", dialogue.main_window, mode,
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
                    if result.eflags == cmd_result.OK:
                        is_ok = dialogue.confirm_list_action(result.stdout.splitlines(), 'About to be actioned. OK?')
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
            if result.eflags == cmd_result.OK:
                if result.stdout:
                    is_ok = dialogue.confirm_list_action(result.stdoutt.splitlines(), 'About to be actioned. OK?')
                else:
                    dialogue.inform_user('Nothing to revert')
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
