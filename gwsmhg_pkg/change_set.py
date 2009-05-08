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

import gtk, gobject, os
from gwsmhg_pkg import cmd_result, gutils, utils, icons

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
    def __init__(self, ifce, ptype, sel_mode=gtk.SELECTION_SINGLE):
        self._ifce = ifce
        self._ptype = ptype
        cmd_result.ProblemReporter.__init__(self)
        gutils.MapManagedTableView.__init__(self, descr=ptype.descr, sel_mode=sel_mode,
            busy_indicator=self._ifce.log.get_busy_indicator())
        self._ifce.SCM.add_notification_cb(["commit"], self.refresh_contents_if_mapped)
        self._ifce.PM.add_notification_cb(self._ifce.PM.tag_changing_cmds, self.refresh_contents_if_mapped)
        self._ifce.log.add_notification_cb(["manual_cmd"], self.refresh_contents_if_mapped)
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
            ])
        self.cwd_merge_id.append(self._ui_manager.add_ui_from_string(CS_TABLE_BASIC_UI_DESCR))
        self.show_all()
    def _set_action_sensitivities(self):
        sel = self.get_selection().count_selected_rows() != 0
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
        pass
    def _update_ws_to_cs_acb(self, action):
        rev = self.get_selected_change_set()
        self._show_busy()
        result = self._ifce.SCM.do_update_workspace(rev=str(rev))
        self._unshow_busy()
        self._report_any_problems(result)
    def _merge_ws_with_cs_acb(self, action):
        rev = self.get_selected_change_set()
        self._show_busy()
        result = self._ifce.SCM.do_merge_workspace(rev=str(rev))
        self._unshow_busy()
        self._report_any_problems(result)

class AUPrecisTableView(PrecisTableView):
    def __init__(self, ifce, ptype, age_col, sel_mode=gtk.SELECTION_SINGLE,
        auto_refresh_on=True, auto_refresh_interval=3600000):
        self._age_col = age_col
        self.rtoc = gutils.RefreshController(is_on=auto_refresh_on, interval=auto_refresh_interval)
        self._normal_interval = auto_refresh_interval
        self.rtoc.set_function(self._refresh_contents)
        PrecisTableView.__init__(self, ifce, ptype, sel_mode=sel_mode)
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
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE, auto_refresh_on=True, auto_refresh_interval=3600000):
        ptype = PrecisType(LOG_TABLE_PRECIS_DESCR, ifce.SCM.get_parents_data)
        AUPrecisTableView.__init__(self, ifce, ptype, sel_mode=sel_mode,
                                   age_col = LOG_TABLE_PRECIS_AGE,
                                   auto_refresh_on=auto_refresh_on,
                                   auto_refresh_interval=auto_refresh_interval)
        self._ifce.SCM.add_notification_cb(["update", "merge"], self.refresh_contents_if_mapped)
        self._action_group[UNIQUE_SELECTION_NOT_PMIC].get_action("cs_update_ws_to").set_visible(False)
        self._action_group[UNIQUE_SELECTION_NOT_PMIC].get_action("cs_merge_ws_with").set_visible(False)
        self._action_group[gutils.ALWAYS_ON].get_action("table_refresh_contents").set_visible(False)

class HeadsTableView(PrecisTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        ptype = PrecisType(LOG_TABLE_PRECIS_DESCR, ifce.SCM.get_heads_data)
        PrecisTableView.__init__(self, ifce, ptype, sel_mode=sel_mode)

class HistoryTableView(PrecisTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        ptype = PrecisType(LOG_TABLE_PRECIS_DESCR, ifce.SCM.get_history_data)
        PrecisTableView.__init__(self, ifce, ptype, sel_mode=sel_mode)

TAG_TABLE_PRECIS_DESCR = \
[
    ["Tag", gobject.TYPE_STRING, False, []],
    ["Rev", gobject.TYPE_INT, False, []],
    ["Branches", gobject.TYPE_STRING, False, []],
    ["Age", gobject.TYPE_STRING, False, []],
    ["Author", gobject.TYPE_STRING, False, []],
    ["Description", gobject.TYPE_STRING, True, []],
]

class TagsTableView(PrecisTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        ptype = PrecisType(TAG_TABLE_PRECIS_DESCR, ifce.SCM.get_tags_data)
        PrecisTableView.__init__(self, ifce, ptype, sel_mode=sel_mode)

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

class BranchesTableView(PrecisTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        ptype = PrecisType(BRANCH_TABLE_PRECIS_DESCR, ifce.SCM.get_branches_data)
        PrecisTableView.__init__(self, ifce, ptype, sel_mode=sel_mode)

BRANCH_LIST_DESCR = \
[
    ["Branch", gobject.TYPE_STRING, False, []],
]

class ChangeSetSelectDialog(gtk.Dialog, gutils.BusyIndicator, gutils.BusyIndicatorUser):
    def __init__(self, ifce, parent=None):
        gutils.BusyIndicator.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, self)
        title = "gwsmg: Select Change Set: %s" % utils.path_rel_home(os.getcwd())
        gtk.Dialog.__init__(self, title=title, parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
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
            hbox.pack_start(button, expand=False, fill=False)
        self.vbox.pack_start(hbox)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Change Set:"))
        self._entry = gutils.EntryWithHistory()
        self._entry.set_width_chars(32)
        self._entry.connect("activate", self._entry_cb)
        hbox.pack_start(self._entry, expand=True, fill=True)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        self.show_all()
    def _browse_change_set(self, ptype, title, size=(640, 240)):
        self._show_busy()
        dialog = SelectDialog(ifce=self._ifce, ptype=ptype, title=title, size=size, parent=self)
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

