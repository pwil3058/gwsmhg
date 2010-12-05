### Copyright (C) 2010 Peter Williams <peter_ono@users.sourceforge.net>

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

import collections, gtk, gobject, os

from gwsmhg_pkg import dialogue, ws_event, gutils, icons, ifce, utils
from gwsmhg_pkg import file_tree, cmd_result, text_edit, const, diff
from gwsmhg_pkg import tlview

Row = collections.namedtuple('Row',
    ['name', 'icon', 'markup'])

_MODEL_TEMPLATE = Row(
    name=gobject.TYPE_STRING,
    icon=gobject.TYPE_STRING,
    markup=gobject.TYPE_STRING,
)

_NAME = tlview.model_col(_MODEL_TEMPLATE, 'name')
_MARKUP = tlview.model_col(_MODEL_TEMPLATE, 'markup')
_ICON = tlview.model_col(_MODEL_TEMPLATE, 'icon')

class Store(tlview.ListStore):
    def __init__(self):
        tlview.ListStore.__init__(self, _MODEL_TEMPLATE)
    def get_patch_name(self, plist_iter):
        return self.get_labelled_value(plist_iter, 'name')

def _markup_applied_patch(patch_name, guards, selected):
    markup = patch_name
    appliable = True
    if guards:
        unselected_pluses = False
        selected_pluses = False
        selected_minuses = False
        markup += " <b>:</b>"
        for guard in guards:
            if guard[1:] in selected:
                markup += " <b>%s</b>" % guard
                if guard[0] == "-":
                    selected_minuses = True
                else:
                    selected_pluses = True
            else:
                markup += " %s" % guard
                unselected_pluses = unselected_pluses or guard[0] == "+"
        if selected_minuses:
            appliable = False
        elif selected_pluses:
            appliable = True
        else:
            appliable = not unselected_pluses
    return (markup, appliable)

def _markup_unapplied_patch(patch_name, guards, selected):
    amarkup, appliable = _markup_applied_patch(patch_name, guards, selected)
    markup = '<span foreground="darkgrey" style="italic">' + amarkup + '</span>'
    return (markup, appliable)

def _patch_status_icon(status):
    if status != const.NOT_APPLIED:
        return icons.STOCK_APPLIED
    else:
        return None

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
    <toolitem name="Select Guards" action="pm_select_guards"/>
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
      <menuitem action="pm_set_patch_guards"/>
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

_VIEW_TEMPLATE = tlview.ViewTemplate(
    properties={
        'enable-grid-lines' : False,
        'reorderable' : False,
        'rules_hint' : False,
        'headers-visible' : False,
    },
    selection_mode=gtk.SELECTION_SINGLE,
    columns=[
        tlview.Column(
            title='Patch List',
            properties={'expand': False, 'resizable' : True},
            cells=[
                tlview.Cell(
                    creator=tlview.CellCreator(
                        function=gtk.CellRendererPixbuf,
                        expand=False,
                        start=True
                    ),
                    properties={},
                    renderer=None,
                    attributes = {'stock_id' : tlview.model_col(_MODEL_TEMPLATE, 'icon')}
                ),
                tlview.Cell(
                    creator=tlview.CellCreator(
                        function=gtk.CellRendererText,
                        expand=False,
                        start=True
                    ),
                    properties={'editable' : False},
                    renderer=None,
                    attributes = {'markup' : tlview.model_col(_MODEL_TEMPLATE, 'markup')}
                ),
            ],
        ),
    ]
)

class PatchListView(tlview.View, dialogue.BusyIndicatorUser, ws_event.Listener):
    def __init__(self, busy_indicator):
        self.store = Store()
        tlview.View.__init__(self, _VIEW_TEMPLATE, self.store)
        dialogue.BusyIndicatorUser.__init__(self, busy_indicator)
        ws_event.Listener.__init__(self)
        self.ui_manager = gutils.UIManager()
        self.unapplied_count = 0
        self.applied_count = 0
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
                ("pm_set_patch_guards", None, "QGuard", None,
                 "Set guards on the selected patch", self.do_set_guards),
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
                ("pm_push_merge", icons.STOCK_QPUSH_MERGE, None, None,
                 "Apply the next unapplied patch merging with equivalent saved patch", self.do_push_merge),
                ("pm_push_all_with_merge", icons.STOCK_QPUSH_MERGE_ALL, None, None,
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
                ("pm_refresh_top_patch", icons.STOCK_QREFRESH, None, None,
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
                ("pm_new", icons.STOCK_QNEW, None, None,
                 "Create a new patch", self.do_new_patch),
                ("pm_import_external_patch", icons.STOCK_IMPORT_PATCH, "QImport", None,
                 "Import an external patch", self.do_import_external_patch),
                ("pm_import_patch_series", icons.STOCK_IMPORT_PATCH, "QImport Patch Series", None,
                 "Import an external patch (mq/quilt style) series", self.do_import_external_patch_series),
                ("pm_select_guards", icons.STOCK_SELECT_GUARD, "QSelect", None,
                 "Select which guards are in force", self.do_select_guards),
            ])
        self._action_group[WS_UPDATE_CLEAN_UP_READY].add_actions(
            [
                ("pm_clean_up_after_update", gtk.STOCK_CLEAR, "Clean Up", None,
                 "Clean up left over heads after repostory and patch series update", self.do_clean_up_after_update),
            ])
        toggle_data = list(range(4))
        toggle_data[gutils.TOC_NAME] = "auto_refresh_patch_list"
        toggle_data[gutils.TOC_LABEL] = "Auto Update"
        toggle_data[gutils.TOC_TOOLTIP] = "Enable/disable automatic updating of the patch list"
        toggle_data[gutils.TOC_STOCK_ID] = gtk.STOCK_REFRESH
        self.toc = gutils.TimeOutController(toggle_data, function=self.set_contents, is_on=False)
        self._action_group[PUSH_POP_INDIFFERENT].add_action(self.toc.toggle_action)
        self.cwd_merge_id = self.ui_manager.add_ui_from_string(PM_PATCHES_UI_DESCR)
        self.get_selection().connect("changed", self._selection_changed_cb)
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
        ifce.PM.update_is_enabled()
        self.update_in_repo_sensitivity()
        self.set_contents()
        self.unshow_busy()
    def _selection_changed_cb(self, selection):
        if selection.count_selected_rows() == 0:
            for index in APPLIED, UNAPPLIED, APPLIED_INDIFFERENT, UNAPPLIED_AND_INTERDIFF:
                self._action_group[index].set_sensitive(False)
        else:
            model, model_iter = self.get_selection().get_selected()
            applied = model.get_value(model_iter, 1) != None
            self._action_group[APPLIED_INDIFFERENT].set_sensitive(True)
            self._action_group[APPLIED].set_sensitive(applied)
            self._action_group[UNAPPLIED].set_sensitive(not applied)
            interdiff_avail = utils.which("interdiff") is not None
            self._action_group[UNAPPLIED_AND_INTERDIFF].set_sensitive(interdiff_avail and not applied)
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
        model, model_iter = self.get_selection().get_selected()
        if model_iter is None:
            return None
        else:
            return model.get_value(model_iter, 0)
    def _set_ws_update_menu_sensitivity(self):
        self._action_group[WS_UPDATE_QSAVE_READY].set_sensitive(
            ifce.PM.get_ws_update_qsave_ready(unapplied_count=self.unapplied_count,
                                              applied_count=self.applied_count))
        self._action_group[WS_UPDATE_PULL_READY].set_sensitive(
            ifce.PM.get_ws_update_pull_ready(applied_count=self.applied_count))
        self._action_group[WS_UPDATE_TO_READY].set_sensitive(
            ifce.PM.get_ws_update_to_ready(applied_count=self.applied_count))
        self._action_group[WS_UPDATE_READY].set_sensitive(
            ifce.PM.get_ws_update_ready(applied_count=self.applied_count))
        self._action_group[WS_UPDATE_MERGE_READY].set_sensitive(
            ifce.PM.get_ws_update_merge_ready(unapplied_count=self.unapplied_count))
        self._action_group[WS_UPDATE_CLEAN_UP_READY].set_sensitive(
            ifce.PM.get_ws_update_clean_up_ready())
    def update_in_repo_sensitivity(self):
        if ifce.in_valid_repo:
            self._selection_changed_cb(self.get_selection())
            self._set_ws_update_menu_sensitivity()
            self._action_group[PUSH_POP_INDIFFERENT].set_sensitive(True)
            self._action_group[PUSH_POP_INDIFFERENT].get_action("pm_select_guards").set_sensitive(ifce.PM.get_enabled())
        else:
            for condition in APPLIED_CONDITIONS + PUSH_POP_CONDITIONS + WS_UPDATE_CONDITIONS:
                self._action_group[condition].set_sensitive(False)
    def set_contents(self, _action=None):
        self.show_busy()
        patch_data_list = ifce.PM.get_all_patches_data()
        selected = ifce.PM.get_selected_guards()
        self.unapplied_count = 0
        self.applied_count = 0
        self.store.clear()
        for patch_data in patch_data_list:
            icon = _patch_status_icon(patch_data.state)
            if patch_data.state is not const.NOT_APPLIED:
                markup, dummy = _markup_applied_patch(patch_data.name, patch_data.guards, selected)
                self.store.append([patch_data.name, icon, markup])
                self.applied_count += 1
            else:
                markup, appliable = _markup_unapplied_patch(patch_data.name, patch_data.guards, selected)
                self.store.append([patch_data.name, icon, markup])
                if appliable:
                    self.unapplied_count += 1
        self._action_group[POP_POSSIBLE].set_sensitive(self.applied_count > 0)
        self._action_group[POP_NOT_POSSIBLE].set_sensitive(self.applied_count == 0)
        self._action_group[PUSH_POSSIBLE].set_sensitive(self.unapplied_count > 0)
        self._action_group[PUSH_NOT_POSSIBLE].set_sensitive(self.unapplied_count == 0)
        self._set_ws_update_menu_sensitivity()
        self.get_selection().unselect_all()
        self.unshow_busy()
    def do_refresh(self, _action=None, notify=True):
        self.show_busy()
        res, sout, serr = ifce.PM.do_refresh(notify=notify)
        self.unshow_busy()
        if res != cmd_result.OK:
            if res & cmd_result.SUGGEST_RECOVER:
                if dialogue.ask_recover_or_cancel(os.linesep.join([sout, serr])) == dialogue.RESPONSE_RECOVER:
                    self.show_busy()
                    res, sout, serr = ifce.PM.do_recover_interrupted_refresh()
                    if res == cmd_result.OK:
                        res, sout, serr = ifce.PM.do_refresh(notify=notify)
                    self.unshow_busy()
            if res != cmd_result.OK: # There're may still be problems
                dialogue.report_any_problems((res, sout, serr))
                return
    def _do_pop_to(self, patch=None):
        while True:
            self.show_busy()
            res, sout, serr = ifce.PM.do_pop_to(patch=patch)
            self.unshow_busy()
            self.set_contents()
            if res != cmd_result.OK:
                if res & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                    ans = dialogue.ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res)
                    if ans == gtk.RESPONSE_CANCEL:
                        return False
                    elif ans == dialogue.RESPONSE_REFRESH:
                        self.do_refresh(notify=False)
                        continue
                    elif ans == dialogue.RESPONSE_FORCE:
                        self.show_busy()
                        res, sout, serr = ifce.PM.do_pop_to(force=True)
                        self.unshow_busy()
                if res != cmd_result.OK: # there're are still problems
                    dialogue.report_any_problems((res, sout, serr))
                    return False
            return True
    def do_pop_to(self, _action=None):
        patch = self.get_selected_patch()
        while ifce.PM.get_top_patch() != patch:
            if not self._do_pop_to(patch):
                break
    def do_pop(self, _action=None):
        self._do_pop_to()
    def do_pop_all(self, _action=None):
        self._do_pop_to("")
    def _do_push_to(self, patch=None, merge=False):
        while True:
            self.show_busy()
            res, sout, serr = ifce.PM.do_push_to(patch=patch, merge=merge)
            self.unshow_busy()
            self.set_contents()
            if res != cmd_result.OK:
                if res & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                    ans = dialogue.ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res, parent=None)
                    if ans == gtk.RESPONSE_CANCEL:
                        return False
                    if ans == dialogue.RESPONSE_REFRESH:
                        self.do_refresh(notify=False)
                        continue
                    elif ans == dialogue.RESPONSE_FORCE:
                        self.show_busy()
                        res, sout, serr = ifce.PM.do_push_to(force=True, merge=merge)
                        self.unshow_busy()
                if res != cmd_result.OK: # there're are still problems
                    dialogue.report_any_problems((res, sout, serr))
                    return False
            return True
    def do_push_to(self, _action=None):
        patch = self.get_selected_patch()
        while ifce.PM.get_top_patch() != patch:
            if not self._do_push_to(patch):
                break
    def do_push(self, _action=None):
        self._do_push_to()
    def do_push_merge(self, _action=None):
        self._do_push_to(merge=True)
    def do_push_all(self, _action=None):
        self._do_push_to("", merge=False)
    def do_push_all_with_merge(self, _action=None):
        self._do_push_to("", merge=True)
    def do_finish_to(self, _action=None):
        patch = self.get_selected_patch()
        while True:
            next_patch = ifce.PM.get_base_patch()
            if not next_patch:
                break
            while True:
                self.show_busy()
                is_ok = ifce.PM.get_description_is_finish_ready(next_patch)
                self.unshow_busy()
                if is_ok:
                    break
                msg = os.linesep.join(
                    ['"%s" has an empty description.' % next_patch,
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
                self.do_edit_description_wait(next_patch)
            self.show_busy()
            res, sout, serr = ifce.PM.do_finish_patch(next_patch)
            self.set_contents()
            self.unshow_busy()
            if res != cmd_result.OK:
                dialogue.report_any_problems((res, sout, serr))
                break
            if patch == next_patch:
                break
    def do_edit_description_wait(self, patch=None):
        if not patch:
            patch = self.get_selected_patch()
        PatchDescrEditDialog(patch, parent=None).run()
    def do_edit_description(self, _action=None):
        patch = self.get_selected_patch()
        PatchDescrEditDialog(patch, parent=None).show()
    def show_files(self, _action=None):
        patch = self.get_selected_patch()
        dialog = file_tree.PatchFilesDialog(patch=patch)
        dialog.show()
    def show_diff_acb(self, _action=None):
        patch = self.get_selected_patch()
        dialog = diff.PmDiffTextDialog(parent=dialogue.main_window, patch=patch)
        dialog.show()
    def do_rename(self, _action=None):
        patch = self.get_selected_patch()
        dialog = dialogue.ReadTextDialog("Rename Patch: %s" % patch, "New Name:", patch)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            new_name = dialog.entry.get_text()
            dialog.destroy()
            if patch == new_name:
                return
            res, sout, serr = ifce.PM.do_rename_patch(patch, new_name)
            dialogue.report_any_problems((res, sout, serr))
            self.set_contents()
        else:
            dialog.destroy()
    def do_set_guards(self, _action=None):
        patch = self.get_selected_patch()
        cguards = ' '.join(ifce.PM.get_patch_guards(patch))
        dialog = dialogue.ReadTextDialog("Set Guards: %s" % patch, "Guards:", cguards)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            guards = dialog.entry.get_text()
            dialog.destroy()
            res, sout, serr = ifce.PM.do_set_patch_guards(patch, guards)
            dialogue.report_any_problems((res, sout, serr))
            self.set_contents()
        else:
            dialog.destroy()
    def do_select_guards(self, _action=None):
        cselected_guards = ' '.join(ifce.PM.get_selected_guards())
        dialog = dialogue.ReadTextDialog("Select Guards: %s" % os.getcwd(), "Guards:", cselected_guards)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            selected_guards = dialog.entry.get_text()
            dialog.destroy()
            res, sout, serr = ifce.PM.do_select_guards(selected_guards)
            dialogue.report_any_problems((res, sout, serr))
            self.set_contents()
        else:
            dialog.destroy()
    def do_delete(self, _action=None):
        patch = self.get_selected_patch()
        res, sout, serr = ifce.PM.do_delete_patch(patch)
        dialogue.report_any_problems((res, sout, serr))
        self.set_contents()
    def do_fold(self, _action=None):
        patch = self.get_selected_patch()
        res, sout, serr = ifce.PM.do_fold_patch(patch)
        dialogue.report_any_problems((res, sout, serr))
        self.set_contents()
    def do_fold_to(self, _action=None):
        patch = self.get_selected_patch()
        while True:
            next_patch = ifce.PM.get_next_patch()
            if not next_patch:
                return
            res, sout, serr = ifce.PM.do_fold_patch(next_patch)
            if res != cmd_result.OK:
                dialogue.report_any_problems((res, sout, serr))
                return
            self.set_contents()
            if patch == next_patch:
                return
    def do_duplicate(self, _action=None):
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
        old_pfname = ifce.PM.get_patch_file_name(patch)
        res, sout, serr = ifce.PM.do_import_patch(old_pfname, duplicate_patch_name)
        self.unshow_busy()
        if res == cmd_result.ERROR_SUGGEST_FORCE:
            if dialogue.ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res) == dialogue.RESPONSE_FORCE:
                self.show_busy()
                res, sout, serr = ifce.PM.do_import_patch(old_pfname, duplicate_patch_name,
                                                          force=True)
                self.unshow_busy()
            else:
                return
        self.set_contents()
        if res != cmd_result.OK:
            dialogue.report_any_problems((res, sout, serr))
            if res & cmd_result.ERROR:
                return
        self.show_busy()
        res, sout, serr = ifce.PM.do_set_patch_description(duplicate_patch_name,
                                                           duplicate_patch_descr)
        self.unshow_busy()
        dialogue.report_any_problems((res, sout, serr))
    def do_interdiff(self, _action=None):
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
        top_patch = ifce.PM.get_top_patch()
        if top_patch:
            top_pfname = ifce.PM.get_patch_file_name(top_patch)
            old_pfname = ifce.PM.get_patch_file_name(patch)
            res, diff_text, serr = utils.run_cmd("interdiff %s %s" % (top_pfname, old_pfname))
            if res != cmd_result.OK:
                dialogue.report_any_problems((res, diff_text, serr))
                return
            temp_pfname = tempfile.mktemp()
            tfobj = open(temp_pfname, 'w')
            tfobj.write(os.linesep.join([interdiff_patch_descr, diff_text]))
            tfobj.close()
        else:
            temp_pfname = ifce.PM.get_patch_file_name(patch)
        res, sout, serr = ifce.PM.do_import_patch(temp_pfname, interdiff_patch_name)
        self.unshow_busy()
        if res == cmd_result.ERROR_SUGGEST_FORCE:
            if dialogue.ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res) == dialogue.RESPONSE_FORCE:
                self.show_busy()
                res, sout, serr = ifce.PM.do_import_patch(temp_pfname, interdiff_patch_name, force=True)
                self.unshow_busy()
        if top_patch:
            os.remove(temp_pfname)
        self.set_contents()
        if res != cmd_result.OK:
            dialogue.report_any_problems((res, sout, serr))
    def do_save_queue_state_for_update(self, _action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        self.show_busy()
        res, sout, serr = ifce.PM.do_save_queue_state_for_update()
        self.unshow_busy()
        self.set_contents()
        dialogue.report_any_problems((res, sout, serr))
    def do_pull_to_repository(self, _action=None):
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
            result = ifce.PM.do_pull_from(source=source, rev=rev)
            self._set_ws_update_menu_sensitivity()
            self.unshow_busy()
            dialogue.report_any_problems(result)
        else:
            dialog.destroy()
    def do_update_workspace(self, _action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        self.show_busy()
        result = ifce.PM.do_update_workspace()
        self._set_ws_update_menu_sensitivity()
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def do_update_workspace_to(self, _action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        dialog = change_set.ChangeSetSelectDialog()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            rev = dialog.get_change_set()
            dialog.destroy()
            if rev:
                self.show_busy()
                result = ifce.PM.do_update_workspace(rev=rev)
                self._set_ws_update_menu_sensitivity()
                self.unshow_busy()
                dialogue.report_any_problems(result)
        else:
            dialog.destroy()
    def do_clean_up_after_update(self, _action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        self.show_busy()
        result = ifce.PM.do_clean_up_after_update()
        self.unshow_busy()
        self.set_contents()
        dialogue.report_any_problems(result)
    def do_new_patch(self, _action=None):
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
            res, sout, serr = ifce.PM.do_new_patch(new_patch_name, force=force)
            self.unshow_busy()
            if res & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                ans = dialogue.ask_force_refresh_or_cancel(os.linesep.join([sout, serr]), res, parent=None)
                if ans == gtk.RESPONSE_CANCEL:
                    return
                if ans == dialogue.RESPONSE_REFRESH:
                    self.do_refresh(notify=False)
                elif ans == dialogue.RESPONSE_FORCE:
                    force = True
            else:
                dialogue.report_any_problems((res, sout, serr))
                break
        self.set_contents()
        if new_patch_descr and res != cmd_result.ERROR:
            self.show_busy()
            res, sout, serr = ifce.PM.do_set_patch_description(new_patch_name, new_patch_descr)
            self.unshow_busy()
            dialogue.report_any_problems((res, sout, serr))
    def do_import_external_patch(self, _action=None):
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
            res, sout, serr = ifce.PM.do_import_patch(patch_file_name, patch_name, force)
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
    def do_import_external_patch_series(self, _action=None):
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
        sfobj = open(series_fn, 'r')
        series = sfobj.readlines()
        sfobj.close()
        series.reverse()
        index = 0
        patch_name_re = re.compile("\s*([^\s#]+)[\s#]*.*$")
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
                res, sout, serr = ifce.PM.do_import_patch(patch_file_name, patch_name, force)
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
        toolbar.set_style(gtk.TOOLBAR_BOTH)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        hbox.pack_end(toolbar, fill=False, expand=False)
        self.pack_start(hbox, expand=False)
        self.pack_start(gutils.wrap_in_scrolled_window(self.view))
        self.show_all()
        self.set_focus_child(self.view)

class PatchDescrEditWidget(NewPatchDescrEditWidget):
    def __init__(self, get_summary, set_summary, patch=None):
        self.view = text_edit.PatchSummaryView(get_summary, set_summary, patch)
        NewPatchDescrEditWidget.__init__(self, view=self.view)
        self.view.load_summary()
    def get_save_button(self):
        return self.view.save_button

class GenericPatchDescrEditDialog(dialogue.AmodalDialog):
    def __init__(self, get_summary, set_summary, parent, patch=None):
        flags = gtk.DIALOG_DESTROY_WITH_PARENT
        dialogue.AmodalDialog.__init__(self, None, parent, flags, None)
        self.set_title('"%s" Description: %s' % (patch, utils.cwd_rel_home()))
        self.edit_descr_widget = PatchDescrEditWidget(get_summary, set_summary,
                                                      patch)
        self.vbox.pack_start(self.edit_descr_widget)
        self.action_area.pack_start(self.edit_descr_widget.get_save_button())
        self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.connect("response", self._handle_response_cb)
        self.set_focus_child(self.edit_descr_widget.view)
    def _handle_response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_CLOSE:
            if self.edit_descr_widget.view.get_buffer().get_modified():
                qtn = os.linesep.join(["Unsaved changes to summary will be lost.", "Close anyway?"])
                if dialogue.ask_yes_no(qtn):
                    self.destroy()
            else:
                self.destroy()

class PatchDescrEditDialog(GenericPatchDescrEditDialog):
    def __init__(self, patch, parent):
        GenericPatchDescrEditDialog.__init__(self,
            get_summary=ifce.PM.get_patch_description,
            set_summary=ifce.PM.do_set_patch_description,
            parent=parent, patch=patch)

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
        res, old_descr, _serr = ifce.PM.get_patch_description(patch)
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
            self.set_icon_from_file(icons.APP_ICON_FILE)
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
