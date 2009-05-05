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
from gwsmhg_pkg import cmd_result, gutils, utils

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
LOG_TABLE_PRECIS_REV = gutils.find_label_index(LOG_TABLE_PRECIS_DESCR, "Rev")

class ParentsTableView(gutils.AutoRefreshTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE, auto_refresh_on=False, auto_refresh_interval=30000):
        self._ifce = ifce
        gutils.AutoRefreshTableView.__init__(self, LOG_TABLE_PRECIS_DESCR, sel_mode=sel_mode,
            auto_refresh_on=auto_refresh_on, auto_refresh_interval=auto_refresh_interval,
            busy_indicator=self._ifce.log.get_busy_indicator())
        self._ifce.PM.add_notification_cb(self._ifce.PM.tag_changing_cmds, self.refresh_contents_if_mapped)
        self._ifce.log.add_notification_cb(["manual_cmd"], self.refresh_contents_if_mapped)
        self.show_all()
    def _refresh_contents(self):
        res, parents, serr = self._ifce.SCM.get_parents_data()
        if res == cmd_result.OK and parents:
            desired_interval = self._normal_interval
            self.set_contents(parents)
            # if any parent's age is expressed in seconds then update every second
            # they're in time order so only need to look at first one
            if parents[0][LOG_TABLE_PRECIS_AGE].find("sec") != -1:
                desired_interval = 1000
            elif parents[0][LOG_TABLE_PRECIS_AGE].find("min") != -1:
                desired_interval = 30000
            elif parents[0][LOG_TABLE_PRECIS_AGE].find("hour") != -1:
                    desired_interval = 1800000
            if desired_interval is not self.rtoc.get_interval():
                self.rtoc.set_interval(desired_interval)
        else:
            self.set_contents([])
        gutils.AutoRefreshTableView._refresh_contents(self)

class HeadsTableView(gutils.AutoRefreshTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE, auto_refresh_on=False, auto_refresh_interval=30000):
        self._ifce = ifce
        gutils.AutoRefreshTableView.__init__(self, LOG_TABLE_PRECIS_DESCR, sel_mode=sel_mode,
            auto_refresh_on=auto_refresh_on, auto_refresh_interval=auto_refresh_interval,
            busy_indicator=self._ifce.log.get_busy_indicator())
        self._ifce.SCM.add_notification_cb(["commit"], self.refresh_contents_if_mapped)
        self._ifce.PM.add_notification_cb(self._ifce.PM.tag_changing_cmds, self.refresh_contents_if_mapped)
        self._ifce.log.add_notification_cb(["manual_cmd"], self.refresh_contents_if_mapped)
        self.show_all()
    def _refresh_contents(self):
        res, heads, serr = self._ifce.SCM.get_heads_data()
        if res == cmd_result.OK and heads:
            desired_interval = self._normal_interval
            self.set_contents(heads)
            # if any head's age is expressed in seconds then update every second
            # they're in time order so only need to look at first one
            if heads[0][LOG_TABLE_PRECIS_AGE].find("sec") != -1:
                desired_interval = 1000
            elif heads[0][LOG_TABLE_PRECIS_AGE].find("min") != -1:
                desired_interval = 30000
            elif heads[0][LOG_TABLE_PRECIS_AGE].find("hour") != -1:
                    desired_interval = 1800000
            if desired_interval is not self.rtoc.get_interval():
                self.rtoc.set_interval(desired_interval)
        else:
            self.set_contents([])
        gutils.AutoRefreshTableView._refresh_contents(self)

class HeadsSelectView(gutils.TableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        self._ifce = ifce
        gutils.TableView.__init__(self, LOG_TABLE_PRECIS_DESCR, sel_mode=sel_mode)
        self.set_size_request(640, 240)
        self._set_contents()
        self.show_all()
    def _set_contents(self):
        res, heads, serr = self._ifce.SCM.get_heads_data()
        if res == cmd_result.OK and heads:
            self.set_contents(heads)
        else:
            self.set_contents([])
    def get_selected_head(self):
        data = self.get_selected_data([LOG_TABLE_PRECIS_REV])
        return str(data[0][0])

class HeadSelectDialog(gtk.Dialog):
    def __init__(self, ifce, parent=None):
        gtk.Dialog.__init__(self, title="gwsmg: Select Head", parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        self.heads_view = HeadsSelectView(ifce=ifce)
        self.vbox.pack_start(gutils.wrap_in_scrolled_window(self.heads_view))
        self.show_all()
        self.heads_view.get_selection().unselect_all()
    def get_head(self):
        return self.heads_view.get_selected_head()

class HistorySelectView(gutils.TableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        self._ifce = ifce
        gutils.TableView.__init__(self, LOG_TABLE_PRECIS_DESCR, sel_mode=sel_mode)
        self.set_size_request(640, 240)
        self._set_contents()
        self.show_all()
    def _set_contents(self):
        res, history, serr = self._ifce.SCM.get_history_data()
        if res == cmd_result.OK and history:
            self.set_contents(history)
        else:
            self.set_contents([])
    def get_selected_rev(self):
        data = self.get_selected_data([LOG_TABLE_PRECIS_REV])
        return str(data[0][0])

class HistorySelectDialog(gtk.Dialog):
    def __init__(self, ifce, parent=None):
        gtk.Dialog.__init__(self, title="gwsmg: Select From History", parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        self.history_view = HistorySelectView(ifce=ifce)
        self.vbox.pack_start(gutils.wrap_in_scrolled_window(self.history_view))
        self.show_all()
        self.history_view.get_selection().unselect_all()
    def get_rev(self):
        return self.history_view.get_selected_rev()

TAG_TABLE_PRECIS_DESCR = \
[
    ["Tag", gobject.TYPE_STRING, False, []],
    ["Rev", gobject.TYPE_INT, False, []],
    ["Branches", gobject.TYPE_STRING, False, []],
    ["Age", gobject.TYPE_STRING, False, []],
    ["Author", gobject.TYPE_STRING, False, []],
    ["Description", gobject.TYPE_STRING, True, []],
]

TAG_TABLE_PRECIS_AGE = gutils.find_label_index(TAG_TABLE_PRECIS_DESCR, "Age")

class TagsTableView(gutils.AutoRefreshTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE, auto_refresh_on=False, auto_refresh_interval=3600000):
        self._ifce = ifce
        gutils.AutoRefreshTableView.__init__(self, TAG_TABLE_PRECIS_DESCR, sel_mode=sel_mode,
            auto_refresh_on=auto_refresh_on, auto_refresh_interval=auto_refresh_interval,
            busy_indicator=self._ifce.log.get_busy_indicator())
        self._ifce.SCM.add_notification_cb(["commit"], self.refresh_contents_if_mapped)
        self._ifce.PM.add_notification_cb(self._ifce.PM.tag_changing_cmds, self.refresh_contents_if_mapped)
        self._ifce.log.add_notification_cb(["manual_cmd"], self.refresh_contents_if_mapped)
        self.show_all()
    def _refresh_contents(self):
        res, tags, serr = self._ifce.SCM.get_tags_data()
        if res == cmd_result.OK and tags:
            desired_interval = self._normal_interval
            self.set_contents(tags)
            # if any tag's age is expressed in seconds then update every second
            # they're in time order so only need to look at first one
            if tags[0][TAG_TABLE_PRECIS_AGE].find("sec") != -1:
                desired_interval = 1000
            elif tags[0][TAG_TABLE_PRECIS_AGE].find("min") != -1:
                desired_interval = 30000
            elif tags[0][TAG_TABLE_PRECIS_AGE].find("hour") != -1:
                    desired_interval = 1800000
            if desired_interval is not self.rtoc.get_interval():
                self.rtoc.set_interval(desired_interval)
        else:
            self.set_contents([])
        gutils.AutoRefreshTableView._refresh_contents(self)

TAG_LIST_DESCR = \
[
    ["Tag", gobject.TYPE_STRING, False, []],
]

TAG_LIST_TAG = gutils.find_label_index(TAG_LIST_DESCR, "Tag")

class TagsSelectView(gutils.TableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        self._ifce = ifce
        gutils.TableView.__init__(self, TAG_LIST_DESCR,
                                  sel_mode=sel_mode, perm_headers=False)
        self.set_size_request(160, 320)
        self._set_contents()
        self.show_all()
    def _set_contents(self):
        res, tags, serr = self._ifce.SCM.get_tags_list()
        if res == cmd_result.OK and tags:
            seq_list = []
            for tag in tags:
                seq_list.append([tag])
            self.set_contents(seq_list)
        else:
            self.set_contents([])
    def get_selected_tag(self):
        data = self.get_selected_data([TAG_LIST_TAG])
        return str(data[0][0])

class TagSelectDialog(gtk.Dialog):
    def __init__(self, ifce, parent=None):
        gtk.Dialog.__init__(self, title="gwsmg: Select Tag", parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        self.tags_view = TagsSelectView(ifce=ifce)
        self.tags_view.set_headers_visible(False)
        self.vbox.pack_start(gutils.wrap_in_scrolled_window(self.tags_view))
        self.show_all()
        self.tags_view.get_selection().unselect_all()
    def get_tag(self):
        return self.tags_view.get_selected_tag()

BRANCH_TABLE_PRECIS_DESCR = \
[
    ["Branch", gobject.TYPE_STRING, False, []],
    ["Rev", gobject.TYPE_INT, False, []],
    ["Tags", gobject.TYPE_STRING, False, []],
    ["Age", gobject.TYPE_STRING, False, []],
    ["Author", gobject.TYPE_STRING, False, []],
    ["Description", gobject.TYPE_STRING, True, []],
]

BRANCH_TABLE_PRECIS_AGE = gutils.find_label_index(BRANCH_TABLE_PRECIS_DESCR, "Age")

class BranchesTableView(gutils.AutoRefreshTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE, auto_refresh_on=False, auto_refresh_interval=3600000):
        self._ifce = ifce
        gutils.AutoRefreshTableView.__init__(self, BRANCH_TABLE_PRECIS_DESCR, sel_mode=sel_mode,
            auto_refresh_on=auto_refresh_on, auto_refresh_interval=auto_refresh_interval,
            busy_indicator=self._ifce.log.get_busy_indicator())
        self._ifce.SCM.add_notification_cb(["commit"], self.refresh_contents_if_mapped)
        self._ifce.PM.add_notification_cb(self._ifce.PM.tag_changing_cmds, self.refresh_contents_if_mapped)
        self._ifce.log.add_notification_cb(["manual_cmd"], self.refresh_contents_if_mapped)
        self.show_all()
    def _refresh_contents(self):
        res, branches, serr = self._ifce.SCM.get_branches_data()
        if res == cmd_result.OK and branches:
            desired_interval = self._normal_interval
            self.set_contents(branches)
            # if any branch's age is expressed in seconds then update every second
            # they're in time order so only need to look at first one
            if branches[0][BRANCH_TABLE_PRECIS_AGE].find("sec") != -1:
                desired_interval = 1000
            elif branches[0][BRANCH_TABLE_PRECIS_AGE].find("min") != -1:
                desired_interval = 30000
            elif branches[0][BRANCH_TABLE_PRECIS_AGE].find("hour") != -1:
                    desired_interval = 1800000
            if desired_interval is not self.rtoc.get_interval():
                self.rtoc.set_interval(desired_interval)
        else:
            self.set_contents([])
        gutils.AutoRefreshTableView._refresh_contents(self)

BRANCH_LIST_DESCR = \
[
    ["Branch", gobject.TYPE_STRING, False, []],
]

BRANCH_LIST_BRANCH = gutils.find_label_index(BRANCH_LIST_DESCR, "Branch")

class BranchesSelectView(gutils.TableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        self._ifce = ifce
        gutils.TableView.__init__(self, BRANCH_LIST_DESCR,
                                  sel_mode=sel_mode, perm_headers=False)
        self.set_size_request(160, 320)
        self._set_contents()
        self.show_all()
    def _set_contents(self):
        res, branches, serr = self._ifce.SCM.get_branches_list()
        if res == cmd_result.OK and branches:
            seq_list = []
            for branch in branches:
                seq_list.append([branch])
            self.set_contents(seq_list)
        else:
            self.set_contents([])
    def get_selected_branch(self):
        data = self.get_selected_data([BRANCH_LIST_BRANCH])
        return str(data[0][0])

class BranchSelectDialog(gtk.Dialog):
    def __init__(self, ifce, parent=None):
        gtk.Dialog.__init__(self, title="gwsmg: Select Branch", parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        self.branches_view = BranchesSelectView(ifce=ifce)
        self.branches_view.set_headers_visible(False)
        self.vbox.pack_start(gutils.wrap_in_scrolled_window(self.branches_view))
        self.show_all()
        self.branches_view.get_selection().unselect_all()
    def get_branch(self):
        return self.branches_view.get_selected_branch()

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
        self._path = gutils.EntryWithHistory()
        self._path.set_width_chars(32)
        self._path.connect("activate", self._path_cb)
        hbox.pack_start(self._path, expand=True, fill=True)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        self.show_all()
    def _browse_tags_cb(self, button=None):
        self._show_busy()
        dialog = TagSelectDialog(ifce=self._ifce, parent=self)
        self._unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self._path.set_text(dialog.get_tag())
        dialog.destroy()
    def _browse_branches_cb(self, button=None):
        self._show_busy()
        dialog = BranchSelectDialog(ifce=self._ifce, parent=self)
        self._unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self._path.set_text(dialog.get_branch())
        dialog.destroy()
    def _browse_heads_cb(self, button=None):
        self._show_busy()
        dialog = HeadSelectDialog(ifce=self._ifce, parent=self)
        self._unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self._path.set_text(dialog.get_head())
        dialog.destroy()
    def _browse_history_cb(self, button=None):
        self._show_busy()
        dialog = HistorySelectDialog(ifce=self._ifce, parent=self)
        self._unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self._path.set_text(dialog.get_rev())
        dialog.destroy()
    def _path_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def get_change_set(self):
        return self._path.get_text()

