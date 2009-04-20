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

import gtk, gobject, pango, os
from gwsmhg_pkg import cmd_result, gutils, file_tree, console, icons, text_edit, utils

class PatchFileTreeStore(file_tree.FileTreeStore):
    def __init__(self, pm_ifce, view=None):
        self._pm_ifce = pm_ifce
        row_data = apply(file_tree.FileTreeRowData, self._pm_ifce.get_status_row_data())
        file_tree.FileTreeStore.__init__(self, show_hidden=True, row_data=row_data)
        # if this is set to the associated view then the view will expand
        # to show new files without disturbing other expansion states
        self._view = view
    def set_view(self, view):
        self._view = view
    def update(self, fsobj_iter=None):
        res, dflist, dummy = self._pm_ifce.get_file_status_list()
        if res == 0:
            files = [tmpx[0] for tmpx in dflist] 
            for f in self.get_file_paths():
                try:
                    i = files.index(f)
                except:
                    self.delete_file(f)
            for dfile, status, extra_info in dflist:
                found, file_iter = self.find_or_insert_file(dfile, file_status=status, extra_info=extra_info)
                if not found and self._view:
                    self._view.expand_to_path(self.get_path(file_iter))
    def repopulate(self):
        self.clear()
        self.update()
    def get_pm_ifce(self):
        return self._pm_ifce
    def set_pm_ifce(self, pm_ifce):
        self._pm_ifce = pm_ifce
        self.update()

PM_FILES_UI_DESCR = \
'''
<ui>
  <menubar name="files_menubar">
    <menu name="files_menu" action="menu_files">
      <menuitem action="refresh_files"/>
      <separator/>
      <menuitem action="auto_refresh_files"/>
    </menu>
  </menubar>
  <popup name="files_popup">
    <placeholder name="selection_indifferent">
      <menuitem action="new_file"/>
    </placeholder>
    <placeholder name="selection">
      <menuitem action="edit_files"/>
      <menuitem action="delete_files"/>
      <menuitem action="pm_remove_files"/>
      <menuitem action="pm_copy_files_selection"/>
      <menuitem action="pm_diff_files_selection"/>
      <menuitem action="pm_move_files_selection"/>
      <menuitem action="pm_revert_files_selection"/>
    </placeholder>
    <placeholder name="unique_selection">
      <menuitem action="pm_rename_file"/>
    </placeholder>
    <placeholder name="no_selection">
      <menuitem action="pm_diff_files_all"/>
      <menuitem action="pm_revert_files_all"/>
    </placeholder>
  </popup>
</ui>
'''

class PatchFileTreeView(file_tree.CwdFileTreeView):
    def __init__(self, pm_ifce, tooltips=None, auto_refresh=False, console_log=None):
        pm_ifce.set_console_log(console_log)
        model = PatchFileTreeStore(pm_ifce=pm_ifce)
        model.get_pm_ifce().add_qrefresh_notification_cb(self.update_tree)
        model.get_pm_ifce().add_qpop_notification_cb(self.update_tree)
        model.get_pm_ifce().add_qpush_notification_cb(self.update_tree)
        file_tree.CwdFileTreeView.__init__(self, model=model, tooltips=tooltips, auto_refresh=auto_refresh, show_status=True)
        model.set_view(self)
        self._action_group[file_tree.SELECTION].add_actions(
            [
                ("pm_remove_files", gtk.STOCK_REMOVE, "_Remove", None,
                 "Remove the selected file(s) from the patch", self.remove_selected_files_acb),
                ("pm_copy_files_selection", gtk.STOCK_COPY, "_Copy", None,
                 "Copy the selected file(s)", self.copy_selected_files_acb),
                ("pm_diff_files_selection", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for selected file(s)", self.diff_selected_files_acb),
                ("pm_move_files_selection", gtk.STOCK_PASTE, "_Move/Rename", None,
                 "Move the selected file(s)", self.move_selected_files_acb),
                ("pm_revert_files_selection", gtk.STOCK_UNDO, "Rever_t", None,
                 "Revert changes in the selected file(s)", self.revert_selected_files_acb),
            ])
        self._action_group[file_tree.UNIQUE_SELECTION].add_actions(
            [
                ("pm_rename_file", gtk.STOCK_PASTE, "Re_name/Move", None,
                 "Rename/move the selected file", self.move_selected_files_acb),
            ])
        self._action_group[file_tree.NO_SELECTION].add_actions(
            [
                ("pm_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self.diff_selected_files_acb),
                ("pm_revert_files_all", gtk.STOCK_UNDO, "Rever_t", None,
                 "Revert all changes in working directory", self.revert_all_files_acb),
            ])
        self._action_group[file_tree.SELECTION_INDIFFERENT].add_actions(
            [
                ("menu_files", None, "_Files"),
            ])
        model.show_hidden_action.set_visible(False)
        model.show_hidden_action.set_sensitive(False)
        model.repopulate()
        self.cwd_merge_id = self._ui_manager.add_ui_from_string(PM_FILES_UI_DESCR)
    def get_pm_name(self):
        return self.get_model().get_pm_ifce().name
    def get_pm_ifce(self):
        return self.get_model().get_pm_ifce()
    def set_pm_ifce(self, pm_ifce):
        old_pm_ifce = self.get_pm_ifce()
        if old_pm_ifce:
            old_pm_ifce.del_qrefresh_notification_cb(self.update_tree)
            old_pm_ifce.del_qpop_notification_cb(self.update_tree)
            old_pm_ifce.del_qpull_notification_cb(self.update_tree)
        self.get_model().set_pm_ifce(pm_ifce)
        new_pm_ifce = self.get_pm_ifce()
        if new_pm_ifce:
            new_pm_ifce.add_qrefresh_notification_cb(self.update_tree)
            new_pm_ifce.add_qpop_notification_cb(self.update_tree)
            new_pm_ifce.add_qpush_notification_cb(self.update_tree)
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
            result = model.get_pm_ifce().do_remove_files(file_list)
            self._show_busy()
            if self._check_if_force(result):
                result = model.get_pm_ifce().do_remove_files(file_list, force=True)
            self.update_tree()
            self._report_any_problems(result)
    def remove_selected_files_acb(self, menu_item):
        self._remove_named_files(self.get_selected_files())
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
            operation = self.get_pm_ifce().do_copy_files
        elif reqop == "m":
            operation = self.get_pm_ifce().do_move_files
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
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
#        dialog = diff.DiffTextDialog(parent=self._get_gtk_window(),
#                                     pm_ifce=self.get_pm_ifce(),
#                                     file_list=self.get_selected_files(), modal=False)
#        dialog.show()
    def revert_named_files(self, file_list, ask=True):
        if ask:
            self._show_busy()
            res, sout, serr = self.get_pm_ifce().revert_files(file_list, dry_run=True)
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
            result = self.get_pm_ifce().revert_files(file_list)
            self.get_model().del_files_from_displayable_nonexistants(file_list)
            self._show_busy()
            self.update_tree()
            self._report_any_problems(result)
    def revert_selected_files_acb(self, action=None):
        self.revert_named_files(self.get_selected_files())
    def revert_all_files_acb(self, action=None):
        self.revert_named_files([])

class PatchFilesWidget(gtk.VBox):
    def __init__(self, pm_ifce, tooltips=None, auto_refresh=False, console_log=None):
        gtk.VBox.__init__(self)
        self._tooltips = tooltips
        # file tree view wrapped in scrolled window
        self.file_tree = PatchFileTreeView(pm_ifce=pm_ifce, tooltips=tooltips,
                                           auto_refresh=auto_refresh,
                                           console_log=console_log)
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
        self.show_all()

PM_PATCHES_UI_DESCR = \
'''
<ui>
  <menubar name="patches_menubar">
    <menu name="patches_menu" action="menu_patches">
      <menuitem action="save_queue_state"/>
      <menuitem action="pm_pop_all"/>
      <menuitem action="pm_push_all"/>
      <separator/>
      <menuitem action="save_queue_state_for_update"/>
      <menuitem action="pm_update_workspace"/>
      <menuitem action="pm_push_all_with_merge"/>
    </menu>
  </menubar>
  <toolbar name="patches_toolbar">
    <toolitem name="Refresh" action="pm_refresh_top_patch"/>
    <toolitem name="Push" action="pm_push"/>
    <toolitem name="Pop" action="pm_pop"/>
    <toolitem name="New" action="pm_new"/>
    <toolitem name="Import" action="pm_import_external_patch"/>
    <toolitem name="Fold" action="pm_fold_external_patch"/>
  </toolbar>
  <menubar name="patch_list_menubar">
    <menu name="patch_list_menu" action="menu_patch_list">
      <menuitem action="refresh_patch_list"/>
      <separator/>
      <menuitem action="auto_refresh_patch_list"/>
    </menu>
  </menubar>
  <popup name="patches_popup">
    <placeholder name="applied">
      <menuitem action="pm_pop_to_patch"/>
      <menuitem action="pm_finish_to"/>
    </placeholder>
    <separator/>
    <placeholder name="applied_indifferent">
      <menuitem action="pm_edit_patch_descr"/>
      <menuitem action="pm_view_patch_files"/>
      <menuitem action="pm_rename_patch"/>
      <menuitem action="pm_delete_patch"/>
    </placeholder>
    <separator/>
    <placeholder name="unapplied">
      <menuitem action="pm_push_to"/>
      <menuitem action="pm_fold"/>
      <menuitem action="pm_fold_to"/>
      <menuitem action="pm_duplicate"/>
    </placeholder>
    <placeholder name="unapplied_and_interdiff">
      <menuitem action="pm_interdiff"/>
    </placeholder>
  </popup>
</ui>
'''

APPLIED = "pm_sel_applied"
UNAPPLIED = "pm_sel_unapplied"
UNAPPLIED_AND_INTERDIFF = "pm_sel_unapplied_interdiff"
APPLIED_INDIFFERENT = "pm_sel_indifferent"
PUSH_POSSIBLE = "pm_push_possible"
PUSH_NOT_POSSIBLE = "pm_push_not_possible"
POP_POSSIBLE = "pm_pop_possible"
PUSH_POP_INDIFFERENT = "pm_push_pop_indifferent"

class PatchListView(gtk.TreeView, cmd_result.ProblemReporter, gutils.BusyIndicator):
    def __init__(self, pm_ifce, scm_ifce):
        cmd_result.ProblemReporter.__init__(self)
        gutils.BusyIndicator.__init__(self)
        self._pm_ifce = pm_ifce
        self._scm_ifce = scm_ifce
        self.store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_INT,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING)
        gtk.TreeView.__init__(self, self.store)
        text_cell = gtk.CellRendererText()
        icon_cell = gtk.CellRendererPixbuf()
        tvcolumn = gtk.TreeViewColumn("patch_list")
        tvcolumn.pack_start(icon_cell, False)
        tvcolumn.pack_start(text_cell)
        tvcolumn.set_attributes(text_cell, text=0, style=1, foreground=2)
        tvcolumn.set_attributes(icon_cell, stock_id=3)
        self.append_column(tvcolumn)
        self.set_headers_visible(False)
        self.get_selection().set_mode(gtk.SELECTION_SINGLE)
        self._ui_manager = gtk.UIManager()
        self._action_group = {}
        for applied_condition in APPLIED, UNAPPLIED, APPLIED_INDIFFERENT, UNAPPLIED_AND_INTERDIFF:
            self._action_group[applied_condition] = gtk.ActionGroup(applied_condition)
            self._ui_manager.insert_action_group(self._action_group[applied_condition], -1)
        for applied_condition in PUSH_POSSIBLE, PUSH_NOT_POSSIBLE, POP_POSSIBLE, PUSH_POP_INDIFFERENT:
            self._action_group[applied_condition] = gtk.ActionGroup(applied_condition)
            self._ui_manager.insert_action_group(self._action_group[applied_condition], -1)
        self._action_group[APPLIED].add_actions(
            [
                ("pm_pop_to_patch", icons.STOCK_POP_PATCH, "Pop To", None,
                 "Pop to the selected patch", self.do_pop_to),
                ("pm_finish_to", icons.STOCK_FINISH_PATCH, "Finish To", None,
                 "Move patches up to the selected patch into main repository", self.do_finish_to),
            ])
        self._action_group[APPLIED_INDIFFERENT].add_actions(
            [
                ("pm_edit_patch_descr", gtk.STOCK_EDIT, "Description", None,
                 "Edit the selected patch's description", self.do_edit_description),
                ("pm_view_patch_files", gtk.STOCK_FILE, "Files", None,
                 "Show files affected by the selected patch", self.show_files),
                ("pm_rename_patch", None, "Rename", None,
                 "Rename the selected patch", self.do_rename),
                ("pm_delete_patch", gtk.STOCK_DELETE, "Delete", None,
                 "Delete the selected patch", self.do_delete),
            ])
        self._action_group[UNAPPLIED].add_actions(
            [
                ("pm_push_to", icons.STOCK_PUSH_PATCH, "Push To", None,
                 "Push to the selected patch", self.do_push_to),
                ("pm_fold", icons.STOCK_FOLD_PATCH, "Fold", None,
                 "Fold the selected patch into the top patch", self.do_fold),
                ("pm_fold_to", icons.STOCK_FOLD_PATCH, "Fold To", None,
                 "Fold patches up to the selected patch into the top patch", self.do_fold_to),
                ("pm_duplicate", gtk.STOCK_DELETE, "Delete", None,
                 "Duplicate the selected patch behind the top patch", self.do_duplicate),
            ])
        self._action_group[UNAPPLIED_AND_INTERDIFF].add_actions(
            [
                ("pm_interdiff", gtk.STOCK_PASTE, "Interdiff", None,
                 'Place the "interdiff" of the selected patch and the top patch behind the top patch', self.do_interdiff),
            ])
        self._action_group[PUSH_POSSIBLE].add_actions(
            [
                ("pm_push", icons.STOCK_PUSH_PATCH, "Push", None,
                 "Apply the next unapplied patch", self.do_push),
                ("pm_push_all", icons.STOCK_PUSH_PATCH, "Push All", None,
                 "Apply all remaining unapplied patches", self.do_push_all),
                ("pm_push_all_with_merge", icons.STOCK_PUSH_PATCH, "Push All (Merge)", None,
                 "Apply all remaining unapplied patches with \"merge\" option enabled", self.do_push_all),
            ])
        self._action_group[PUSH_NOT_POSSIBLE].add_actions(
            [
                ("pm_update_workspace", None, "Update Workspace", None,
                 "Update the workspace from the repository", self.do_update_workspace),
                ("save_queue_state_for_update", None, "Save Queue State For Update", None,
                 "Save the queue state prepatory to update", self.do_save_queue_state),
            ])
        self._action_group[POP_POSSIBLE].add_actions(
            [
                ("pm_pop", icons.STOCK_POP_PATCH, "Pop", None,
                 "Pop the top applied patch", self.do_pop),
                ("pm_pop_all", icons.STOCK_POP_PATCH, "Pop All", None,
                 "Pop all remaining applied patches", self.do_pop_all),
                ("pm_refresh_top_patch", gtk.STOCK_REFRESH, "Refresh", None,
                 "Refresh the top patch", self.do_refresh),
                ("pm_fold_external_patch", icons.STOCK_FOLD_PATCH, "Fold", None,
                 "Fold an external patch into the top patch", self.do_fold_external_patch),
            ])
        self._action_group[PUSH_POP_INDIFFERENT].add_actions(
            [
                ("menu_patches", None, "_Patches"),
                ("save_queue_state", gtk.STOCK_SAVE, "Save Queue State", None,
                 "Save the current patch queue state", self.do_save_queue_state),
                ("menu_patch_list", None, "Patch _List"),
                ("refresh_patch_list", gtk.STOCK_REFRESH, "Update Patch List", None,
                 "Refresh/update the patch list display", self.set_contents),
                ("pm_new", gtk.STOCK_ADD, "New", None,
                 "Create a new patch", self.do_new_patch),
                ("pm_import_external_patch", icons.STOCK_IMPORT_PATCH, "Import", None,
                 "Import an external patch", self.do_import_external_patch),
            ])
        toggle_data = range(4)
        toggle_data[gutils.TOC_NAME] = "auto_refresh_patch_list"
        toggle_data[gutils.TOC_LABEL] = "Auto Update"
        toggle_data[gutils.TOC_TOOLTIP] = "Enable/disable automatic updating of the patch list"
        toggle_data[gutils.TOC_STOCK_ID] = gtk.STOCK_REFRESH
        self.toc = gutils.TimeOutController(toggle_data, function=self.set_contents, is_on=False)
        self._action_group[PUSH_POP_INDIFFERENT].add_action(self.toc.toggle_action)
        self.cwd_merge_id = self._ui_manager.add_ui_from_string(PM_PATCHES_UI_DESCR)
        self.get_selection().connect("changed", self._selection_changed_cb)
        self.applied_count = self.unapplied_count = 0
        self.set_contents(False)
        self.get_selection().unselect_all()
        self._selection_changed_cb(self.get_selection())
        self.connect("button_press_event", self._handle_button_press_cb)
    def _selection_changed_cb(self, selection):
        if selection.count_selected_rows() == 0:
            for index in APPLIED, UNAPPLIED, APPLIED_INDIFFERENT, UNAPPLIED_AND_INTERDIFF:
                self._action_group[index].set_sensitive(False)
        else:
            model, iter = self.get_selection().get_selected()
            applied = model.get_value(iter, 3) != None
            self._action_group[APPLIED_INDIFFERENT].set_sensitive(True)
            self._action_group[APPLIED].set_sensitive(applied)
            self._action_group[UNAPPLIED].set_sensitive(not applied)
            self._action_group[UNAPPLIED_AND_INTERDIFF].set_sensitive(utils.which("interdiff") and not applied)
    def _handle_button_press_cb(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 3:
                menu = self._ui_manager.get_widget("/patches_popup")
                menu.popup(None, None, None, event.button, event.time)
                return True
            elif event.button == 2:
                self.get_selection().unselect_all()
                return True
        return False
    def get_ui_widget(self, path):
        return self._ui_manager.get_widget(path)
    def get_selected_patch(self):
        model, iter = self.get_selection().get_selected()
        if iter is None:
            return None
        else:
            return model.get_value(iter, 0)
    def set_contents(self, show_busy=True):
        self._show_busy(show_busy)
        applied_patch_list = self._pm_ifce.get_applied_patches()
        unapplied_patch_list = self._pm_ifce.get_unapplied_patches()
        self.store.clear()
        for patch_name in applied_patch_list:
            self.store.append([patch_name, pango.STYLE_NORMAL, "black", icons.STOCK_APPLIED])
        self.applied_count = len(applied_patch_list)
        self._action_group[POP_POSSIBLE].set_sensitive(self.applied_count > 0)
        for patch_name in unapplied_patch_list:
            self.store.append([patch_name, pango.STYLE_ITALIC, "dark grey", None])
        self.unapplied_count = len(unapplied_patch_list)
        self._action_group[PUSH_POSSIBLE].set_sensitive(self.unapplied_count > 0)
        self._action_group[PUSH_NOT_POSSIBLE].set_sensitive(self.unapplied_count == 0)
        self.get_selection().unselect_all()
        self._unshow_busy(show_busy)
    def do_refresh(self, action=None):
        self._show_busy()
        res, sout, serr = self._pm_ifce.do_refresh()
        if res is not cmd_result.OK:
            self._unshow_busy()
            if res & cmd_result.SUGGEST_RECOVER:
                if gutils.ask_recover_or_cancel(os.linesep.join([sout, serr]), self) is gutils.RECOVER:
                    self._show_busy()
                    res, sout, serr = self._pm_ifce.do_recover_interrupted_refresh()
                    if res is cmd_result.OK:
                        res, sout, serr = self._pm_ifce.do_refresh()
                    self._unshow_busy()
            if res is not cmd_result.OK: # There're may still be problems
                self._report_any_problems((res, sout, serr))
                return
        else:
            self._unshow_busy()        
    def _do_pop_to(self, patch=None):
        while True:
            self._show_busy()
            res, sout, serr = self._pm_ifce.do_pop_to(patch=patch)
            self._unshow_busy()
            self.set_contents()
            if res is not cmd_result.OK:
                if res & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                    ans = gutils.ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res, self)
                    if ans is gtk.RESPONSE_CANCEL:
                        return False
                    if ans is gutils.REFRESH:
                        self.do_refresh()
                        self._show_busy()
                        res, sout, serr = self._pm_ifce.do_pop_to(patch=patch)
                        self._unshow_busy()
                    elif ans is gutils.FORCE:
                        self._show_busy()
                        res, sout, serr = self._pm_ifce.do_pop_to(force=True)
                        self._unshow_busy()
                if res is not cmd_result.OK: # there're are still problems
                    self._report_any_problems((res, sout, serr))
                    return False
            return True
    def do_pop_to(self, action=None):
        patch = self.get_selected_patch()
        while self._pm_ifce.top_patch() != patch:
            if not self._do_pop_to(patch):
                break
    def do_pop(self, action=None):
        self._do_pop_to()
    def do_pop_all(self, action=None):
        self._do_pop_to("")
    def _do_push_to(self, patch=None, merge=False):
        while True:
            self._show_busy()
            res, sout, serr = self._pm_ifce.do_push_to(patch=patch, merge=merge)
            self._unshow_busy()
            self.set_contents()
            if res is not cmd_result.OK:
                if res & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                    ans = gutils.ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res, self)
                    if ans is gtk.RESPONSE_CANCEL:
                        return False
                    self._show_busy()
                    if ans is gutils.REFRESH:
                        res, sout, serr = self._pm_ifcr.do_refresh()
                        if res is cmd_result.OK:
                            res, sout, serr = self._pm_ifce.do_push_to(patch=patch, merge=merge)
                    elif ans is gutils.FORCE:
                        res, sout, serr = self._pm_ifce.do_push_to(force=True, merge=merge)
                    self._unshow_busy()
                if res is not cmd_result.OK: # there're are still problems
                    self._report_any_problems((res, sout, serr))
                    return False
            return True
    def do_push_to(self, action=None):
        patch = self.get_selected_patch()
        while self._pm_ifce.top_patch() != patch:
            if not self._do_push_to(patch):
                break
    def do_push(self, action=None):
        self._do_push_to()
    def do_push_all(self, action=None):
        self._do_push_to("", merge=False)
    def do_push_all_with_merge(self, action=None):
        self._do_push_to("", merge=True)
    def do_finish_to(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_save_queue_state(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_edit_description(self, action=None):
        patch = self.get_selected_patch()
        PatchDescrEditDialog(patch, parent=None, scm_ifce=self._scm_ifce, pm_ifce=self._pm_ifce, modal=False).show()
    def show_files(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_rename(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_delete(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_fold(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_fold_to(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_duplicate(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_interdiff(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_update_workspace(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_new_patch(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_fold_external_patch(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)
    def do_import_external_patch(self, action=None):
        gutils.inform_user('Not yet implemented', problem_type=gtk.MESSAGE_INFO)

class PatchListWidget(gtk.VBox, console.ConsoleLogUser, gutils.TooltipsUser):
    def __init__(self, pm_ifce, scm_ifce, tooltips=None, console_log=None):
        gtk.VBox.__init__(self)
        console.ConsoleLogUser.__init__(self, console_log)
        gutils.TooltipsUser.__init__(self, tooltips)
        self._pm_ifce = pm_ifce
        self._scm_ifce = scm_ifce
        self.list_view = PatchListView(self._pm_ifce, self._scm_ifce)
        # file tree menu bar
        self.menu_bar = self.list_view.get_ui_widget("/patch_list_menubar")
        self.pack_start(self.menu_bar, expand=False)
        self.pack_start(gutils.wrap_in_scrolled_window(self.list_view))

class PatchManagementWidget(gtk.VBox, console.ConsoleLogUser, gutils.TooltipsUser):
    def __init__(self, pm_ifce, scm_ifce, tooltips=None, console_log=None):
        gtk.VBox.__init__(self)
        console.ConsoleLogUser.__init__(self, console_log)
        gutils.TooltipsUser.__init__(self, tooltips)
        self._pm_ifce = pm_ifce
        self._scm_ifce = scm_ifce
        self._file_tree = PatchFilesWidget(pm_ifce=self._pm_ifce, auto_refresh=False,
            console_log=self._console_log, tooltips=self._tooltips)
        self._patch_list = PatchListWidget(pm_ifce=self._pm_ifce, scm_ifce=self._scm_ifce,
            console_log=self._console_log, tooltips=self._tooltips)
        self._menu_bar = self._patch_list.list_view.get_ui_widget("/patches_menubar")
        self._tool_bar = self._patch_list.list_view.get_ui_widget("/patches_toolbar")
        self._tool_bar.set_icon_size(gtk.ICON_SIZE_SMALL_TOOLBAR)
        #self._tool_bar.set_style(gtk.TOOLBAR_BOTH_HORIZ)
        self.pack_start(self._menu_bar, expand=False)
        self.pack_start(self._tool_bar, expand=False)
        hpane = gtk.HPaned()
        hpane.add1(self._file_tree)
        hpane.add2(self._patch_list)
        self.pack_start(hpane)

class PatchDescrEditWidget(gtk.VBox, cmd_result.ProblemReporter):
    def __init__(self, patch, scm_ifce, pm_ifce, tooltips=None):
        gtk.VBox.__init__(self)
        cmd_result.ProblemReporter.__init__(self)
        self._scm_ifce = scm_ifce
        # TextView for change message
        self.view = text_edit.PatchSummaryView(patch, scm_ifce, pm_ifce)
        hbox = gtk.HBox()
        menubar = self.view.get_ui_widget("/patch_summary_menubar")
        hbox.pack_start(menubar, fill=True, expand=False)
        toolbar = self.view.get_ui_widget("/patch_summary_toolbar")
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        hbox.pack_end(toolbar, fill=False, expand=False)
        self.pack_start(hbox, expand=False)
        self.pack_start(gutils.wrap_in_scrolled_window(self.view))
        self.show_all()
        self.view.load_summary()
        self.set_focus_child(self.view)
    def get_save_button(self):
        return self.view.save_button

class PatchDescrEditDialog(gtk.Dialog):
    def __init__(self, patch, parent, scm_ifce, pm_ifce, modal=False):
        if modal:
            flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
        else:
            flags = gtk.DIALOG_DESTROY_WITH_PARENT
        gtk.Dialog.__init__(self, "\"%s\" Description: %s" % (patch, utils.path_rel_home(os.getcwd())),
            parent, flags, None)
        self.edit_descr_widget = PatchDescrEditWidget(patch, scm_ifce, pm_ifce, tooltips=None)
        self.vbox.pack_start(self.edit_descr_widget)
        self.action_area.pack_start(self.edit_descr_widget.get_save_button())
        self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.connect("response", self._handle_response_cb)
        self.set_focus_child(self.edit_descr_widget.view)
    def _handle_response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_CLOSE:
            if self.edit_descr_widget.view.get_buffer().get_modified():
                qn = os.linesep.join(["Unsaved changes to summary will be lost.", "Close anyway?"])
                if gutils.ask_yes_no(qn):
                    self.destroy()
            else:
                self.destroy()

