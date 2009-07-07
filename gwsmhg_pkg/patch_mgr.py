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

import gtk, gobject, pango, os, tempfile, re
from gwsmhg_pkg import dialogue, ifce, cmd_result, gutils, file_tree, icons, utils
from gwsmhg_pkg import text_edit, change_set, diff, path, tortoise, ws_event
from gwsmhg_pkg import actions

class PatchFileTreeStore(file_tree.FileTreeStore):
    def __init__(self, patch=None, view=None, rootdir=None):
        self._patch = patch
        row_data = apply(file_tree.FileTreeRowData, ifce.PM.get_status_row_data())
        file_tree.FileTreeStore.__init__(self, show_hidden=True, row_data=row_data,
                                         rootdir=rootdir)
        # if this is set to the associated view then the view will expand
        # to show new files without disturbing other expansion states
        self._view = view
    def set_view(self, view):
        self._view = view
    def update(self, fsobj_iter=None):
        res, dflist, dummy = ifce.PM.get_file_status_list(self._patch,
                                                          rootdir=self._rootdir)
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
    </placeholder>
    <placeholder name="unique_selection">
    </placeholder>
    <placeholder name="no_selection">
      <menuitem action="pm_diff_files_all"/>
    </placeholder>
  </popup>
</ui>
'''

class PatchFileTreeView(file_tree.CwdFileTreeView):
    def __init__(self, busy_indicator, patch=None, rootdir=None):
        self._patch = patch
        model = PatchFileTreeStore(patch=patch, rootdir=rootdir)
        file_tree.CwdFileTreeView.__init__(self, busy_indicator=busy_indicator, model=model,
             auto_refresh=False, show_status=True, rootdir=rootdir)
        model.set_view(self)
        self.add_conditional_actions(actions.ON_IN_REPO_PMIC_SELN,
            [
                ("pm_diff_files_selection", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for selected file(s)", self.diff_selected_files_acb),
            ])
        self.add_conditional_actions(actions.ON_IN_REPO_PMIC_NO_SELN,
            [
                ("pm_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self.diff_all_files_acb),
            ])
        self.add_conditional_actions(actions.ON_IN_REPO_PMIC_SELN_INDEP,
            [
                ("menu_files", None, "_Files"),
            ])
        model.show_hidden_action.set_visible(False)
        model.show_hidden_action.set_sensitive(False)
        self.get_conditional_action("new_file").set_visible(False)
        self.get_conditional_action("edit_files").set_visible(False)
        self.get_conditional_action("delete_files").set_visible(False)
        model.repopulate()
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(PATCH_FILES_UI_DESCR)
    def diff_selected_files_acb(self, action=None):
        dialog = diff.PmDiffTextDialog(parent=dialogue.main_window,
                                       patch=self._patch,
                                       file_list=self.get_selected_files(),
                                       rootdir=self._rootdir)
        dialog.show()
    def diff_all_files_acb(self, action=None):
        dialog = diff.PmDiffTextDialog(parent=dialogue.main_window,
                                       patch=self._patch, rootdir=self._rootdir)
        dialog.show()

class PatchFilesDialog(dialogue.AmodalDialog):
    def __init__(self, patch, rootdir=None):
        dialogue.AmodalDialog.__init__(self, None, None,
                                       gtk.DIALOG_DESTROY_WITH_PARENT,
                                       (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE),
                                       rootdir=rootdir)
        self.set_title('patch: %s files: %s' % (patch, self._rel_rootdir))
        # file tree view wrapped in scrolled window
        self.file_tree = PatchFileTreeView(busy_indicator=self, patch=patch,
                                           rootdir=self._rootdir)
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

class TopPatchFileTreeView(file_tree.CwdFileTreeView):
    def __init__(self, busy_indicator, auto_refresh=False, rootdir=None):
        model = PatchFileTreeStore(rootdir=rootdir)
        file_tree.CwdFileTreeView.__init__(self, busy_indicator=busy_indicator,
            model=model, auto_refresh=auto_refresh, show_status=True,
            rootdir=rootdir)
        model.set_view(self)
        self.move_conditional_action('new_file', actions.ON_IN_REPO_PMIC_SELN_INDEP)
        self.add_conditional_actions(actions.ON_IN_REPO_PMIC_SELN,
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
        self.add_conditional_actions(actions.ON_IN_REPO_PMIC_UNIQUE_SELN,
            [
                ("pm_rename_file", gtk.STOCK_PASTE, "Re_name/Move", None,
                 "Rename/move the selected file", self.move_selected_files_acb),
            ])
        self.add_conditional_actions(actions.ON_IN_REPO_PMIC_NO_SELN,
            [
                ("pm_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self.diff_all_files_acb),
                ("pm_revert_files_all", gtk.STOCK_UNDO, "Rever_t", None,
                 "Revert all changes in working directory", self.revert_all_files_acb),
            ])
        self.add_conditional_actions(actions.ON_IN_REPO_PMIC_SELN_INDEP,
            [
                ("menu_files", None, "_Files"),
            ])
        model.show_hidden_action.set_visible(False)
        model.show_hidden_action.set_sensitive(False)
        model.repopulate()
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(PM_FILES_UI_DESCR)
        self.add_notification_cb(ws_event.CHECKOUT|ws_event.CHANGE_WD, self.repopulate_tree)
        self.add_notification_cb(ws_event.FILE_CHANGES, self.update_tree)
        self._event_cond_change_cb()
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
    def create_new_file(self, new_file_name, open_for_edit=False):
        result = file_tree.CwdFileTreeView.create_new_file(self, new_file_name, open_for_edit)
        if not result[0]:
            result = ifce.PM.do_add_files([new_file_name], rootdir=self._rootdir)
            dialogue.report_any_problems(result)
        return result
    def delete_files(self, file_list):
        return ifce.PM.do_delete_files(file_list, rootdir=self._rootdir)
    def _remove_named_files(self, file_list, ask=True):
        if not ask or self._confirm_list_action(file_list, "About to be removed. OK?"):
            model = self.get_model()
            self.show_busy()
            result = ifce.PM.do_remove_files(file_list, rootdir=self._rootdir)
            self.show_busy()
            if self._check_if_force(result):
                result = ifce.PM.do_remove_files(file_list, force=True, rootdir=self._rootdir)
            self.update_tree()
            dialogue.report_any_problems(result)
    def remove_selected_files_acb(self, menu_item):
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
            if self._rootdir:
                dialog.set_current_folder(self._rootdir)
            else:
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
            operation = ifce.PM.do_copy_files
        elif reqop == "m":
            operation = ifce.PM.do_move_files
        else:
            raise "Invalid operation requested"
        response, target = self._get_target(file_list)
        if response == gtk.RESPONSE_OK:
            force = False
            if ask:
                while True:
                    self.show_busy()
                    res, sout, serr = operation(file_list, target, force=force,
                                                dry_run=True, rootdir=self._rootdir)
                    self.unshow_busy()
                    if res == cmd_result.OK:
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
                    response = operation(file_list, target, force=force, rootdir=self._rootdir)
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
        dialog = diff.PmDiffTextDialog(parent=dialogue.main_window,
                                       file_list=self.get_selected_files(),
                                       rootdir=self._rootdir)
        dialog.show()
    def diff_all_files_acb(self, action=None):
        dialog = diff.PmDiffTextDialog(parent=dialogue.main_window,
                                       rootdir=self._rootdir)
        dialog.show()
    def revert_named_files(self, file_list, ask=True):
        if ask:
            self.show_busy()
            res, sout, serr = ifce.PM.do_revert_files(file_list, dry_run=True,
                                                      rootdir=self._rootdir)
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
            result = ifce.PM.do_revert_files(file_list, rootdir=self._rootdir)
            self.get_model().del_files_from_displayable_nonexistants(file_list)
            self.show_busy()
            self.update_tree()
            dialogue.report_any_problems(result)
    def revert_selected_files_acb(self, action=None):
        self.revert_named_files(self.get_selected_files())
    def revert_all_files_acb(self, action=None):
        self.revert_named_files([])

class TopPatchFilesWidget(gtk.VBox):
    def __init__(self, busy_indicator, auto_refresh=False, rootdir=None):
        gtk.VBox.__init__(self)
        # file tree view wrapped in scrolled window
        self.file_tree = TopPatchFileTreeView(busy_indicator=busy_indicator,
            auto_refresh=auto_refresh, rootdir=rootdir)
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

PM_PATCHES_UI_DESCR = \
'''
<ui>
  <menubar name="patches_menubar">
    <menu name="patches_menu" action="menu_patches">
      <menuitem action="pm_pop_all"/>
      <menuitem action="pm_push_all"/>
      <menuitem action="pm_import_patch_series"/>
    </menu>
    <menu name="patches_ws_menu" action="menu_patches_ws">
      <menuitem action="save_queue_state_for_update"/>
      <menuitem action="pm_pull_to_repository"/>
      <menuitem action="pm_update_workspace"/>
      <menuitem action="pm_update_workspace_to"/>
      <menuitem action="pm_push_all_with_merge"/>
      <menuitem action="pm_clean_up_after_update"/>
    </menu>
  </menubar>
  <toolbar name="patches_toolbar">
    <toolitem name="Refresh" action="pm_refresh_top_patch"/>
    <toolitem name="Push" action="pm_push"/>
    <toolitem name="Pop" action="pm_pop"/>
    <separator/>
    <toolitem name="PushMerge" action="pm_push_merge"/>
    <separator/>
    <toolitem name="New" action="pm_new"/>
    <toolitem name="Import" action="pm_import_external_patch"/>
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
      <menuitem action="pm_view_patch_diff"/>
      <menuitem action="pm_rename_patch"/>
    </placeholder>
    <separator/>
    <placeholder name="unapplied">
      <menuitem action="pm_delete_patch"/>
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
POP_NOT_POSSIBLE = "pm_pop_not_possible"
PUSH_POP_INDIFFERENT = "pm_push_pop_indifferent"
WS_UPDATE_QSAVE_READY = "pm_ws_update_qsave_ready"
WS_UPDATE_PULL_READY = "pm_ws_update_pull_ready"
WS_UPDATE_READY = "pm_ws_update_ready"
WS_UPDATE_TO_READY = "pm_ws_update_to_ready"
WS_UPDATE_MERGE_READY = "pm_ws_update_merge_ready"
WS_UPDATE_CLEAN_UP_READY = "pm_ws_update_clean_up_ready"

APPLIED_CONDITIONS = [
    APPLIED,
    UNAPPLIED,
    UNAPPLIED_AND_INTERDIFF,
    APPLIED_INDIFFERENT,
]

PUSH_POP_CONDITIONS = [
    PUSH_POSSIBLE,
    PUSH_NOT_POSSIBLE,
    POP_POSSIBLE,
    POP_NOT_POSSIBLE,
    PUSH_POP_INDIFFERENT,
]

WS_UPDATE_CONDITIONS = [
    WS_UPDATE_QSAVE_READY,
    WS_UPDATE_PULL_READY,
    WS_UPDATE_READY,
    WS_UPDATE_TO_READY,
    WS_UPDATE_MERGE_READY,
    WS_UPDATE_CLEAN_UP_READY,
]

class PatchListView(gtk.TreeView, dialogue.BusyIndicatorUser, ws_event.Listener):
    def __init__(self, busy_indicator, rootdir=None):
        self._rootdir = rootdir
        self.store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_INT,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING)
        gtk.TreeView.__init__(self, self.store)
        ws_event.Listener.__init__(self)
        dialogue.BusyIndicatorUser.__init__(self, busy_indicator)
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
        self.ui_manager = gtk.UIManager()
        self._action_group = {}
        for condition in APPLIED_CONDITIONS + PUSH_POP_CONDITIONS + WS_UPDATE_CONDITIONS:
            self._action_group[condition] = gtk.ActionGroup(condition)
            self.ui_manager.insert_action_group(self._action_group[condition], -1)
        self._action_group[APPLIED].add_actions(
            [
                ("pm_pop_to_patch", icons.STOCK_POP_PATCH, "QPop To", None,
                 "Pop to the selected patch", self.do_pop_to),
                ("pm_finish_to", icons.STOCK_FINISH_PATCH, "QFinish To", None,
                 "Move patches up to the selected patch into main repository", self.do_finish_to),
            ])
        self._action_group[APPLIED_INDIFFERENT].add_actions(
            [
                ("pm_edit_patch_descr", gtk.STOCK_EDIT, "Description", None,
                 "Edit the selected patch's description", self.do_edit_description),
                ("pm_view_patch_files", gtk.STOCK_FILE, "Files", None,
                 "Show files affected by the selected patch", self.show_files),
                ("pm_view_patch_diff", icons.STOCK_DIFF, "Diff", None,
                 "Show diff for the selected patch", self.show_diff_acb),
                ("pm_rename_patch", None, "QRename", None,
                 "Rename the selected patch", self.do_rename),
            ])
        self._action_group[UNAPPLIED].add_actions(
            [
                ("pm_delete_patch", gtk.STOCK_DELETE, "QDelete", None,
                 "Delete the selected patch", self.do_delete),
                ("pm_push_to", icons.STOCK_PUSH_PATCH, "QPush To", None,
                 "Push to the selected patch", self.do_push_to),
                ("pm_fold", icons.STOCK_FOLD_PATCH, "QFold", None,
                 "Fold the selected patch into the top patch", self.do_fold),
                ("pm_fold_to", icons.STOCK_FOLD_PATCH, "QFold To", None,
                 "Fold patches up to the selected patch into the top patch", self.do_fold_to),
                ("pm_duplicate", gtk.STOCK_COPY, "Duplicate", None,
                 "Duplicate the selected patch behind the top patch", self.do_duplicate),
            ])
        self._action_group[UNAPPLIED_AND_INTERDIFF].add_actions(
            [
                ("pm_interdiff", gtk.STOCK_PASTE, "Interdiff", None,
                 'Place the "interdiff" of the selected patch and the top patch behind the top patch', self.do_interdiff),
            ])
        self._action_group[PUSH_POSSIBLE].add_actions(
            [
                ("pm_push", icons.STOCK_PUSH_PATCH, "QPush", None,
                 "Apply the next unapplied patch", self.do_push),
                ("pm_push_all", icons.STOCK_PUSH_PATCH, "QPush All", None,
                 "Apply all remaining unapplied patches", self.do_push_all),
            ])
        self._action_group[WS_UPDATE_MERGE_READY].add_actions(
            [
                ("pm_push_merge", icons.STOCK_PUSH_PATCH, "QPush (Merge)", None,
                 "Apply the next unapplied patch merging with equivalent saved patch", self.do_push_merge),
                ("pm_push_all_with_merge", icons.STOCK_PUSH_PATCH, "QPush All (Merge)", None,
                 "Apply all remaining unapplied patches with \"merge\" option enabled", self.do_push_all_with_merge),
            ])
        self._action_group[WS_UPDATE_QSAVE_READY].add_actions(
            [
                ("save_queue_state_for_update", None, "QSave For Update", None,
                 "Save the queue state prepatory to update", self.do_save_queue_state_for_update),
            ])
        self._action_group[POP_POSSIBLE].add_actions(
            [
                ("pm_pop", icons.STOCK_POP_PATCH, "QPop", None,
                 "Pop the top applied patch", self.do_pop),
                ("pm_pop_all", icons.STOCK_POP_PATCH, "QPop All", None,
                 "Pop all remaining applied patches", self.do_pop_all),
                ("pm_refresh_top_patch", gtk.STOCK_REFRESH, "QRefresh", None,
                 "Refresh the top patch", self.do_refresh),
            ])
        self._action_group[WS_UPDATE_READY].add_actions(
            [
                ("pm_update_workspace", None, "Update Workspace", None,
                 "Update the workspace to the repository tip", self.do_update_workspace),
            ])
        self._action_group[WS_UPDATE_TO_READY].add_actions(
            [
                ("pm_update_workspace_to", None, "Update Workspace To", None,
                 "Update the workspace to a specified revision", self.do_update_workspace_to),
            ])
        self._action_group[WS_UPDATE_PULL_READY].add_actions(
            [
                ("pm_pull_to_repository", None, "Pull To Workspace", None,
                 "Pull to the repository from the default remote path", self.do_pull_to_repository),
            ])
        self._action_group[PUSH_POP_INDIFFERENT].add_actions(
            [
                ("menu_patches", None, "_Patches"),
                ("menu_patches_ws", None, "_Workspace Update"),
                ("menu_patch_list", None, "Patch _List"),
                ("refresh_patch_list", gtk.STOCK_REFRESH, "Update Patch List", None,
                 "Refresh/update the patch list display", self.set_contents),
                ("pm_new", gtk.STOCK_ADD, "New", None,
                 "Create a new patch", self.do_new_patch),
                ("pm_import_external_patch", icons.STOCK_IMPORT_PATCH, "QImport", None,
                 "Import an external patch", self.do_import_external_patch),
                ("pm_import_patch_series", icons.STOCK_IMPORT_PATCH, "QImport Patch Series", None,
                 "Import an external patch (mq/quilt style) series", self.do_import_external_patch_series),
            ])
        self._action_group[WS_UPDATE_CLEAN_UP_READY].add_actions(
            [
                ("pm_clean_up_after_update", gtk.STOCK_CLEAR, "Clean Up", None,
                 "Clean up left over heads after repostory and patch series update", self.do_clean_up_after_update),
            ])
        toggle_data = range(4)
        toggle_data[gutils.TOC_NAME] = "auto_refresh_patch_list"
        toggle_data[gutils.TOC_LABEL] = "Auto Update"
        toggle_data[gutils.TOC_TOOLTIP] = "Enable/disable automatic updating of the patch list"
        toggle_data[gutils.TOC_STOCK_ID] = gtk.STOCK_REFRESH
        self.toc = gutils.TimeOutController(toggle_data, function=self.set_contents, is_on=False)
        self._action_group[PUSH_POP_INDIFFERENT].add_action(self.toc.toggle_action)
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(PM_PATCHES_UI_DESCR)
        self.get_selection().connect("changed", self._selection_changed_cb)
        self.applied_count = self.unapplied_count = 0
        self.set_contents()
        self.get_selection().unselect_all()
        self._selection_changed_cb(self.get_selection())
        self.connect("button_press_event", self._handle_button_press_cb)
        self.connect("key_press_event", self._handle_key_press_cb)
        self.add_notification_cb(ws_event.REPO_MOD, self.update_in_repo_sensitivity)
        self.add_notification_cb(ws_event.CHANGE_WD, self.update_for_chdir)
        self.update_in_repo_sensitivity()
    def update_for_chdir(self):
        self.show_busy()
        self.update_in_repo_sensitivity()
        self.set_contents()
        self.unshow_busy()
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
                menu = self.ui_manager.get_widget("/patches_popup")
                menu.popup(None, None, None, event.button, event.time)
                return True
            elif event.button == 2:
                self.get_selection().unselect_all()
                return True
        return False
    def _handle_key_press_cb(self, widget, event):
        if event.keyval == gtk.gdk.keyval_from_name('Escape'):
            self.get_selection().unselect_all()
            return True
        return False
    def get_selected_patch(self):
        model, iter = self.get_selection().get_selected()
        if iter is None:
            return None
        else:
            return model.get_value(iter, 0)
    def _set_ws_update_menu_sensitivity(self):
        self._action_group[WS_UPDATE_QSAVE_READY].set_sensitive(
            ifce.PM.get_ws_update_qsave_ready(unapplied_count=self.unapplied_count,
                                              applied_count=self.applied_count,
                                              rootdir=self._rootdir))
        self._action_group[WS_UPDATE_PULL_READY].set_sensitive(
            ifce.PM.get_ws_update_pull_ready(applied_count=self.applied_count,
                                             rootdir=self._rootdir))
        self._action_group[WS_UPDATE_TO_READY].set_sensitive(
            ifce.PM.get_ws_update_to_ready(applied_count=self.applied_count,
                                           rootdir=self._rootdir))
        self._action_group[WS_UPDATE_READY].set_sensitive(
            ifce.PM.get_ws_update_ready(applied_count=self.applied_count,
                                        rootdir=self._rootdir))
        self._action_group[WS_UPDATE_MERGE_READY].set_sensitive(
            ifce.PM.get_ws_update_merge_ready(unapplied_count=self.unapplied_count,
                                              rootdir=self._rootdir))
        self._action_group[WS_UPDATE_CLEAN_UP_READY].set_sensitive(
            ifce.PM.get_ws_update_clean_up_ready(rootdir=self._rootdir))
    def _in_valid_repo(self):
        if self._rootdir:
            return True
        else:
            return ifce.in_valid_repo
    def update_in_repo_sensitivity(self):
        if self._in_valid_repo():
            self._selection_changed_cb(self.get_selection())
            self._set_ws_update_menu_sensitivity()
            self._action_group[PUSH_POP_INDIFFERENT].set_sensitive(True)
        else:
            for condition in APPLIED_CONDITIONS + PUSH_POP_CONDITIONS + WS_UPDATE_CONDITIONS:
                self._action_group[condition].set_sensitive(False)
    def set_contents(self, action=None):
        self.show_busy()
        applied_patch_list = ifce.PM.get_applied_patches(rootdir=self._rootdir)
        unapplied_patch_list = ifce.PM.get_unapplied_patches(rootdir=self._rootdir)
        self.store.clear()
        for patch_name in applied_patch_list:
            self.store.append([patch_name, pango.STYLE_NORMAL, "black", icons.STOCK_APPLIED])
        self.applied_count = len(applied_patch_list)
        self._action_group[POP_POSSIBLE].set_sensitive(self.applied_count > 0)
        self._action_group[POP_NOT_POSSIBLE].set_sensitive(self.applied_count == 0)
        for patch_name in unapplied_patch_list:
            self.store.append([patch_name, pango.STYLE_ITALIC, "dark grey", None])
        self.unapplied_count = len(unapplied_patch_list)
        self._action_group[PUSH_POSSIBLE].set_sensitive(self.unapplied_count > 0)
        self._action_group[PUSH_NOT_POSSIBLE].set_sensitive(self.unapplied_count == 0)
        self._set_ws_update_menu_sensitivity()
        self.get_selection().unselect_all()
        self.unshow_busy()
    def do_refresh(self, action=None):
        self.show_busy()
        res, sout, serr = ifce.PM.do_refresh(rootdir=self._rootdir)
        if res is not cmd_result.OK:
            self.unshow_busy()
            if res & cmd_result.SUGGEST_RECOVER:
                if dialogue.ask_recover_or_cancel(os.linesep.join([sout, serr])) is dialogue.RESPONSE_RECOVER:
                    self.show_busy()
                    res, sout, serr = ifce.PM.do_recover_interrupted_refresh()
                    if res is cmd_result.OK:
                        res, sout, serr = ifce.PM.do_refresh(rootdir=self._rootdir)
                    self.unshow_busy()
            if res is not cmd_result.OK: # There're may still be problems
                dialogue.report_any_problems((res, sout, serr))
                return
        else:
            self.unshow_busy()        
    def _do_pop_to(self, patch=None):
        while True:
            self.show_busy()
            res, sout, serr = ifce.PM.do_pop_to(patch=patch, rootdir=self._rootdir)
            self.unshow_busy()
            self.set_contents()
            if res is not cmd_result.OK:
                if res & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                    ans = dialogue.ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res)
                    if ans is gtk.RESPONSE_CANCEL:
                        return False
                    elif ans is dialogue.RESPONSE_REFRESH:
                        self.do_refresh()
                        continue
                    elif ans is dialogue.RESPONSE_FORCE:
                        self.show_busy()
                        res, sout, serr = ifce.PM.do_pop_to(force=True, rootdir=self._rootdir)
                        self.unshow_busy()
                if res is not cmd_result.OK: # there're are still problems
                    dialogue.report_any_problems((res, sout, serr))
                    return False
            return True
    def do_pop_to(self, action=None):
        patch = self.get_selected_patch()
        while ifce.PM.get_top_patch(rootdir=self._rootdir) != patch:
            if not self._do_pop_to(patch):
                break
    def do_pop(self, action=None):
        self._do_pop_to()
    def do_pop_all(self, action=None):
        self._do_pop_to("")
    def _do_push_to(self, patch=None, merge=False):
        while True:
            self.show_busy()
            res, sout, serr = ifce.PM.do_push_to(patch=patch, merge=merge, rootdir=self._rootdir)
            self.unshow_busy()
            self.set_contents()
            if res is not cmd_result.OK:
                if res & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                    ans = dialogue.ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res, parent=None)
                    if ans is gtk.RESPONSE_CANCEL:
                        return False
                    if ans is dialogue.RESPONSE_REFRESH:
                        self.do_refresh()
                        continue
                    elif ans is dialogue.RESPONSE_FORCE:
                        self.unshow_busy()
                        res, sout, serr = ifce.PM.do_push_to(force=True, merge=merge,
                                                             rootdir=self._rootdir)
                        self.unshow_busy()
                if res is not cmd_result.OK: # there're are still problems
                    dialogue.report_any_problems((res, sout, serr))
                    return False
            return True
    def do_push_to(self, action=None):
        patch = self.get_selected_patch()
        while ifce.PM.get_top_patch(rootdir=self._rootdir) != patch:
            if not self._do_push_to(patch):
                break
    def do_push(self, action=None):
        self._do_push_to()
    def do_push_merge(self, action=None):
        self._do_push_to(merge=True)
    def do_push_all(self, action=None):
        self._do_push_to("", merge=False)
    def do_push_all_with_merge(self, action=None):
        self._do_push_to("", merge=True)
    def do_finish_to(self, action=None):
        patch = self.get_selected_patch()
        while True:
            next = ifce.PM.get_base_patch(rootdir=self._rootdir)
            if not next:
                break
            while True:
                self.show_busy()
                ok = ifce.PM.get_description_is_finish_ready(next, rootdir=self._rootdir)
                self.unshow_busy()
                if ok:
                    break
                msg = os.linesep.join(
                    ['"%s" has an empty description.' % next,
                     "Do you wish to:",
                     "\tcancel,",
                     "\tedit the description and retry, or",
                     "\tforce the finish operation?"
                    ])
                ans = dialogue.ask_edit_force_or_cancel(msg, parent=None)
                if ans == gtk.RESPONSE_CANCEL:
                    return
                elif ans == dialogue.RESPONSE_FORCE:
                    break
                self.do_edit_description_wait(next)
            self.show_busy()
            res, sout, serr = ifce.PM.do_finish_patch(next, rootdir=self._rootdir)
            self.set_contents()
            self.unshow_busy()
            if res is not cmd_result.OK:
                dialogue.report_any_problems((res, sout, serr))
                break
            if patch == next:
                break
    def do_edit_description_wait(self, patch=None):
        if not patch:
            patch = self.get_selected_patch()
        PatchDescrEditDialog(patch, parent=None, rootdir=self._rootdir).run()
    def do_edit_description(self, action=None):
        patch = self.get_selected_patch()
        PatchDescrEditDialog(patch, parent=None, rootdir=self._rootdir).show()
    def show_files(self, action=None):
        patch = self.get_selected_patch()
        dialog = PatchFilesDialog(patch=patch, rootdir=self._rootdir)
        dialog.show()
    def show_diff_acb(self, action=None):
        patch = self.get_selected_patch()
        dialog = diff.PmDiffTextDialog(parent=dialogue.main_window, patch=patch,
                                       rootdir=self._rootdir)
        dialog.show()
    def do_rename(self, action=None):
        patch = self.get_selected_patch()
        dialog = dialogue.ReadTextDialog("Rename Patch: %s" % patch, "New Name:", patch)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            new_name = dialog.entry.get_text()
            dialog.destroy()
            if patch == new_name:
                return
            res, sout, serr = ifce.PM.do_rename_patch(patch, new_name, rootdir=self._rootdir)
            dialogue.report_any_problems((res, sout, serr))
            self.set_contents()
        else:
            dialog.destroy()
    def do_delete(self, action=None):
        patch = self.get_selected_patch()
        res, sout, serr = ifce.PM.do_delete_patch(patch, rootdir=self._rootdir)
        dialogue.report_any_problems((res, sout, serr))
        self.set_contents()
    def do_fold(self, action=None):
        patch = self.get_selected_patch()
        res, sout, serr = ifce.PM.do_fold_patch(patch, rootdir=self._rootdir)
        dialogue.report_any_problems((res, sout, serr))
        self.set_contents()
    def do_fold_to(self, action=None):
        patch = self.get_selected_patch()
        while True:
            next = ifce.PM.get_next_patch(rootdir=self._rootdir)
            if not next:
                return
            res, sout, serr = ifce.PM.do_fold_patch(next, rootdir=self._rootdir)
            if res is not cmd_result.OK:
                dialogue.report_any_problems((res, sout, serr))
                return
            self.set_contents()
            if patch == next:
                return
    def do_duplicate(self, action=None):
        patch = self.get_selected_patch()
        dialog = DuplicatePatchDialog(patch, parent=None)
        if dialog.run() == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return
        duplicate_patch_name = dialog.get_duplicate_patch_name()
        duplicate_patch_descr = dialog.get_duplicate_patch_descr()
        dialog.destroy()
        if not duplicate_patch_name:
            return
        self.show_busy()
        old_pfname = ifce.PM.get_patch_file_name(patch, rootdir=self._rootdir)
        res, sout, serr = ifce.PM.do_import_patch(old_pfname, duplicate_patch_name,
                                                  rootdir=self._rootdir)
        self.unshow_busy()
        if res == cmd_result.ERROR_SUGGEST_FORCE:
            if ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res) == dialogue.RESPONSE_FORCE:
                self.show_busy()
                res, sout, serr = ifce.PM.do_import_patch(old_pfname, duplicate_patch_name,
                                                          force=True, rootdir=self._rootdir)
                self.unshow_busy()
            else:
                return
        self.set_contents()
        if res is not cmd_result.OK:
            dialogue.report_any_problems((res, sout, serr))
            if res & cmd_result.ERROR:
                return
        self.show_busy()
        res, sout, serr = ifce.PM.do_set_patch_description(duplicate_patch_name,
                                                           duplicate_patch_descr,
                                                           rootdir=self._rootdir)
        self.unshow_busy()
        dialogue.report_any_problems((res, sout, serr))
    def do_interdiff(self, action=None):
        patch = self.get_selected_patch()
        dialog = DuplicatePatchDialog(patch, verb="Interdiff", parent=None)
        if dialog.run() == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return
        interdiff_patch_name = dialog.get_duplicate_patch_name()
        interdiff_patch_descr = dialog.get_duplicate_patch_descr()
        dialog.destroy()
        if not interdiff_patch_name:
            return
        self.show_busy()
        top_patch = ifce.PM.get_top_patch(rootdir=self._rootdir)
        if top_patch:
            top_pfname = ifce.PM.get_patch_file_name(top_patch, rootdir=self._rootdir)
            old_pfname = ifce.PM.get_patch_file_name(patch, rootdir=self._rootdir)
            res, diff, serr = utils.run_cmd("interdiff %s %s" % (top_pfname, old_pfname))
            if res is not cmd_result.OK:
                dialogue.report_any_problems((res, diff, serr))
                return
            temp_pfname = tempfile.mktemp()
            tf = open(temp_pfname, 'w')
            tf.write(os.linesep.join([interdiff_patch_descr, diff]))
            tf.close()
        else:
            temp_pfname = ifce.PM.get_patch_file_name(patch, rootdir=self._rootdir)
        res, sout, serr = ifce.PM.do_import_patch(temp_pfname, interdiff_patch_name,
                                                  rootdir=self._rootdir)
        self.unshow_busy()
        if res == cmd_result.ERROR_SUGGEST_FORCE:
            if ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res) == dialogue.RESPONSE_FORCE:
                self.show_busy()
                res, sout, serr = ifce.PM.do_import_patch(temp_pfname, interdiff_patch_name, force=True,
                                                          rootdir=self._rootdir)
                self.unshow_busy()
        if top_patch:
            os.remove(temp_pfname)
        self.set_contents()
        if res is not cmd_result.OK:
            dialogue.report_any_problems((res, sout, serr))
    def do_save_queue_state_for_update(self, action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        self.show_busy()
        res, sout, serr = ifce.PM.do_save_queue_state_for_update(rootdir=self._rootdir)
        self.unshow_busy()
        self.set_contents()
        dialogue.report_any_problems((res, sout, serr))
    def do_pull_to_repository(self, action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        self.show_busy()
        dialog = path.PullDialog()
        self.unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            source = dialog.get_path()
            rev = dialog.get_revision()
            dialog.destroy()
            self.show_busy()
            result = ifce.PM.do_pull_from(source=source, rev=rev, rootdir=self._rootdir)
            self._set_ws_update_menu_sensitivity()
            self.unshow_busy()
            dialogue.report_any_problems(result)
        else:
            dialog.destroy()
    def do_update_workspace(self, action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        self.show_busy()
        result = ifce.PM.do_update_workspace(rootdir=self._rootdir)
        self._set_ws_update_menu_sensitivity()
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def do_update_workspace_to(self, action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        dialog = change_set.ChangeSetSelectDialog(rootdir=self._rootdir)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            rev = dialog.get_change_set()
            dialog.destroy()
            if rev:
                self.show_busy()
                result = ifce.PM.do_update_workspace(rev=rev, rootdir=self._rootdir)
                self._set_ws_update_menu_sensitivity()
                self.unshow_busy()
                dialogue.report_any_problems(result)
        else:
            dialog.destroy()
    def do_clean_up_after_update(self, action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        self.show_busy()
        result = ifce.PM.do_clean_up_after_update(rootdir=self._rootdir)
        self.unshow_busy()
        self.set_contents()
        dialogue.report_any_problems(result)
    def do_new_patch(self, action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        dialog = NewPatchDialog(parent=None)
        if dialog.run() == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return
        new_patch_name = dialog.get_new_patch_name()
        new_patch_descr = dialog.get_new_patch_descr()
        dialog.destroy()
        if not new_patch_name:
            return
        force = False
        while True:
            self.show_busy()
            res, sout, serr = ifce.PM.do_new_patch(new_patch_name, force=force,
                                                   rootdir=self._rootdir)
            self.unshow_busy()
            if res & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                ans = dialogue.ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res, parent=None)
                if ans is gtk.RESPONSE_CANCEL:
                    return
                if ans is dialogue.RESPONSE_REFRESH:
                    self.do_refresh(rootdir=self._rootdir)
                elif ans is dialogue.RESPONSE_FORCE:
                    force = True
            else:
                dialogue.report_any_problems((res, sout, serr))
                break
        self.set_contents()
        if new_patch_descr and res is not cmd_result.ERROR:
            self.show_busy()
            res, sout, serr = ifce.PM.do_set_patch_description(new_patch_name, new_patch_descr,
                                                               rootdir=self._rootdir)
            self.unshow_busy()
            dialogue.report_any_problems((res, sout, serr))
    def do_import_external_patch(self, action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        patch_file_name = dialogue.ask_file_name("Select patch file to be imported")
        if not patch_file_name:
            return
        force = False
        patch_name = None
        while True:
            self.show_busy()
            res, sout, serr = ifce.PM.do_import_patch(patch_file_name, patch_name, force,
                                                      rootdir=self._rootdir)
            self.unshow_busy()
            if res & cmd_result.SUGGEST_FORCE_OR_RENAME:
                question = os.linesep.join([sout, serr, "Force import of patch, rename patch or cancel import?"])
                ans = dialogue.ask_rename_force_or_cancel(question)
                if ans == gtk.RESPONSE_CANCEL:
                    return
                elif ans == dialogue.RESPONSE_FORCE:
                    force = True
                    continue
                elif ans == dialogue.RESPONSE_RENAME:
                    if not patch_name:
                        patch_name = os.path.basename(patch_file_name)
                    patch_name = dialogue.get_modified_string("Rename Patch", "New Name :", patch_name)
                    continue
            dialogue.report_any_problems((res, sout, serr))
            break
        self.set_contents()
    def do_import_external_patch_series(self, action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        patch_series_dir = dialogue.ask_dir_name("Select patch series to be imported")
        if not patch_series_dir:
            return
        series_fn = os.sep.join([patch_series_dir, "series"])
        if (not os.path.exists(series_fn) and os.path.isfile(series_fn)):
            dialogue.report_any_problems((cmd_result.ERROR, "", "Series file not found."))
            return
        sf = open(series_fn, 'r')
        series = sf.readlines()
        sf.close()
        series.reverse()
        index = 0
        patch_name_re = re.compile("\s*([^\s#]*)[\s#]*.*$")
        while index < len(series):
            match = patch_name_re.match(series[index])
            if not match:
                index += 1
                continue
            base_name = match.group(1)
            patch_file_name = os.sep.join([patch_series_dir, base_name])
            force = False
            patch_name = None
            while True:
                self.show_busy()
                res, sout, serr = ifce.PM.do_import_patch(patch_file_name, patch_name, force,
                                                          rootdir=self._rootdir)
                self.unshow_busy()
                if res & cmd_result.SUGGEST_FORCE_OR_RENAME:
                    question = os.linesep.join([sout, serr, "Force import of patch, rename patch or skip patch?"])
                    ans = dialogue.ask_rename_force_or_skip(question)
                    if ans == dialogue.RESPONSE_SKIP_ALL:
                        index = len(series)
                        break
                    elif ans == dialogue.RESPONSE_SKIP:
                        break
                    elif ans == dialogue.RESPONSE_FORCE:
                        force = True
                        continue
                    elif ans == dialogue.RESPONSE_RENAME:
                        if not patch_name:
                            patch_name = base_name
                        patch_name = dialogue.get_modified_string("Rename Patch", "New Name :", patch_name)
                        continue
                dialogue.report_any_problems((res, sout, serr))
                break
            self.set_contents()
            index += 1

class PatchListWidget(gtk.VBox):
    def __init__(self, busy_indicator, rootdir=None):
        gtk.VBox.__init__(self)
        self.list_view = PatchListView(busy_indicator=busy_indicator, rootdir=rootdir)
        # file tree menu bar
        self.menu_bar = self.list_view.ui_manager.get_widget("/patch_list_menubar")
        self.pack_start(self.menu_bar, expand=False)
        self.pack_start(gutils.wrap_in_scrolled_window(self.list_view))

class PatchManagementWidget(gtk.VBox):
    def __init__(self, busy_indicator=None, rootdir=None):
        gtk.VBox.__init__(self)
        self._file_tree = TopPatchFilesWidget(busy_indicator=busy_indicator,
            auto_refresh=False, rootdir=rootdir)
        self._patch_list = PatchListWidget(busy_indicator=busy_indicator,
                                           rootdir=rootdir)
        self._menu_bar = self._patch_list.list_view.ui_manager.get_widget("/patches_menubar")
        self._tool_bar = self._patch_list.list_view.ui_manager.get_widget("/patches_toolbar")
        #self._tool_bar.set_icon_size(gtk.ICON_SIZE_SMALL_TOOLBAR)
        #self._tool_bar.set_style(gtk.TOOLBAR_BOTH_HORIZ)
        self.pack_start(self._menu_bar, expand=False)
        self.pack_start(self._tool_bar, expand=False)
        hpane = gtk.HPaned()
        hpane.add1(self._file_tree)
        hpane.add2(self._patch_list)
        self.pack_start(hpane)

class NewPatchDescrEditWidget(gtk.VBox):
    def __init__(self, view=None):
        gtk.VBox.__init__(self)
        # TextView for change message
        if view:
            self.view = view
        else:
            self.view = text_edit.NewPatchSummaryView()
        hbox = gtk.HBox()
        menubar = self.view.ui_manager.get_widget("/patch_summary_menubar")
        hbox.pack_start(menubar, fill=True, expand=False)
        toolbar = self.view.ui_manager.get_widget("/patch_summary_toolbar")
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        hbox.pack_end(toolbar, fill=False, expand=False)
        self.pack_start(hbox, expand=False)
        self.pack_start(gutils.wrap_in_scrolled_window(self.view))
        self.show_all()
        self.set_focus_child(self.view)

class PatchDescrEditWidget(NewPatchDescrEditWidget):
    def __init__(self, get_summary, set_summary, patch=None, rootdir=None):
        self.view = text_edit.PatchSummaryView(get_summary, set_summary, patch,
                                               rootdir=rootdir)
        NewPatchDescrEditWidget.__init__(self, view=self.view)
        self.view.load_summary()
    def get_save_button(self):
        return self.view.save_button

class GenericPatchDescrEditDialog(dialogue.AmodalDialog):
    def __init__(self, get_summary, set_summary, parent, patch=None, rootdir=None):
        flags = gtk.DIALOG_DESTROY_WITH_PARENT
        dialogue.AmodalDialog.__init__(self, None, parent, flags, None, rootdir=rootdir)
        self.set_title('"%s" Description: %s' % (patch, self._rel_rootdir))
        self.edit_descr_widget = PatchDescrEditWidget(get_summary, set_summary,
                                                      patch, rootdir=self._rootdir)
        self.vbox.pack_start(self.edit_descr_widget)
        self.action_area.pack_start(self.edit_descr_widget.get_save_button())
        self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.connect("response", self._handle_response_cb)
        self.set_focus_child(self.edit_descr_widget.view)
    def _handle_response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_CLOSE:
            if self.edit_descr_widget.view.get_buffer().get_modified():
                qn = os.linesep.join(["Unsaved changes to summary will be lost.", "Close anyway?"])
                if dialogue.ask_yes_no(qn):
                    self.destroy()
            else:
                self.destroy()

class PatchDescrEditDialog(GenericPatchDescrEditDialog):
    def __init__(self, patch, parent, rootdir=None):
        GenericPatchDescrEditDialog.__init__(self,
            get_summary=ifce.PM.get_patch_description,
            set_summary=ifce.PM.do_set_patch_description,
            parent=parent, patch=patch, rootdir=rootdir)

class DuplicatePatchDialog(dialogue.Dialog):
    def __init__(self, patch, parent, verb="Duplicate"):
        flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
        title = '%s "%s": %s' % (verb, patch, utils.path_rel_home(os.getcwd()))
        dialogue.Dialog.__init__(self, title, parent, flags,
                                 (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                  gtk.STOCK_OK, gtk.RESPONSE_OK))
        hbox = gtk.HBox()
        vbox = gtk.VBox()
        vbox.pack_start(gtk.Label('%s Patch:' % verb))
        vbox.pack_start(gtk.Label(' As Patch Named:'))
        hbox.pack_start(vbox, fill=False, expand=False)
        vbox = gtk.VBox()
        entry = gtk.Entry()
        entry.set_text(patch)
        entry.set_editable(False)
        vbox.pack_start(entry)
        self.new_name_entry = gtk.Entry()
        self.new_name_entry.set_width_chars(32)
        vbox.pack_start(self.new_name_entry)
        hbox.pack_start(vbox)
        hbox.show_all()
        self.vbox.pack_start(hbox)
        self.edit_descr_widget = NewPatchDescrEditWidget()
        res, old_descr, serr = ifce.PM.get_patch_description(patch)
        if not res:
            self.edit_descr_widget.view.get_buffer().set_text(old_descr)
        self.vbox.pack_start(self.edit_descr_widget)
        self.set_focus_child(self.new_name_entry)
    def get_duplicate_patch_name(self):
        return self.new_name_entry.get_text()
    def get_duplicate_patch_descr(self):
        return self.edit_descr_widget.view.get_msg()

class NewPatchDialog(dialogue.Dialog):
    def __init__(self, parent, objname="Patch"):
        flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
        title = 'New %s: %s -- gwsmhg' % (objname, utils.path_rel_home(os.getcwd()))
        dialogue.Dialog.__init__(self, title, parent, flags,
                                 (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                  gtk.STOCK_OK, gtk.RESPONSE_OK))
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        self.hbox = gtk.HBox()
        self.hbox.pack_start(gtk.Label('New %s Name:' % objname), fill=False, expand=False)
        self.new_name_entry = gtk.Entry()
        self.new_name_entry.set_width_chars(32)
        self.hbox.pack_start(self.new_name_entry)
        self.hbox.show_all()
        self.vbox.pack_start(self.hbox)
        self.edit_descr_widget = NewPatchDescrEditWidget()
        self.vbox.pack_start(self.edit_descr_widget)
        self.set_focus_child(self.new_name_entry)
    def get_new_patch_name(self):
        return self.new_name_entry.get_text()
    def get_new_patch_descr(self):
        return self.edit_descr_widget.view.get_msg()

