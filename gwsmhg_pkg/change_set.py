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

import gtk, gobject, os
from gwsmhg_pkg import cmd_result, gutils, utils, icons, file_tree, diff
from gwsmhg_pkg import text_edit, tortoise, ws_event

CS_TABLE_BASIC_UI_DESCR = \
'''
<ui>
  <popup name="table_popup">
    <placeholder name="top">
      <menuitem action="cs_summary"/>
    </placeholder>
    <separator/>
    <placeholder name="middle">
      <menuitem action="cs_update_ws_to"/>
      <menuitem action="cs_merge_ws_with"/>
      <menuitem action="cs_backout"/>
    </placeholder>
    <separator/>
    <placeholder name="bottom"/>
  </popup>
</ui>
'''

UNIQUE_SELECTION = "unique_selection"
UNIQUE_SELECTION_NOT_PMIC = "unique_selection_not_pmic"

class PrecisType:
    def __init__(self, descr, get_data):
        self.descr = descr
        self.get_data = get_data

class PrecisTableView(gutils.MapManagedTableView, cmd_result.ProblemReporter):
    def __init__(self, ifce, ptype, sel_mode=gtk.SELECTION_SINGLE, busy_indicator=None):
        self._ifce = ifce
        self._ptype = ptype
        if not busy_indicator:
            busy_indicator = self._ifce.log.get_busy_indicator()
        cmd_result.ProblemReporter.__init__(self)
        gutils.MapManagedTableView.__init__(self, descr=ptype.descr, sel_mode=sel_mode,
            busy_indicator=busy_indicator)
        self._ncb = ws_event.add_notification_cb(ws_event.REPO_MOD, self.refresh_contents_if_mapped)
        self.connect("destroy", self._destroy_cb)
        for condition in [UNIQUE_SELECTION, UNIQUE_SELECTION_NOT_PMIC]:
            self._action_group[condition] = gtk.ActionGroup(condition)
            self._ui_manager.insert_action_group(self._action_group[condition], -1)
        self._action_group[UNIQUE_SELECTION].add_actions(
            [
                ("cs_summary", gtk.STOCK_INFO, "Summary", None,
                 "View a summary of the selected change set", self._view_cs_summary_acb),
            ])
        self._action_group[UNIQUE_SELECTION_NOT_PMIC].add_actions(
            [
                ("cs_update_ws_to", gtk.STOCK_JUMP_TO, "Update To", None,
                 "Update the work space to the selected change set",
                 self._update_ws_to_cs_acb),
                ("cs_merge_ws_with", icons.STOCK_MERGE, "Merge With", None,
                 "Merge the work space with the selected change set",
                 self._merge_ws_with_cs_acb),
                ("cs_backout", icons.STOCK_BACKOUT, "Backout", None,
                 "Bactrack the selected change set",
                 self._backout_cs_acb),
            ])
        self.cwd_merge_id.append(self._ui_manager.add_ui_from_string(CS_TABLE_BASIC_UI_DESCR))
        self.show_all()
    def _destroy_cb(self, widget):
        ws_event.del_notification_cb(self._ncb)
    def _set_action_sensitivities(self):
        sel = self.get_selection().count_selected_rows() == 1
        self._action_group[UNIQUE_SELECTION].set_sensitive(sel)
        self._action_group[UNIQUE_SELECTION_NOT_PMIC].set_sensitive(sel and not self._ifce.PM.get_in_progress())
    def _refresh_contents(self):
        res, data, serr = self._ptype.get_data()
        if res == cmd_result.OK and data:
            self.set_contents(data)
        else:
            self.set_contents([])
        gutils.MapManagedTableView._refresh_contents(self)
    def get_selected_change_set(self):
        data = self.get_selected_data([0])
        if len(data):
            return str(data[0][0])
        else:
            return ""
    def _view_cs_summary_acb(self, action):
        rev = self.get_selected_change_set()
        self._show_busy()
        dialog = ChangeSetSummaryDialog(self._ifce, rev)
        self._unshow_busy()
        dialog.show()
    def _update_ws_to_cs_acb(self, action):
        rev = str(self.get_selected_change_set())
        self._show_busy()
        result = self._ifce.SCM.do_update_workspace(rev=rev)
        self._unshow_busy()
        if result[0] & cmd_result.SUGGEST_MERGE_OR_DISCARD:
            question = os.linesep.join(result[1:])
            ans = gutils.ask_merge_discard_or_cancel(question, result[0])
            if ans == gutils.DISCARD:
                self._show_busy()
                result = self._ifce.SCM.do_update_workspace(rev=rev, discard=True)
                self._unshow_busy()
                self._report_any_problems(result)
            elif ans == gutils.MERGE:
                self._show_busy()
                result = self._ifce.SCM.do_merge_workspace(rev=rev, force=False)
                self._unshow_busy()
                if result[0] & cmd_result.SUGGEST_FORCE:
                    question = os.linesep.join(result[1:])
                    ans = gutils.ask_force_or_cancel(question)
                    if ans == gutils.FORCE:
                        self._show_busy()
                        result = self._ifce.SCM.do_merge_workspace(rev=rev, force=True)
                        self._unshow_busy()
                        self._report_any_problems(result)
                else:
                    self._report_any_problems(result)
        else:
            self._report_any_problems(result)
    def _merge_ws_with_cs_acb(self, action):
        rev = str(self.get_selected_change_set())
        self._show_busy()
        result = self._ifce.SCM.do_merge_workspace(rev=rev)
        self._unshow_busy()
        if result[0] & cmd_result.SUGGEST_FORCE:
            question = os.linesep.join(result[1:])
            ans = gutils.ask_force_or_cancel(question)
            if ans == gutils.FORCE:
                self._show_busy()
                result = self._ifce.SCM.do_merge_workspace(rev=rev, force=True)
                self._unshow_busy()
                self._report_any_problems(result)
        else:
            self._report_any_problems(result)
    def _backout_cs_acb(self, action):
        rev = str(self.get_selected_change_set())
        self._show_busy()
        BackoutDialog(ifce=self._ifce, rev=rev)
        self._unshow_busy()

class AUPrecisTableView(PrecisTableView):
    def __init__(self, ifce, ptype, age_col, sel_mode=gtk.SELECTION_SINGLE,
        busy_indicator=None,
        auto_refresh_on=True, auto_refresh_interval=3600000):
        self._age_col = age_col
        self.rtoc = gutils.RefreshController(is_on=auto_refresh_on, interval=auto_refresh_interval)
        self._normal_interval = auto_refresh_interval
        self.rtoc.set_function(self._refresh_contents)
        PrecisTableView.__init__(self, ifce, ptype, sel_mode=sel_mode, busy_indicator=busy_indicator)
    def _refresh_contents(self):
        res, parents, serr = self._ptype.get_data()
        if res == cmd_result.OK and parents:
            desired_interval = self._normal_interval
            self.set_contents(parents)
            # if any parent's age is expressed in seconds then update every second
            # they're in time order so only need to look at first one
            if parents[0][self._age_col].find("sec") != -1:
                desired_interval = 1000
            elif parents[0][self._age_col].find("min") != -1:
                desired_interval = 60000
            elif parents[0][self._age_col].find("hour") != -1:
                    desired_interval = 3600000
            if desired_interval is not self.rtoc.get_interval():
                self.rtoc.set_interval(desired_interval)
        else:
            self.set_contents([])
        gutils.MapManagedTableView._refresh_contents(self)
    def map_action(self):
        PrecisTableView.map_action(self)
        self.rtoc.restart_cycle()
    def unmap_action(self):
        self.rtoc.stop_cycle()
        PrecisTableView.unmap_action(self)
    def refresh_contents(self):
        self.rtoc.stop_cycle()
        self._refresh_contents()
        self.rtoc.restart_cycle()

class SelectView(gutils.TableView):
    def __init__(self, ifce, ptype, size=(640, 240), sel_mode=gtk.SELECTION_SINGLE):
        self._ifce = ifce
        self._ptype = ptype
        gutils.TableView.__init__(self, ptype.descr, sel_mode=sel_mode)
        self.set_size_request(size[0], size[1])
        self._set_contents()
        self.show_all()
    def _set_contents(self):
        res, data, serr = self._ptype.get_data()
        if res == cmd_result.OK and data:
            self.set_contents(data)
        else:
            self.set_contents([])
    def get_selected_change_set(self):
        data = self.get_selected_data([0])
        if len(data):
            return str(data[0][0])
        else:
            return ""

class SelectDialog(gtk.Dialog):
    def __init__(self, ifce, ptype, title, size=(640, 240), parent=None):
        gtk.Dialog.__init__(self, title="gwsmg: Select %s" % title, parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        self._view = SelectView(ifce=ifce, ptype=ptype, size=size)
        self.vbox.pack_start(gutils.wrap_in_scrolled_window(self._view))
        self.show_all()
        self._view.get_selection().unselect_all()
    def get_change_set(self):
        return self._view.get_selected_change_set()

LOG_TABLE_PRECIS_DESCR = \
[
    ["Rev", gobject.TYPE_INT, False, []],
    ["Age", gobject.TYPE_STRING, False, []],
    ["Tags", gobject.TYPE_STRING, False, []],
    ["Branches", gobject.TYPE_STRING, False, []],
    ["Author", gobject.TYPE_STRING, False, []],
    ["Description", gobject.TYPE_STRING, True, []],
]

LOG_TABLE_PRECIS_AGE = gutils.find_label_index(LOG_TABLE_PRECIS_DESCR, "Age")

class ParentsTableView(AUPrecisTableView):
    def __init__(self, ifce, rev=None, sel_mode=gtk.SELECTION_SINGLE,
        busy_indicator=None,
        auto_refresh_on=True, auto_refresh_interval=3600000):
        self._rev = rev
        ptype = PrecisType(LOG_TABLE_PRECIS_DESCR, self.get_parents_data)
        AUPrecisTableView.__init__(self, ifce, ptype, sel_mode=sel_mode,
                                   age_col = LOG_TABLE_PRECIS_AGE,
                                   auto_refresh_on=auto_refresh_on,
                                   auto_refresh_interval=auto_refresh_interval,
                                   busy_indicator=busy_indicator)
        ws_event.del_notification_cb(self._ncb)
        self._ncb = ws_event.add_notification_cb(ws_event.REPO_MOD|ws_event.CHECKOUT, self.refresh_contents_if_mapped)
        self._action_group[UNIQUE_SELECTION_NOT_PMIC].get_action("cs_update_ws_to").set_visible(False)
        self._action_group[UNIQUE_SELECTION_NOT_PMIC].get_action("cs_merge_ws_with").set_visible(False)
        self._action_group[gutils.ALWAYS_ON].get_action("table_refresh_contents").set_visible(False)
    def get_parents_data(self):
        return self._ifce.SCM.get_parents_data(self._rev)

class ChangeSetTableView(PrecisTableView):
    def __init__(self, ifce, ptype, sel_mode=gtk.SELECTION_SINGLE, busy_indicator=None):
        PrecisTableView.__init__(self, ifce=ifce, ptype=ptype, sel_mode=sel_mode, busy_indicator=busy_indicator)

class HeadsTableView(ChangeSetTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        ptype = PrecisType(LOG_TABLE_PRECIS_DESCR, ifce.SCM.get_heads_data)
        ChangeSetTableView.__init__(self, ifce, ptype, sel_mode=sel_mode)

TAG_MSG_UI_DESCR = \
'''
<ui>
  <toolbar name="tag_message_toolbar">
    <toolitem action="summary_ack"/>
    <toolitem action="summary_sign_off"/>
    <toolitem action="summary_author"/>
  </toolbar>
</ui>
'''

class TagMessageWidget(gtk.VBox):
    def __init__(self, ifce, label="Message (optional)"):
        gtk.VBox.__init__(self)
        self.view = text_edit.SummaryView(ifce=ifce)
        self.view.get_ui_manager().add_ui_from_string(TAG_MSG_UI_DESCR)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(label), expand=False, fill=False)
        toolbar = self.view.get_ui_widget("/tag_message_toolbar")
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        hbox.pack_end(toolbar, fill=False, expand=False)
        self.pack_start(hbox, expand=False)
        self.pack_start(gutils.wrap_in_scrolled_window(self.view))
        self.show_all()
    def get_msg(self):
        return self.view.get_msg()

class SetTagDialog(gutils.ReadTextAndToggleDialog, cmd_result.ProblemReporter):
    def __init__(self, ifce, rev=None, parent=None):
        self._ifce = ifce
        self._rev = rev
        cmd_result.ProblemReporter.__init__(self)
        gutils.ReadTextAndToggleDialog.__init__(self, title="gwsmhg: Set Tag",
            prompt="Tag:", toggle_prompt="Local", toggle_state=False, parent=parent)
        self.message = TagMessageWidget(ifce=ifce)
        self.vbox.add(self.message)
        self.connect("response", self._response_cb)
        self.show_all()
    def _response_cb(self, dialog, response_id):
        self.hide()
        if response_id == gtk.RESPONSE_CANCEL:
            self.destroy()
        else:
            tag = self.entry.get_text()
            local = self.toggle.get_active()
            msg = self.message.get_msg()
            self.show_busy()
            result = self._ifce.SCM.do_set_tag(tag=tag, local=local, msg=msg, rev=self._rev)
            self.unshow_busy()
            if result[0] & cmd_result.SUGGEST_FORCE:
                ans = gutils.ask_rename_force_or_cancel(result[1] + result[2], result[0])
                if ans == gutils.EDIT:
                    self.show()
                    return
                if ans == gutils.FORCE:
                    self.show_busy()
                    result = self._ifce.SCM.do_set_tag(tag=tag, local=local, msg=msg, rev=self._rev, force=True)
                    self.unshow_busy()
                    self._report_any_problems(result)
            else:
                self._report_any_problems(result)
            self.destroy()

HISTORY_TABLE_UI_DESCR = \
'''
<ui>
  <popup name="table_popup">
    <placeholder name="top"/>
    <separator/>
    <placeholder name="middle">
      <menuitem action="cs_tag_selected"/>
    </placeholder>
    <separator/>
    <placeholder name="bottom"/>
  </popup>
</ui>
'''

class HistoryTableView(ChangeSetTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        ptype = PrecisType(LOG_TABLE_PRECIS_DESCR, ifce.SCM.get_history_data)
        ChangeSetTableView.__init__(self, ifce, ptype, sel_mode=sel_mode)
        self._action_group[UNIQUE_SELECTION_NOT_PMIC].add_actions(
            [
                ("cs_tag_selected", icons.STOCK_TAG, "Tag", None,
                 "Tag the selected change set",
                 self._tag_cs_acb),
            ])
        self.cwd_merge_id.append(self._ui_manager.add_ui_from_string(HISTORY_TABLE_UI_DESCR))
    def _tag_cs_acb(self, action=None):
        rev = self.get_selected_change_set()
        self._show_busy()
        SetTagDialog(ifce=self._ifce, rev=str(rev)).run()
        self._unshow_busy()

class RemoveTagDialog(gutils.ReadTextDialog, cmd_result.ProblemReporter):
    def __init__(self, ifce, tag=None, parent=None):
        self._ifce = ifce
        self._tag = tag
        cmd_result.ProblemReporter.__init__(self)
        gutils.ReadTextDialog.__init__(self, title='gwsmhg: Remove Tag',
            prompt='Removing Tag: ', suggestion=tag, parent=parent)
        self.entry.set_editable(False)
        self.message = TagMessageWidget(ifce=ifce)
        self.vbox.add(self.message)
        self.connect("response", self._response_cb)
        self.show_all()
        self.set_focus(self.message.view)
    def _response_cb(self, dialog, response_id):
        self.hide()
        if response_id == gtk.RESPONSE_CANCEL:
            self.destroy()
        else:
            msg = self.message.get_msg()
            self.show_busy()
            result = self._ifce.SCM.do_remove_tag(tag=self._tag, msg=msg)
            self.unshow_busy()
            self._report_any_problems(result)
            self.destroy()

class MoveTagDialog(gutils.ReadTextDialog, cmd_result.ProblemReporter):
    def __init__(self, ifce, tag=None, parent=None):
        self._ifce = ifce
        self._tag = tag
        cmd_result.ProblemReporter.__init__(self)
        gutils.ReadTextDialog.__init__(self, title="gwsmhg: Move Tag",
            prompt='Move Tag: ', suggestion=tag, parent=parent)
        self.entry.set_editable(False)
        self._select_widget = ChangeSetSelectWidget(ifce=ifce, label="To Change Set:",
            busy_indicator=self, discard_toggle=False)
        self.vbox.pack_start(self._select_widget)
        self.message = TagMessageWidget(ifce=ifce)
        self.message.view.grab_focus()
        self.vbox.add(self.message)
        self.connect("response", self._response_cb)
        self.show_all()
        self.set_focus(self._select_widget._entry)
    def _response_cb(self, dialog, response_id):
        self.hide()
        if response_id == gtk.RESPONSE_CANCEL:
            self.destroy()
        else:
            rev = self._select_widget.get_change_set()
            msg = self.message.get_msg()
            self.show_busy()
            result = self._ifce.SCM.do_move_tag(tag=self._tag, rev=rev, msg=msg)
            self.unshow_busy()
            self._report_any_problems(result)
            self.destroy()

TAG_TABLE_PRECIS_DESCR = \
[
    ["Tag", gobject.TYPE_STRING, False, []],
    ["Rev", gobject.TYPE_INT, False, []],
    ["Branches", gobject.TYPE_STRING, False, []],
    ["Age", gobject.TYPE_STRING, False, []],
    ["Author", gobject.TYPE_STRING, False, []],
    ["Description", gobject.TYPE_STRING, True, []],
]

TAG_TABLE_UI_DESCR = \
'''
<ui>
  <popup name="table_popup">
    <placeholder name="top"/>
    <separator/>
    <placeholder name="middle">
      <menuitem action="cs_remove_selected_tag"/>
      <menuitem action="cs_move_selected_tag"/>
    </placeholder>
    <separator/>
    <placeholder name="bottom"/>
  </popup>
</ui>
'''

class TagsTableView(ChangeSetTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        ptype = PrecisType(TAG_TABLE_PRECIS_DESCR, ifce.SCM.get_tags_data)
        ChangeSetTableView.__init__(self, ifce, ptype, sel_mode=sel_mode)
        self._action_group[UNIQUE_SELECTION_NOT_PMIC].add_actions(
            [
                ("cs_remove_selected_tag", icons.STOCK_REMOVE, "Remove", None,
                 "Remove the selected tag from the repository",
                 self._remove_tag_cs_acb),
                ("cs_move_selected_tag", icons.STOCK_MOVE, "Move", None,
                 "Move the selected tag to another change set",
                 self._move_tag_cs_acb),
            ])
        self.cwd_merge_id.append(self._ui_manager.add_ui_from_string(TAG_TABLE_UI_DESCR))
    def _remove_tag_cs_acb(self, action=None):
        tag = self.get_selected_change_set()
        self._show_busy()
        RemoveTagDialog(ifce=self._ifce, tag=tag).run()
        self._unshow_busy()
    def _move_tag_cs_acb(self, action=None):
        tag = self.get_selected_change_set()
        self._show_busy()
        MoveTagDialog(ifce=self._ifce, tag=tag).run()
        self._unshow_busy()

TAG_LIST_DESCR = \
[
    ["Tag", gobject.TYPE_STRING, False, []],
]

BRANCH_TABLE_PRECIS_DESCR = \
[
    ["Branch", gobject.TYPE_STRING, False, []],
    ["Rev", gobject.TYPE_INT, False, []],
    ["Tags", gobject.TYPE_STRING, False, []],
    ["Age", gobject.TYPE_STRING, False, []],
    ["Author", gobject.TYPE_STRING, False, []],
    ["Description", gobject.TYPE_STRING, True, []],
]

class BranchesTableView(ChangeSetTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        ptype = PrecisType(BRANCH_TABLE_PRECIS_DESCR, ifce.SCM.get_branches_data)
        ChangeSetTableView.__init__(self, ifce, ptype, sel_mode=sel_mode)

BRANCH_LIST_DESCR = \
[
    ["Branch", gobject.TYPE_STRING, False, []],
]

class ChangeSetSelectWidget(gtk.VBox, gutils.BusyIndicatorUser):
    def __init__(self, ifce, busy_indicator, label="Change Set:", discard_toggle=False):
        gtk.VBox.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, busy_indicator)
        self._ifce = ifce
        hbox = gtk.HBox()
        self._tags_button = gtk.Button(label="Browse _Tags")
        self._tags_button.connect("clicked", self._browse_tags_cb)
        self._branches_button = gtk.Button(label="Browse _Branches")
        self._branches_button.connect("clicked", self._browse_branches_cb)
        self._heads_button = gtk.Button(label="Browse _Heads")
        self._heads_button.connect("clicked", self._browse_heads_cb)
        self._history_button = gtk.Button(label="Browse H_istory")
        self._history_button.connect("clicked", self._browse_history_cb)
        for button in self._tags_button, self._branches_button, self._heads_button, self._history_button:
            hbox.pack_start(button, expand=True, fill=False)
        self.pack_start(hbox, expand=False)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(label), fill=False, expand=False)
        self._entry = gutils.EntryWithHistory()
        self._entry.set_width_chars(32)
        self._entry.connect("activate", self._entry_cb)
        hbox.pack_start(self._entry, expand=True, fill=True)
        if discard_toggle:
            self._discard_toggle = gtk.CheckButton('Discard local changes')
            self._discard_toggle.set_active(False)
            hbox.pack_start(self._discard_toggle, expand=False, fill=False)
        else:
            self._discard_toggle = None
        self.pack_start(hbox, expand=False, fill=False)
        self.show_all()
    def _browse_change_set(self, ptype, title, size=(640, 240)):
        self._show_busy()
        dialog = SelectDialog(ifce=self._ifce, ptype=ptype, title=title, size=size, parent=None)
        self._unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self._entry.set_text(dialog.get_change_set())
        dialog.destroy()
    def _browse_tags_cb(self, button=None):
        ptype = PrecisType(TAG_LIST_DESCR, self._ifce.SCM.get_tags_list_for_table)
        self._browse_change_set(ptype, "Tag", size=(160, 320))
    def _browse_branches_cb(self, button=None):
        ptype = PrecisType(TAG_LIST_DESCR, self._ifce.SCM.get_branches_list_for_table)
        self._browse_change_set(ptype, "Branch", size=(160, 320))
    def _browse_heads_cb(self, button=None):
        ptype = PrecisType(LOG_TABLE_PRECIS_DESCR, self._ifce.SCM.get_heads_data)
        self._browse_change_set(ptype, "Head", size=(640, 480))
    def _browse_history_cb(self, button=None):
        ptype = PrecisType(LOG_TABLE_PRECIS_DESCR, self._ifce.SCM.get_history_data)
        self._browse_change_set(ptype, "Change Set", size=(640, 480))
    def _entry_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def get_change_set(self):
        return self._entry.get_text()
    def get_discard(self):
        if self._discard_toggle is None:
            return False
        return self._discard_toggle.get_active()

class ChangeSetSelectDialog(gtk.Dialog, gutils.BusyIndicator, gutils.BusyIndicatorUser):
    def __init__(self, ifce, discard_toggle=False, parent=None):
        gutils.BusyIndicator.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, self)
        title = "gwsmg: Select Change Set: %s" % utils.path_rel_home(os.getcwd())
        gtk.Dialog.__init__(self, title=title, parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        self._widget = ChangeSetSelectWidget(ifce=ifce, busy_indicator=self.get_busy_indicator(),
            discard_toggle=discard_toggle)
        self.vbox.pack_start(self._widget)
        self.show_all()
    def get_change_set(self):
        return self._widget.get_change_set()
    def get_discard(self):
        return self._widget.get_discard()

class FileTreeStore(file_tree.FileTreeStore):
    def __init__(self, ifce, rev):
        self._rev = rev
        self._ifce = ifce
        row_data = apply(file_tree.FileTreeRowData, self._ifce.SCM.get_status_row_data())
        file_tree.FileTreeStore.__init__(self, show_hidden=True, row_data=row_data)
        self.repopulate()
    def update(self, fsobj_iter=None):
        res, files, dummy = self._ifce.SCM.get_change_set_files(self._rev)
        if res == 0:
            for file_name, status, extra_info in files:
                self.find_or_insert_file(file_name, file_status=status, extra_info=extra_info)
    def repopulate(self):
        self.clear()
        self.update()

CHANGE_SET_FILES_UI_DESCR = \
'''
<ui>
  <popup name="files_popup">
    <placeholder name="selection">
      <menuitem action="scm_diff_files_selection"/>
    </placeholder>
    <separator/>
    <placeholder name="no_selection"/>
      <menuitem action="scm_diff_files_all"/>
    <separator/>
  </popup>
</ui>
'''

class FileTreeView(file_tree.FileTreeView):
    def __init__(self, ifce, rev, busy_indicator, tooltips=None):
        self._ifce = ifce
        self._rev = rev
        self.model = FileTreeStore(ifce, rev)
        file_tree.FileTreeView.__init__(self, model=self.model, busy_indicator=busy_indicator,
            tooltips=tooltips, auto_refresh=False, show_status=True)
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.set_headers_visible(False)
        self._action_group[file_tree.SELECTION].add_actions(
            [
                ("scm_diff_files_selection", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for selected file(s)", self._diff_selected_files_acb),
            ])
        self._action_group[file_tree.NO_SELECTION].add_actions(
            [
                ("scm_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self._diff_all_files_acb),
            ])
        self._action_group[file_tree.SELECTION_INDIFFERENT].set_visible(False)
        self.scm_change_merge_id = self._ui_manager.add_ui_from_string(CHANGE_SET_FILES_UI_DESCR)
        self.expand_all()
    def _diff_selected_files_acb(self, action=None):
        parent = self._get_gtk_window()
        self._show_busy()
        dialog = diff.ScmDiffTextDialog(parent=parent, ifce=self._ifce,
                                     file_list=self.get_selected_files(),
                                     torev=self._rev, modal=False)
        self._unshow_busy()
        dialog.show()
    def _diff_all_files_acb(self, action=None):
        parent = self._get_gtk_window()
        self._show_busy()
        dialog = diff.ScmDiffTextDialog(parent=parent, ifce=self._ifce,
                                     torev=self._rev, modal=False)
        self._unshow_busy()
        dialog.show()

class ChangeSetSummaryDialog(gtk.Dialog, gutils.BusyIndicator, gutils.BusyIndicatorUser):
    def __init__(self, ifce, rev, parent=None):
        self._rev = rev
        self._ifce = ifce
        gutils.BusyIndicator.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, self)
        title = "gwsmg: Change Set: %s : %s" % (rev, utils.path_rel_home(os.getcwd()))
        gtk.Dialog.__init__(self, title=title, parent=parent,
                            flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
                           )
        self._ifce = ifce
        res, summary, serr = self.get_change_set_summary()
        self._add_labelled_texts([("Precis:", summary['PRECIS'])])
        self._add_labelled_texts([("Revision:", summary['REV']), ("Node:", summary['NODE'])])
        self._add_labelled_texts([("Date:", summary['DATE']), ("Age:", summary['AGE'])])
        self._add_labelled_texts([("Author:", summary['AUTHOR']), ("Email:", summary['EMAIL'])])
        self._add_labelled_texts([("Tags:", summary['TAGS'])])
        self._add_labelled_texts([("Branches:", summary['BRANCHES'])])
        vpaned1 = gtk.VPaned()
        self.vbox.pack_start(vpaned1)
        vbox = gtk.VBox()
        self._add_label("Description:", vbox)
        cdv = gtk.TextView()
        cdv.set_editable(False)
        cdv.set_cursor_visible(False)
        cdv.get_buffer().set_text(summary['DESCR'])
        vbox.pack_start(gutils.wrap_in_scrolled_window(cdv), expand=True)
        vpaned1.add1(vbox)
        vpaned2 = gtk.VPaned()
        vbox = gtk.VBox()
        self._add_label("File(s):", vbox)
        self.ftv = self.get_file_tree_view()
        vbox.pack_start(gutils.wrap_in_scrolled_window(self.ftv), expand=True)
        vpaned2.add1(vbox)
        vbox = gtk.VBox()
        self._add_label("Parent(s):", vbox)
        ptv = self.get_parents_view()
        vbox.pack_start(gutils.wrap_in_scrolled_window(ptv), expand=True)
        vpaned2.add2(vbox)
        vpaned1.add2(vpaned2)
        self.connect("response", self._close_cb)
        self.show_all()
    def get_change_set_summary(self):
        return self._ifce.SCM.get_change_set_summary(self._rev)
    def get_file_tree_view(self):
        return FileTreeView(self._ifce, self._rev, busy_indicator=self.get_busy_indicator())
    def get_parents_view(self):
        return ParentsTableView(self._ifce, self._rev, auto_refresh_on=False,
            busy_indicator=self.get_busy_indicator())
    def _add_label(self, text, component=None):
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(text), expand=False, fill=False)
        if component:
            component.pack_start(hbox, expand=False, fill=False)
        else:
            self.vbox.pack_start(hbox, expand=False)
    def _add_labelled_texts(self, list, component=None):
        hbox = gtk.HBox()
        for item in list:
            label = item[0].strip()
            text = item[1].strip()
            hbox.pack_start(gtk.Label(label), expand=False, fill=False)
            entry = gtk.Entry()
            entry.set_text(text)
            entry.set_editable(False)
            entry.set_width_chars(len(text))
            hbox.pack_start(entry, expand=False, fill=True)
        if component:
            component.pack_start(hbox, expand=False, fill=True)
        else:
            self.vbox.pack_start(hbox, expand=False, fill=True)
    def _close_cb(self, dialog, response_id):
        self.destroy()

class BackoutDialog(gutils.ReadTextAndToggleDialog, cmd_result.ProblemReporter):
    def __init__(self, ifce, rev=None, parent=None):
        self._ifce = ifce
        self._rev = rev
        cmd_result.ProblemReporter.__init__(self)
        gutils.ReadTextAndToggleDialog.__init__(self, title='gwsmhg: Backout',
            prompt='Backing Out: ', suggestion=rev, parent=parent,
            toggle_prompt='Merge', toggle_state=False)
        self.entry.set_editable(False)
        self._radio_labels = []
        self._parent_revs = []
        res, parents_data, serr = self._ifce.SCM.get_parents_data(rev)
        if len(parents_data) > 1:
            for data in parents_data:
                rev = str(data[gutils.find_label_index(LOG_TABLE_PRECIS_DESCR, 'Rev')])
                descr = data[gutils.find_label_index(LOG_TABLE_PRECIS_DESCR, 'Description')]
                self._radio_labels.append('%s: %s' % (rev, descr))
                self._parent_revs.append(rev)
            self._radio_buttons = gutils.RadioButtonFramedVBox(title='Select Parent', labels=self._radio_labels)
            self.vbox.add(self._radio_buttons)
        self.message = TagMessageWidget(ifce=ifce, label="Message")
        self.vbox.add(self.message)
        self.connect("response", self._response_cb)
        self.show_all()
        self.set_focus(self.message.view)
    def _response_cb(self, dialog, response_id):
        self.hide()
        if response_id == gtk.RESPONSE_CANCEL:
            self.destroy()
        else:
            merge = self.toggle.get_active()
            if self._parent_revs:
                parent = self._parent_revs[self._radio_buttons.get_selected_index()]
            else:
                parent = None
            msg = self.message.get_msg()
            self.show_busy()
            result = self._ifce.SCM.do_backout(rev=self._rev, merge=merge, parent=parent, msg=msg)
            self.unshow_busy()
            self._report_any_problems(result)
            self.destroy()

