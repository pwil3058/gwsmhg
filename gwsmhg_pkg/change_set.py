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

import gtk, gobject
from gwsmhg_pkg import cmd_result, gutils

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

class ParentsView(gutils.AutoRefreshTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE, auto_refresh_on=False, auto_refresh_interval=30000):
        self._ifce = ifce
        gutils.AutoRefreshTableView.__init__(self, LOG_TABLE_PRECIS_DESCR, sel_mode=sel_mode,
            auto_refresh_on=auto_refresh_on, auto_refresh_interval=auto_refresh_interval,
            busy_indicator=self._ifce.log.get_busy_indicator())
        self._ifce.PM.add_notification_cb(self._ifce.PM.tag_changing_cmds, self.refresh_contents_if_mapped)
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

class HeadsView(gutils.AutoRefreshTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE, auto_refresh_on=False, auto_refresh_interval=30000):
        self._ifce = ifce
        gutils.AutoRefreshTableView.__init__(self, LOG_TABLE_PRECIS_DESCR, sel_mode=sel_mode,
            auto_refresh_on=auto_refresh_on, auto_refresh_interval=auto_refresh_interval,
            busy_indicator=self._ifce.log.get_busy_indicator())
        self._ifce.SCM.add_notification_cb(["commit"], self.refresh_contents_if_mapped)
        self._ifce.PM.add_notification_cb(self._ifce.PM.tag_changing_cmds, self.refresh_contents_if_mapped)
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

class TagsView(gutils.AutoRefreshTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE, auto_refresh_on=False, auto_refresh_interval=3600000):
        self._ifce = ifce
        gutils.AutoRefreshTableView.__init__(self, TAG_TABLE_PRECIS_DESCR, sel_mode=sel_mode,
            auto_refresh_on=auto_refresh_on, auto_refresh_interval=auto_refresh_interval,
            busy_indicator=self._ifce.log.get_busy_indicator())
        self._ifce.SCM.add_notification_cb(["commit"], self.refresh_contents_if_mapped)
        self._ifce.PM.add_notification_cb(self._ifce.PM.tag_changing_cmds, self.refresh_contents_if_mapped)
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

class BranchesView(gutils.AutoRefreshTableView):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE, auto_refresh_on=False, auto_refresh_interval=3600000):
        self._ifce = ifce
        gutils.AutoRefreshTableView.__init__(self, BRANCH_TABLE_PRECIS_DESCR, sel_mode=sel_mode,
            auto_refresh_on=auto_refresh_on, auto_refresh_interval=auto_refresh_interval,
            busy_indicator=self._ifce.log.get_busy_indicator())
        self._ifce.SCM.add_notification_cb(["commit"], self.refresh_contents_if_mapped)
        self._ifce.PM.add_notification_cb(self._ifce.PM.tag_changing_cmds, self.refresh_contents_if_mapped)
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

