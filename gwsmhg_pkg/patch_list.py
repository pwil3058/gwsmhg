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
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import collections
import gtk
import gobject
import os
import tempfile
import re
import hashlib

from gwsmhg_pkg import dialogue
from gwsmhg_pkg import ws_event
from gwsmhg_pkg import gutils
from gwsmhg_pkg import icons
from gwsmhg_pkg import ifce
from gwsmhg_pkg import utils
from gwsmhg_pkg import file_tree
from gwsmhg_pkg import cmd_result
from gwsmhg_pkg import text_edit
from gwsmhg_pkg import const
from gwsmhg_pkg import diff
from gwsmhg_pkg import tlview
from gwsmhg_pkg import path
from gwsmhg_pkg import change_set
from gwsmhg_pkg import actions
from gwsmhg_pkg import ws_actions
from gwsmhg_pkg import table
from gwsmhg_pkg import patch_view

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

AC_POP_POSSIBLE = ws_actions.AC_PMIC
AC_PUSH_POSSIBLE, AC_PUSH_POSSIBLE_MASK = actions.ActionCondns.new_flags_and_mask(1)

AC_APPLIED, AC_UNAPPLIED, AC_APPLIED_CONDNS = actions.ActionCondns.new_flags_and_mask(2)
AC_INTERDIFF, AC_INTERDIFF_MASK = actions.ActionCondns.new_flags_and_mask(1)

AC_WS_UPDATE_QSAVE_READY, \
AC_WS_UPDATE_PULL_READY, \
AC_WS_UPDATE_READY, \
AC_WS_UPDATE_TO_READY, \
AC_WS_UPDATE_MERGE_READY, \
AC_WS_UPDATE_CLEAN_UP_READY, \
AC_WS_CONDNS = actions.ActionCondns.new_flags_and_mask(6)

def get_applied_condns(seln):
    model, model_iter = seln.get_selected()
    if model_iter is None:
        return actions.MaskedCondns(actions.AC_DONT_CARE, AC_APPLIED_CONDNS)
    cond = AC_APPLIED if model.get_patch_is_applied(model_iter) else AC_UNAPPLIED
    return actions.MaskedCondns(cond, AC_APPLIED_CONDNS)

def get_interdiff_condns():
    return actions.MaskedCondns(AC_INTERDIFF if utils.which("interdiff") is not None else 0, AC_INTERDIFF_MASK)

def get_pushable_condns(unapplied_count):
    return actions.MaskedCondns(AC_PUSH_POSSIBLE if unapplied_count > 0 else 0, AC_PUSH_POSSIBLE_MASK)

def get_ws_update_condns(applied_count, unapplied_count):
    condn = actions.AC_DONT_CARE
    if ifce.PM.get_ws_update_qsave_ready(unapplied_count=unapplied_count, applied_count=applied_count):
        condn += AC_WS_UPDATE_QSAVE_READY
    if ifce.PM.get_ws_update_pull_ready(applied_count=applied_count):
        condn += AC_WS_UPDATE_PULL_READY
    if ifce.PM.get_ws_update_to_ready(applied_count=applied_count):
        condn += AC_WS_UPDATE_TO_READY
    if ifce.PM.get_ws_update_ready(applied_count=applied_count):
        condn += AC_WS_UPDATE_READY
    if ifce.PM.get_ws_update_merge_ready(unapplied_count=unapplied_count):
        condn += AC_WS_UPDATE_MERGE_READY
    if ifce.PM.get_ws_update_clean_up_ready():
        condn += AC_WS_UPDATE_CLEAN_UP_READY
    return actions.MaskedCondns(condn, AC_WS_CONDNS)

_finish_empty_msg_prompt = '\n'.join(
    [_('Do you wish to:'),
     _('\tcancel,'),
     _('\tedit the description and retry, or'),
     _('\tforce the finish operation?')
    ])

class ListView(table.TableView):
    PopUp = "/patches_popup"
    class Model(tlview.NamedListStore):
        Row = collections.namedtuple('Row',    ['name', 'icon', 'markup'])
        types = Row(
            name=gobject.TYPE_STRING,
            icon=gobject.TYPE_STRING,
            markup=gobject.TYPE_STRING,
        )
        def get_patch_name(self, plist_iter):
            return self.get_value_named(plist_iter, 'name')
        def get_patch_is_applied(self, plist_iter):
            return self.get_value_named(plist_iter, 'icon') is not None
    specification = tlview.ViewSpec(
        properties={
            'enable-grid-lines' : False,
            'reorderable' : False,
            'rules_hint' : False,
            'headers-visible' : False,
        },
        selection_mode=gtk.SELECTION_SINGLE,
        columns=[
            tlview.ColumnSpec(
                title=_('Patch List'),
                properties={'expand': False, 'resizable' : True},
                cells=[
                    tlview.CellSpec(
                        cell_renderer_spec=tlview.CellRendererSpec(
                            cell_renderer=gtk.CellRendererPixbuf,
                            expand=False,
                            start=True
                        ),
                        properties={},
                        cell_data_function_spec=None,
                        attributes = {'stock_id' : Model.col_index('icon')}
                    ),
                    tlview.CellSpec(
                        cell_renderer_spec=tlview.CellRendererSpec(
                            cell_renderer=gtk.CellRendererText,
                            expand=False,
                            start=True
                        ),
                        properties={'editable' : False},
                        cell_data_function_spec=None,
                        attributes = {'markup' : Model.col_index('markup')}
                    ),
                ],
            ),
        ]
    )
    UI_DESCR = \
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
        <toolitem action="pm_refresh_top_patch"/>
        <toolitem action="pm_push"/>
        <toolitem action="pm_pop"/>
        <separator/>
        <toolitem name="PushMerge" action="pm_push_merge"/>
        <separator/>
        <toolitem action="pm_new"/>
        <toolitem action="pm_select_guards"/>
        <toolitem action="pm_import_external_patch"/>
      </toolbar>
      <menubar name="patch_list_menubar">
        <menu name="patch_list_menu" action="menu_patch_list">
          <menuitem action="refresh_patch_list"/>
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
          <menuitem action="pm_patch_view"/>
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
    def __init__(self, busy_indicator=None, size_req=None):
        self.last_import_dir = None
        self._hash_data = None
        table.TableView.__init__(self, busy_indicator=busy_indicator, size_req=size_req)
        # This callback is needed to process applied/unapplied status
        self.get_selection().connect('changed', self._selection_changed_cb)
        self.add_notification_cb(ws_event.CHANGE_WD, self._repopulate_list_cb)
        self.add_notification_cb(ws_event.PATCH_CHANGES, self._update_list_cb)
        self.add_notification_cb(ws_event.AUTO_UPDATE, self._auto_update_list_cb)
        self.repopulate_list()
    def populate_action_groups(self):
        table.TableView.populate_action_groups(self)
        self.action_groups[AC_APPLIED].add_actions(
            [
                ("pm_pop_to_patch", icons.STOCK_POP_PATCH, _('QPop To'), None,
                 _('Pop to the selected patch'), self.do_pop_to),
                ("pm_finish_to", icons.STOCK_FINISH_PATCH, _('QFinish To'), None,
                 _('Move patches up to the selected patch into main repository'), self.do_finish_to),
            ])
        self.action_groups[actions.AC_SELN_MADE].add_actions(
            [
                ("pm_edit_patch_descr", gtk.STOCK_EDIT, _('Description'), None,
                 _('Edit the selected patch\'s description'), self.do_edit_description),
                ("pm_patch_view", icons.STOCK_DIFF, _('Details'), None,
                 _('View the selected patch\'s details'), self.do_view_selected_patch),
                ("pm_view_patch_files", gtk.STOCK_FILE, _('Files'), None,
                 _('Show files affected by the selected patch'), self.show_files),
                ("pm_view_patch_diff", icons.STOCK_DIFF, _('Diff'), None,
                 _('Show diff for the selected patch'), self.show_diff_acb),
                ("pm_rename_patch", None, _('QRename'), None,
                 _('Rename the selected patch'), self.do_rename),
                ("pm_set_patch_guards", icons.STOCK_QGUARD, None, None,
                 _('Set guards on the selected patch'), self.do_set_guards),
            ])
        self.action_groups[AC_UNAPPLIED].add_actions(
            [
                ("pm_delete_patch", gtk.STOCK_DELETE, "QDelete", None,
                 _('Delete the selected patch'), self.do_delete),
                ("pm_push_to", icons.STOCK_PUSH_PATCH, "QPush To", None,
                 _('Push to the selected patch'), self.do_push_to),
                ("pm_fold", icons.STOCK_FOLD_PATCH, "QFold", None,
                 _('Fold the selected patch into the top patch'), self.do_fold),
                ("pm_fold_to", icons.STOCK_FOLD_PATCH, "QFold To", None,
                 _('Fold patches up to the selected patch into the top patch'), self.do_fold_to),
                ("pm_duplicate", gtk.STOCK_COPY, _('Duplicate'), None,
                 _('Duplicate the selected patch behind the top patch'), self.do_duplicate),
            ])
        self.action_groups[AC_UNAPPLIED + AC_INTERDIFF].add_actions(
            [
                ("pm_interdiff", gtk.STOCK_PASTE, "Interdiff", None,
                 _('Place the "interdiff" of the selected patch and the top patch behind the top patch'), self.do_interdiff),
            ])
        self.action_groups[AC_PUSH_POSSIBLE].add_actions(
            [
                ("pm_push", icons.STOCK_PUSH_PATCH, "QPush", None,
                 _('Apply the next unapplied patch'), self.do_push),
                ("pm_push_all", icons.STOCK_PUSH_PATCH, "QPush All", None,
                 _('Apply all remaining unapplied patches'), self.do_push_all),
            ])
        self.action_groups[AC_POP_POSSIBLE].add_actions(
            [
                ("pm_pop", icons.STOCK_POP_PATCH, "QPop", None,
                 _('Pop the top applied patch'), self.do_pop),
                ("pm_pop_all", icons.STOCK_POP_PATCH, "QPop All", None,
                 _('Pop all remaining applied patches'), self.do_pop_all),
                ("pm_refresh_top_patch", icons.STOCK_QREFRESH, None, None,
                 _('Refresh the top patch'), self.do_refresh),
            ])
        self.action_groups[ws_actions.AC_IN_PGND].add_actions(
            [
                ("menu_patches", None, _('_Patches')),
                ("menu_patches_ws", None, _('_Workspace Update')),
                ("refresh_patch_list", gtk.STOCK_REFRESH, _('Update Patch List'), None,
                 _('Refresh/update the patch list display'), self._update_list_cb),
                ("pm_import_patch_series", icons.STOCK_IMPORT_PATCH, _('QImport Patch Series'), None,
                 _('Import an external patch (mq/quilt style) series'), self.do_import_external_patch_series),
                ("pm_select_guards", icons.STOCK_QSELECT, None, None,
                 _('Select which guards are in force'), self.do_select_guards),
            ])
        self.action_groups[ws_actions.AC_IN_REPO].add_actions(
            [
                ("menu_patch_list", None, _('Patch _List')),
                ("pm_new", icons.STOCK_QNEW, None, None,
                 _('Create a new patch'), self.do_new_patch),
                ("pm_import_external_patch", icons.STOCK_IMPORT_PATCH, "QImport", None,
                 _('Import an external patch'), self.do_import_external_patch),
            ])
        self.action_groups[AC_WS_UPDATE_MERGE_READY].add_actions(
            [
                ("pm_push_merge", icons.STOCK_QPUSH_MERGE, None, None,
                 _('Apply the next unapplied patch merging with equivalent saved patch'), self.do_push_merge),
                ("pm_push_all_with_merge", icons.STOCK_QPUSH_MERGE_ALL, None, None,
                 _('Apply all remaining unapplied patches with "merge" option enabled'), self.do_push_all_with_merge),
            ])
        self.action_groups[AC_WS_UPDATE_QSAVE_READY].add_actions(
            [
                ("save_queue_state_for_update", None, _('QSave For Update'), None,
                 _('Save the queue state prepatory to update'), self.do_save_queue_state_for_update),
            ])
        self.action_groups[AC_WS_UPDATE_READY].add_actions(
            [
                ("pm_update_workspace", None, _('Update Workspace'), None,
                 _('Update the workspace to the repository tip'), self.do_update_workspace),
            ])
        self.action_groups[AC_WS_UPDATE_TO_READY].add_actions(
            [
                ("pm_update_workspace_to", None, _('Update Workspace To'), None,
                 _('Update the workspace to a specified revision'), self.do_update_workspace_to),
            ])
        self.action_groups[AC_WS_UPDATE_PULL_READY].add_actions(
            [
                ("pm_pull_to_repository", None, _('Pull To Workspace'), None,
                 _('Pull to the repository from the default remote path'), self.do_pull_to_repository),
            ])
        self.action_groups[AC_WS_UPDATE_CLEAN_UP_READY].add_actions(
            [
                ("pm_clean_up_after_update", gtk.STOCK_CLEAR, _('Clean Up'), None,
                 _('Clean up left over heads after repostory and patch series update'), self.do_clean_up_after_update),
            ])
    def _selection_changed_cb(self, selection):
        # This callback is needed to process applied/unapplied status
        # self.action_groups' callback handles the other selection conditions
        self.action_groups.update_condns(get_applied_condns(selection))
    def get_selected_patch(self):
        store, store_iter = self.seln.get_selected()
        return None if store_iter is None else store.get_patch_name(store_iter)
    def _update_list_cb(self, _arg=None):
        self.refresh_contents()
    def _auto_update_list_cb(self, _arg=None):
        if not self._hash_data or (self._hash_data.digest() != ifce.PM.get_all_patches_hash_digest()):
            self.refresh_contents()
    def _fetch_contents(self):
        self._hash_data = hashlib.sha1()
        patch_data_list = ifce.PM.get_all_patches_data(self._hash_data)
        selected = ifce.PM.get_selected_guards(self._hash_data)
        unapplied_count = 0
        applied_count = 0
        contents = []
        for patch_data in patch_data_list:
            icon = _patch_status_icon(patch_data.state)
            if patch_data.state is not const.NOT_APPLIED:
                markup, dummy = _markup_applied_patch(patch_data.name, patch_data.guards, selected)
                contents.append([patch_data.name, icon, markup])
                applied_count += 1
            else:
                markup, appliable = _markup_unapplied_patch(patch_data.name, patch_data.guards, selected)
                contents.append([patch_data.name, icon, markup])
                if appliable:
                    unapplied_count += 1
        condns = get_pushable_condns(unapplied_count)
        condns |= get_ws_update_condns(applied_count, unapplied_count)
        self.action_groups.update_condns(condns)
        return contents
    def repopulate_list(self):
        self.set_contents()
        condns = get_applied_condns(self.get_selection())
        condns |= ws_actions.get_in_pgnd_condns()
        condns |= get_interdiff_condns()
        self.action_groups.update_condns(condns)
    def _repopulate_list_cb(self, _arg=None):
        self.show_busy()
        ifce.PM.update_is_enabled()
        self.repopulate_list()
        self.unshow_busy()
    def do_refresh(self, _action=None, notify=True):
        self.show_busy()
        result = ifce.PM.do_refresh(notify=notify)
        self.unshow_busy()
        if result.ecode != cmd_result.OK:
            if result.ecode & cmd_result.SUGGEST_RECOVER:
                if dialogue.ask_recover_or_cancel(result) == dialogue.Response.RECOVER:
                    self.show_busy()
                    result = ifce.PM.do_recover_interrupted_refresh()
                    if result.ecode == cmd_result.OK:
                        result = ifce.PM.do_refresh(notify=notify)
                    self.unshow_busy()
            if result.ecode != cmd_result.OK: # There're may still be problems
                dialogue.report_any_problems(result)
                return
    def _do_pop_to(self, patch=None):
        while True:
            self.show_busy()
            result = ifce.PM.do_pop_to(patch=patch)
            self.unshow_busy()
            if result.ecode != cmd_result.OK:
                if result.ecode & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                    ans = dialogue.ask_force_refresh_or_cancel(result)
                    if ans == gtk.RESPONSE_CANCEL:
                        return False
                    elif ans == dialogue.Response.REFRESH:
                        self.do_refresh(notify=False)
                        continue
                    elif ans == dialogue.Response.FORCE:
                        self.show_busy()
                        result = ifce.PM.do_pop_to(force=True)
                        self.unshow_busy()
                if result.ecode != cmd_result.OK: # there're are still problems
                    dialogue.report_any_problems(result)
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
            result = ifce.PM.do_push_to(patch=patch, merge=merge)
            self.unshow_busy()
            if result.ecode != cmd_result.OK:
                if result.ecode & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                    ans = dialogue.ask_force_refresh_or_cancel(result, parent=None)
                    if ans == gtk.RESPONSE_CANCEL:
                        return False
                    if ans == dialogue.Response.REFRESH:
                        self.do_refresh(notify=False)
                        continue
                    elif ans == dialogue.Response.FORCE:
                        self.show_busy()
                        result = ifce.PM.do_push_to(force=True, merge=merge)
                        self.unshow_busy()
                if result.ecode != cmd_result.OK: # there're are still problems
                    dialogue.report_any_problems(result)
                    return False
            return True
    def do_push_to(self, _action=None):
        patch = self.get_selected_patch()
        while ifce.PM.get_top_patch() != patch:
            if not self._do_push_to(patch=patch):
                break
    def do_push(self, _action=None):
        self._do_push_to()
    def do_push_merge(self, _action=None):
        self._do_push_to(merge=True)
    def do_push_all(self, _action=None):
        self._do_push_to(patch="", merge=False)
    def do_push_all_with_merge(self, _action=None):
        self._do_push_to(patch="", merge=True)
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
                dummyres = cmd_result.Result(ecode=cmd_result.SUGGEST_ALL,
                    stdout = _('"%s" has an empty description.') % next_patch,
                    stderr = '')
                ans = dialogue.ask_edit_force_or_cancel(dummyres, clarification=_finish_empty_msg_prompt, parent=None)
                if ans == gtk.RESPONSE_CANCEL:
                    return
                elif ans == dialogue.Response.FORCE:
                    break
                self.do_edit_description_wait(next_patch)
            self.show_busy()
            result = ifce.PM.do_finish_patch(next_patch)
            self.unshow_busy()
            if result.ecode != cmd_result.OK:
                dialogue.report_any_problems(result)
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
    def do_view_selected_patch(self, action=None):
        patchname = self.get_selected_patch()
        patch_view.Dialogue(patchname).show()
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
        dialog = dialogue.ReadTextDialog(_('Rename Patch: %s') % patch, _('New Name:'), patch)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            new_name = dialog.entry.get_text()
            dialog.destroy()
            if patch == new_name:
                return
            self.show_busy()
            result = ifce.PM.do_rename_patch(patch, new_name)
            self.unshow_busy()
            dialogue.report_any_problems(result)
        else:
            dialog.destroy()
    def do_set_guards(self, _action=None):
        patch = self.get_selected_patch()
        cguards = ' '.join(ifce.PM.get_patch_guards(patch))
        dialog = dialogue.ReadTextDialog(_('Set Guards: %s') % patch, _('Guards:'), cguards)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            guards = dialog.entry.get_text()
            dialog.destroy()
            self.show_busy()
            result = ifce.PM.do_set_patch_guards(patch, guards)
            self.unshow_busy()
            dialogue.report_any_problems(result)
        else:
            dialog.destroy()
    def do_select_guards(self, _action=None):
        cselected_guards = ' '.join(ifce.PM.get_selected_guards())
        dialog = dialogue.ReadTextDialog(_('Select Guards: %s') % os.getcwd(), _('Guards:'), cselected_guards)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            selected_guards = dialog.entry.get_text()
            dialog.destroy()
            self.show_busy()
            result = ifce.PM.do_select_guards(selected_guards)
            self.unshow_busy()
            dialogue.report_any_problems(result)
        else:
            dialog.destroy()
    def do_delete(self, _action=None):
        patch = self.get_selected_patch()
        if dialogue.ask_ok_cancel(_('Confirm delete "%s" patch?') % patch):
            self.show_busy()
            result = ifce.PM.do_delete_patch(patch)
            self.unshow_busy()
            dialogue.report_any_problems(result)
    def do_fold(self, _action=None):
        patch = self.get_selected_patch()
        self.show_busy()
        result = ifce.PM.do_fold_patch(patch)
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def do_fold_to(self, _action=None):
        patch = self.get_selected_patch()
        while True:
            next_patch = ifce.PM.get_next_patch()
            if not next_patch:
                return
            self.show_busy()
            result = ifce.PM.do_fold_patch(next_patch)
            self.unshow_busy()
            if result.ecode != cmd_result.OK:
                dialogue.report_any_problems(result)
                return
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
        result = ifce.PM.do_import_patch(old_pfname, duplicate_patch_name)
        self.unshow_busy()
        if result.ecode == cmd_result.ERROR_SUGGEST_FORCE:
            if dialogue.ask_force_refresh_or_cancel(result) == dialogue.Response.FORCE:
                self.show_busy()
                result = ifce.PM.do_import_patch(old_pfname, duplicate_patch_name, force=True)
                self.unshow_busy()
            else:
                return
        if result.ecode != cmd_result.OK:
            dialogue.report_any_problems(result)
            if result.ecode & cmd_result.ERROR:
                return
        self.show_busy()
        result = ifce.PM.do_set_patch_description(duplicate_patch_name, duplicate_patch_descr)
        self.unshow_busy()
        dialogue.report_any_problems(result)
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
            result = utils.run_cmd("interdiff %s %s" % (top_pfname, old_pfname))
            if result.ecode != cmd_result.OK:
                dialogue.report_any_problems(result)
                return
            temp_pfname = tempfile.mktemp()
            tfobj = open(temp_pfname, 'w')
            tfobj.write('\n'.join([interdiff_patch_descr, result.stdout]))
            tfobj.close()
        else:
            temp_pfname = ifce.PM.get_patch_file_name(patch)
        result = ifce.PM.do_import_patch(temp_pfname, interdiff_patch_name)
        self.unshow_busy()
        if result.ecode == cmd_result.ERROR_SUGGEST_FORCE:
            if dialogue.ask_force_refresh_or_cancel(result) == dialogue.Response.FORCE:
                self.show_busy()
                result = ifce.PM.do_import_patch(temp_pfname, interdiff_patch_name, force=True)
                self.unshow_busy()
        if top_patch:
            os.remove(temp_pfname)
        if result.ecode != cmd_result.OK:
            dialogue.report_any_problems(result)
    def do_save_queue_state_for_update(self, _action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        self.show_busy()
        result = ifce.PM.do_save_queue_state_for_update()
        self.unshow_busy()
        dialogue.report_any_problems(result)
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
            self._condn_change_update_cb()
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
        self._condn_change_update_cb()
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
                self._condn_change_update_cb()
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
            result = ifce.PM.do_new_patch(new_patch_name, force=force)
            self.unshow_busy()
            if result.ecode & cmd_result.SUGGEST_FORCE_OR_REFRESH:
                ans = dialogue.ask_force_refresh_or_cancel(result, parent=None)
                if ans == gtk.RESPONSE_CANCEL:
                    return
                if ans == dialogue.Response.REFRESH:
                    self.do_refresh(notify=False)
                elif ans == dialogue.Response.FORCE:
                    force = True
            else:
                dialogue.report_any_problems(result)
                break
        if new_patch_descr and result.ecode != cmd_result.ERROR:
            self.show_busy()
            result = ifce.PM.do_set_patch_description(new_patch_name, new_patch_descr)
            self.unshow_busy()
            dialogue.report_any_problems(result)
    def do_import_external_patch(self, _action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        patch_file_name = dialogue.ask_file_name(_('Select patch file to be imported'))
        if not patch_file_name:
            return
        force = False
        patch_name = None
        while True:
            self.show_busy()
            result = ifce.PM.do_import_patch(patch_file_name, patch_name, force)
            self.unshow_busy()
            if result.ecode & cmd_result.SUGGEST_FORCE_OR_RENAME:
                ans = dialogue.ask_rename_force_or_cancel(result, clarification=_('Force import of patch, rename patch or cancel import?'))
                if ans == gtk.RESPONSE_CANCEL:
                    return
                elif ans == dialogue.Response.FORCE:
                    force = True
                    continue
                elif ans == dialogue.Response.RENAME:
                    if not patch_name:
                        patch_name = os.path.basename(patch_file_name)
                    patch_name = dialogue.get_modified_string(_('Rename Patch'), _('New Name :'), patch_name)
                    continue
            dialogue.report_any_problems(result)
            break
    def do_import_external_patch_series(self, _action=None):
        if not ifce.PM.get_enabled():
            dialogue.report_any_problems(ifce.PM.not_enabled_response)
            return
        patch_series_dir = dialogue.ask_dir_name(_('Select patch series to be imported'))
        if not patch_series_dir:
            return
        series_fn = os.sep.join([patch_series_dir, "series"])
        if (not os.path.exists(series_fn) and os.path.isfile(series_fn)):
            dialogue.report_any_problems(cmd_result.Result(cmd_result.ERROR, "", _('Series file not found.')))
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
                result = ifce.PM.do_import_patch(patch_file_name, patch_name, force)
                self.unshow_busy()
                if result.ecode & cmd_result.SUGGEST_FORCE_OR_RENAME:
                    ans = dialogue.ask_rename_force_or_skip(result, clarification=_('Force import of patch, rename patch or skip patch?'))
                    if ans == dialogue.Response.SKIP_ALL:
                        index = len(series)
                        break
                    elif ans == dialogue.Response.SKIP:
                        break
                    elif ans == dialogue.Response.FORCE:
                        force = True
                        continue
                    elif ans == dialogue.Response.RENAME:
                        if not patch_name:
                            patch_name = base_name
                        patch_name = dialogue.get_modified_string(_('Rename Patch'), _('New Name :'), patch_name)
                        continue
                dialogue.report_any_problems(result)
                break
            index += 1

class List(table.TableWidget):
    View = ListView
    def __init__(self, scroll_bar=True, busy_indicator=None, size_req=None):
        table.TableWidget.__init__(self, scroll_bar=scroll_bar, busy_indicator=busy_indicator, size_req=size_req)
        self.header.lhs.pack_start(self.ui_manager.get_widget('/patch_list_menubar'), expand=True, fill=True)

def do_export_named_patch(parent, patchname, suggestion=None, busy_indicator=None):
    if not suggestion:
        suggestion = utils.convert_patchname_to_filename(patchname)
    if busy_indicator is None:
        busy_indicator = dialogue.main_window
    PROMPT = _('Export as ...')
    export_filename = dialogue.ask_file_name(PROMPT, suggestion=suggestion, existing=False)
    if export_filename is None:
        return
    force = False
    overwrite = False
    refresh_tried = False
    while True:
        busy_indicator.show_busy()
        result = ifce.PM.do_export_patch_as(patchname, export_filename, force=force, overwrite=overwrite)
        busy_indicator.unshow_busy()
        if refresh_tried:
            result = cmd_result.turn_off_flags(result, cmd_result.SUGGEST_REFRESH)
        if result.ecode & cmd_result.SUGGEST_FORCE_OR_REFRESH != 0:
            resp = dialogue.ask_force_refresh_absorb_or_cancel(result, clarification=None)
            if resp == gtk.RESPONSE_CANCEL:
                return
            elif resp == dialogue.Response.FORCE:
                force = True
            elif resp == dialogue.Response.REFRESH:
                refresh_tried = True
                dialogue.show_busy()
                result = ifce.PM.do_refresh_patch()
                dialogue.unshow_busy()
                dialogue.report_any_problems(result)
            continue
        elif result.ecode & cmd_result.SUGGEST_RENAME != 0:
            resp = dialogue.ask_rename_overwrite_or_cancel(result, clarification=None)
            if resp == gtk.RESPONSE_CANCEL:
                return
            elif resp == dialogue.Response.OVERWRITE:
                overwrite = True
            elif resp == dialogue.Response.RENAME:
                export_filename = dialogue.ask_file_name(PROMPT, suggestion=export_filename, existing=False)
                if export_filename is None:
                    return
            continue
        dialogue.report_any_problems(result)
        break

class NewPatchDescrEditWidget(text_edit.DbMessageWidget):
    UI_DESCR = \
        '''
        <ui>
          <menubar name="patch_summary_menubar">
            <menu name="patch_summary_menu" action="menu_summary">
              <separator/>
              <menuitem action="text_edit_insert_from"/>
            </menu>
          </menubar>
          <toolbar name="patch_summary_toolbar">
            <toolitem action="text_edit_ack"/>
            <toolitem action="text_edit_sign_off"/>
            <toolitem action="text_edit_author"/>
          </toolbar>
        </ui>
        '''
    def __init__(self, save_file_name=None, auto_save=False):
        text_edit.DbMessageWidget.__init__(self, save_file_name=save_file_name, auto_save=auto_save)
        menubar = self.ui_manager.get_widget("/patch_summary_menubar")
        self.top_hbox.pack_start(menubar, fill=True, expand=False)
        toolbar = self.ui_manager.get_widget("/patch_summary_toolbar")
        toolbar.set_style(gtk.TOOLBAR_BOTH)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.top_hbox.pack_end(toolbar, fill=False, expand=False)
        self.show_all()
        self.set_focus_child(self.view)
    def populate_action_groups(self):
        text_edit.DbMessageWidget.populate_action_groups(self)
        self.action_groups[actions.AC_DONT_CARE].add_action(gtk.Action("menu_summary", _("Description"), _(""), None))

class PatchDescrEditWidget(NewPatchDescrEditWidget):
    def __init__(self, patch):
        NewPatchDescrEditWidget.__init__(self, save_file_name=None, auto_save=False)
        self._patch = patch
        self.load_text_fm_db()
    def get_text_fm_db(self):
        return ifce.PM.get_patch_description(self._patch)
    def set_text_in_db(self, text):
        return ifce.PM.do_set_patch_description(self._patch, text)

class PatchDescrEditDialog(dialogue.AmodalDialog):
    def __init__(self, patch, parent=None):
        flags = gtk.DIALOG_DESTROY_WITH_PARENT
        dialogue.AmodalDialog.__init__(self, None, parent, flags, None)
        self.set_title(_('"%s" Description: %s') % (patch, utils.cwd_rel_home()))
        self.edit_descr_widget = PatchDescrEditWidget(patch)
        self.vbox.pack_start(self.edit_descr_widget)
        self.action_area.pack_start(self.edit_descr_widget.reload_button)
        self.action_area.pack_start(self.edit_descr_widget.save_button)
        self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.connect('response', self._handle_response_cb)
        self.set_focus_child(self.edit_descr_widget.view)
    def _handle_response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_CLOSE:
            if self.edit_descr_widget.view.get_buffer().get_modified():
                qtn = '\n'.join([_('Unsaved changes to summary will be lost.'), _('Close anyway?')])
                if dialogue.ask_yes_no(qtn):
                    self.destroy()
            else:
                self.destroy()

class DuplicatePatchDialog(dialogue.Dialog):
    def __init__(self, patch, parent, verb=_('Duplicate')):
        flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
        title = '%s "%s": %s' % (verb, patch, utils.path_rel_home(os.getcwd()))
        dialogue.Dialog.__init__(self, title, parent, flags,
                                 (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                  gtk.STOCK_OK, gtk.RESPONSE_OK))
        hbox = gtk.HBox()
        vbox = gtk.VBox()
        vbox.pack_start(gtk.Label(_('%s Patch:') % verb))
        vbox.pack_start(gtk.Label(_(' As Patch Named:')))
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
        try:
            self.edit_descr_widget.view.get_buffer().set_text(ifce.PM.get_patch_description(patch))
        except cmd_result.Failure:
            pass
        self.vbox.pack_start(self.edit_descr_widget)
        self.set_focus_child(self.new_name_entry)
    def get_duplicate_patch_name(self):
        return self.new_name_entry.get_text()
    def get_duplicate_patch_descr(self):
        return self.edit_descr_widget.view.get_msg()

class NewPatchDialog(dialogue.Dialog):
    def __init__(self, parent, objname=_('Patch')):
        flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
        title = 'New %s: %s -- gwsmhg' % (objname, utils.path_rel_home(os.getcwd()))
        dialogue.Dialog.__init__(self, title, parent, flags,
                                 (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                  gtk.STOCK_OK, gtk.RESPONSE_OK))
        if not parent:
            self.set_icon_from_file(icons.APP_ICON_FILE)
        self.hbox = gtk.HBox()
        self.hbox.pack_start(gtk.Label(_('New %s Name:') % objname), fill=False, expand=False)
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
        return self.edit_descr_widget.get_contents()
