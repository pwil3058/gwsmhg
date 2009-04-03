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
from gwsmhg_pkg import cmd_result

COLUMNS = (gobject.TYPE_INT,
           gobject.TYPE_STRING,
           gobject.TYPE_STRING,
           gobject.TYPE_STRING,
           gobject.TYPE_STRING,
           gobject.TYPE_STRING)

REV_ID, AGE, TAGS, BRANCHES, AUTHOR, DESCRIPTION = range(len(COLUMNS))

LABEL = \
      { REV_ID: "Rev",
        AGE: "Age",
        TAGS: "Tags",
        BRANCHES: "Branches",
        AUTHOR: "Author",
        DESCRIPTION: "Description",
      }

class ChangeSetView(gtk.TreeView):
    def __init__(self):
        model = apply(gtk.ListStore, COLUMNS)
        gtk.TreeView.__init__(self, model)
        bgnd = ["#F0F0F0", "white"]
        for colid in [REV_ID, AGE, TAGS, BRANCHES, AUTHOR, DESCRIPTION]:
            cell = gtk.CellRendererText()
            tvcolumn = gtk.TreeViewColumn(LABEL[colid], cell, text=colid)
            cell.set_property("cell-background", bgnd[colid % 2])
            tvcolumn.set_expand(colid==DESCRIPTION)
            self.append_column(tvcolumn)
        self.set_headers_visible(False)
    def set_contents(self, cset_list):
        model = self.get_model()
        model.clear()
        for cset in cset_list:
            model.append(cset)
        self.set_headers_visible(self.get_model().iter_n_children(None) > 0)

class ParentsView(ChangeSetView):
    def __init__(self, scm_ifce):
        ChangeSetView.__init__(self)
        self._scm_ifce = scm_ifce
        self._scm_ifce.add_commit_notification_cb(self.update_after_commit)
        self.get_selection().set_mode(gtk.SELECTION_SINGLE)
        self.get_selection().unselect_all()
        self._auto_update_interval = 1000
        self._auto_update_id = None
        self._auto_update()
    def _auto_update(self):
        self.update()
        self._auto_update_id = gobject.timeout_add(self._auto_update_interval, self._auto_update)
        return False
    def restart_auto_update(self):
        gobject.source_remove(self._auto_update_id)
        self._auto_update()
    def get_scm_ifce(self):
        return self._scm_ifce
    def set_scm_ifce(self, scm_ifce):
        old_scm_ifce = self.get_scm_ifce()
        if old_scm_ifce:
            old_scm_ifce.del_commit_notification_cb(self.update_after_commit)
        self._scm_ifce = scm_ifce
        new_scm_ifce = self.get_scm_ifce()
        if new_scm_ifce:
            new_scm_ifce.add_commit_notification_cb(self.update_after_commit)
        self.restart_auto_update()
    def update(self):
        self._auto_update_interval = 30000
        if self._scm_ifce:
            res, parents, serr = self._scm_ifce.get_parents()
            if res == cmd_result.OK:
                self.set_contents(parents)
                for parent in parents:
                    # if any parent's age is expressed in seconds then update every second
                    if parent[AGE].find("sec") != -1:
                        self._auto_update_interval = 1000
                        break
            else:
                self.set_contents([])
    def update_after_commit(self, files_in_commit):
        self.restart_auto_update()

