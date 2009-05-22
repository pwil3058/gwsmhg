### Copyright (C) 2005 Peter Williams <peter_ono@users.sourceforge.net>

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
from gwsmhg_pkg import gutils, cmd_result, change_set, icons, file_tree, diff

PATH_TABLE_PRECIS_DESCR = \
[
    ["Alias", gobject.TYPE_STRING, False, []],
    ["Path", gobject.TYPE_STRING, True, []],
]

PATH_TABLE_UI_DESCR = \
'''
<ui>
  <popup name="table_popup">
    <placeholder name="top">
      <menuitem action="view_incoming_from_path"/>
      <menuitem action="pull_from_path"/>
    </placeholder>
    <separator/>
    <placeholder name="middle">
      <menuitem action="view_outgoing_to_path"/>
      <menuitem action="push_to_path"/>
    </placeholder>
    <separator/>
    <placeholder name="bottom"/>
  </popup>
</ui>
'''

class PathTableView(gutils.MapManagedTableView, cmd_result.ProblemReporter):
    def __init__(self, ifce, sel_mode=gtk.SELECTION_SINGLE):
        self._ifce = ifce
        cmd_result.ProblemReporter.__init__(self)
        gutils.MapManagedTableView.__init__(self, descr=PATH_TABLE_PRECIS_DESCR,
            sel_mode=sel_mode, busy_indicator=self._ifce.log.get_busy_indicator())
        for condition in [change_set.UNIQUE_SELECTION, change_set.UNIQUE_SELECTION_NOT_PMIC]:
            self._action_group[condition] = gtk.ActionGroup(condition)
            self._ui_manager.insert_action_group(self._action_group[condition], -1)
        self._action_group[change_set.UNIQUE_SELECTION].add_actions(
            [
                ("view_incoming_from_path", gtk.STOCK_INFO, "Incoming", None,
                 "View the incoming change sets available to pull from the selected path",
                 self._view_incoming_acb),
                ("view_outgoing_to_path", gtk.STOCK_INFO, "Outgoing", None,
                 "View the outgoing change sets ready to push to the selected path",
                 self._view_outgoing_acb),
                ("pull_from_path", gtk.STOCK_EXECUTE, "Pull", None,
                 "Pull all available change sets from the selected path",
                 self._pull_from_acb),
            ])
        self._action_group[change_set.UNIQUE_SELECTION_NOT_PMIC].add_actions(
            [
                ("push_to_path", gtk.STOCK_EXECUTE, "Push", None,
                 "Push all available change sets to the selected path",
                 self._push_to_acb),
            ])
        self.cwd_merge_id.append(self._ui_manager.add_ui_from_string(PATH_TABLE_UI_DESCR))
        self.show_all()
    def _set_action_sensitivities(self):
        sel = self.get_selection().count_selected_rows() == 1
        self._action_group[change_set.UNIQUE_SELECTION].set_sensitive(sel)
        self._action_group[change_set.UNIQUE_SELECTION_NOT_PMIC].set_sensitive(sel and not self._ifce.PM.get_in_progress())
    def _refresh_contents(self):
        res, data, serr = self._ifce.SCM.get_path_table_data()
        if res == cmd_result.OK and data:
            self.set_contents(data)
        else:
            self.set_contents([])
        gutils.MapManagedTableView._refresh_contents(self)
    def get_selected_path_alias(self):
        data = self.get_selected_data([0])
        if len(data):
            return str(data[0][0])
        else:
            return ""
    def get_selected_path(self):
        data = self.get_selected_data([1])
        if len(data):
            return str(data[0][0])
        else:
            return ""
    def _view_incoming_acb(self, action):
        path = self.get_selected_path()
        self._show_busy()
        dialog = IncomingCSDialog(self._ifce, path)
        self._unshow_busy()
        dialog.show()
    def _view_outgoing_acb(self, action):
        path = self.get_selected_path()
        self._show_busy()
        dialog = OutgoingCSDialog(self._ifce, path)
        self._unshow_busy()
        dialog.show()
    def _pull_from_acb(self, action):
        path = self.get_selected_path()
        self._show_busy()
        result = self._ifce.SCM.do_pull_from(source=path)
        self._unshow_busy()
        self._report_any_problems(result)
    def _push_to_acb(self, action):
        path = self.get_selected_path()
        self._show_busy()
        result = self._ifce.SCM.do_push_to(path=path)
        self._unshow_busy()
        self._report_any_problems(result)


class PathCSTableView(change_set.ChangeSetTableView):
    def __init__(self, ifce, get_data, path=None, sel_mode=gtk.SELECTION_SINGLE, busy_indicator=None):
        ptype = change_set.PrecisType(change_set.LOG_TABLE_PRECIS_DESCR, get_data)
        change_set.ChangeSetTableView.__init__(self, ifce, ptype, sel_mode=sel_mode,
            busy_indicator=busy_indicator)
        self._action_group[change_set.UNIQUE_SELECTION_NOT_PMIC].get_action("cs_update_ws_to").set_visible(False)
        self._action_group[change_set.UNIQUE_SELECTION_NOT_PMIC].get_action("cs_merge_ws_with").set_visible(False)
        self.set_size_request(640, 160)

class IncomingParentsTableView(PathCSTableView):
    def __init__(self, ifce, rev, path=None, sel_mode=gtk.SELECTION_SINGLE, busy_indicator=None):
        self._path = path
        self._rev = rev
        PathCSTableView.__init__(self, ifce=ifce, get_data=self.get_table_data,
            path=path, sel_mode=sel_mode, busy_indicator=busy_indicator)
    def _view_cs_summary_acb(self, action):
        rev = self.get_selected_change_set()
        self._show_busy()
        dialog = IncomingCSSummaryDialog(self._ifce, rev, self._path)
        self._unshow_busy()
        dialog.show()
    def get_table_data(self):
        return self._ifce.SCM.get_incoming_parents_table_data(self._rev, self._path)

class IncomingFileTreeStore(file_tree.FileTreeStore):
    def __init__(self, ifce, rev, path):
        self._rev = rev
        self._ifce = ifce
        self._path = path
        row_data = apply(file_tree.FileTreeRowData, self._ifce.SCM.get_status_row_data())
        file_tree.FileTreeStore.__init__(self, show_hidden=True, row_data=row_data)
        self.repopulate()
    def update(self, fsobj_iter=None):
        res, files, dummy = self._ifce.SCM.get_incoming_change_set_files(self._rev, self._path)
        if res == 0:
            for file_name, status, extra_info in files:
                self.find_or_insert_file(file_name, file_status=status, extra_info=extra_info)
    def repopulate(self):
        self.clear()
        self.update()

INCOMING_CS_FILES_UI_DESCR = \
'''
<ui>
  <popup name="files_popup">
    <placeholder name="selection"/>
    <separator/>
    <placeholder name="no_selection"/>
      <menuitem action="incoming_diff_files_all"/>
    <separator/>
  </popup>
</ui>
'''

class IncomingFileTreeView(file_tree.FileTreeView):
    def __init__(self, ifce, rev, path, busy_indicator, tooltips=None):
        self._ifce = ifce
        self._rev = rev
        self._path = path
        self.model = IncomingFileTreeStore(ifce, rev, path)
        file_tree.FileTreeView.__init__(self, model=self.model, busy_indicator=busy_indicator,
            tooltips=tooltips, auto_refresh=False, show_status=True)
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.set_headers_visible(False)
        self._action_group[file_tree.NO_SELECTION].add_actions(
            [
                ("incoming_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 "Display the diff for all changes", self._diff_all_files_acb),
            ])
        self._action_group[file_tree.SELECTION_INDIFFERENT].set_visible(False)
        self.scm_change_merge_id = self._ui_manager.add_ui_from_string(INCOMING_CS_FILES_UI_DESCR)
        self.expand_all()
    def _diff_all_files_acb(self, action=None):
        parent = self._get_gtk_window()
        self._show_busy()
        dialog = diff.IncomingDiffTextDialog(parent=parent, ifce=self._ifce,
                                     rev=self._rev, path=self._path, modal=False)
        self._unshow_busy()
        dialog.show()

class IncomingCSSummaryDialog(change_set.ChangeSetSummaryDialog):
    def __init__(self, ifce, rev, path, parent=None):
        self._path = path
        change_set.ChangeSetSummaryDialog.__init__(self, ifce=ifce, rev=rev, parent=parent)
        self.set_title("gwsmg: Change Set: %s : %s" % (rev, path))
    def get_change_set_summary(self):
        return self._ifce.SCM.get_incoming_change_set_summary(self._rev, self._path)
    def get_file_tree_view(self):
        return IncomingFileTreeView(self._ifce, self._rev, self._path, busy_indicator=self.get_busy_indicator())
    def get_parents_view(self):
        return IncomingParentsTableView(self._ifce, self._rev, self._path)

INCOMING_TABLE_UI_DESCR = \
'''
<ui>
  <popup name="table_popup">
    <placeholder name="top">
      <menuitem action="cs_pull_to"/>
    </placeholder>
    <separator/>
    <placeholder name="middle">
    </placeholder>
    <separator/>
    <placeholder name="bottom"/>
  </popup>
</ui>
'''

class IncomingTableView(PathCSTableView):
    def __init__(self, ifce, get_data, path=None, sel_mode=gtk.SELECTION_SINGLE, busy_indicator=None):
        self._path = path
        PathCSTableView.__init__(self, ifce=ifce, get_data=get_data, path=path,
            sel_mode=sel_mode, busy_indicator=busy_indicator)
        self._action_group[change_set.UNIQUE_SELECTION].add_actions(
            [
                ("cs_pull_to", gtk.STOCK_EXECUTE, "Pull To", None,
                 "Pull up to the selected change set", self._pull_to_cs_acb),
            ])
        self.cwd_merge_id.append(self._ui_manager.add_ui_from_string(INCOMING_TABLE_UI_DESCR))
    def _pull_to_cs_acb(self, action):
        rev = self.get_selected_change_set()
        self._show_busy()
        self._ifce.SCM.do_pull_from(rev=rev, source=self._path)
        self._refresh_contents()
        self._unshow_busy()
    def _view_cs_summary_acb(self, action):
        rev = self.get_selected_change_set()
        self._show_busy()
        dialog = IncomingCSSummaryDialog(self._ifce, rev, self._path)
        self._unshow_busy()
        dialog.show()

OUTGOING_TABLE_UI_DESCR = \
'''
<ui>
  <popup name="table_popup">
    <placeholder name="top">
      <menuitem action="cs_push_to"/>
    </placeholder>
    <separator/>
    <placeholder name="middle">
    </placeholder>
    <separator/>
    <placeholder name="bottom"/>
  </popup>
</ui>
'''

class OutgoingTableView(PathCSTableView):
    def __init__(self, ifce, get_data, path=None, sel_mode=gtk.SELECTION_SINGLE, busy_indicator=None):
        self._path = path
        PathCSTableView.__init__(self, ifce=ifce, get_data=get_data, path=path,
            sel_mode=sel_mode, busy_indicator=busy_indicator)
        self._action_group[change_set.UNIQUE_SELECTION_NOT_PMIC].add_actions(
            [
                ("cs_push_to", gtk.STOCK_EXECUTE, "Push To", None,
                 "Push up to the selected change set", self._push_to_cs_acb),
            ])
        self.cwd_merge_id.append(self._ui_manager.add_ui_from_string(OUTGOING_TABLE_UI_DESCR))
    def _push_to_cs_acb(self, action):
        rev = self.get_selected_change_set()
        self._show_busy()
        self._ifce.SCM.do_push_to(rev=rev, path=self._path)
        self._refresh_contents()
        self._unshow_busy()

class PathCSDialog(gtk.Dialog, gutils.BusyIndicator, gutils.BusyIndicatorUser):
    def __init__(self, ifce, get_data, title, path=None, table=PathCSTableView, parent=None):
        self._path = path
        self._ifce = ifce
        gtk.Dialog.__init__(self, title="gwsmg: %s: %s" % (title, path), parent=parent,
                            flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
                           )
        gutils.BusyIndicator.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, self)
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        self._view = table(ifce=ifce, get_data=get_data, path=path,
            busy_indicator=self.get_busy_indicator())
        self.vbox.pack_start(gutils.wrap_in_scrolled_window(self._view))
        self.show_all()
        self._view.get_selection().unselect_all()
        self.connect("response", self._close_cb)
    def _close_cb(self, dialog, response_id):
        self.destroy()

class IncomingCSDialog(PathCSDialog):
    def __init__(self, ifce, path):
        PathCSDialog.__init__(self, ifce=ifce, get_data=self.get_data, path=path,
            title="Incoming", table=IncomingTableView)
    def get_data(self):
        return self._ifce.SCM.get_incoming_table_data(self._path)

class OutgoingCSDialog(PathCSDialog):
    def __init__(self, ifce, path):
        PathCSDialog.__init__(self, ifce=ifce, get_data=self.get_data, path=path,
            title="Outgoing", table=OutgoingTableView)
    def get_data(self):
        return self._ifce.SCM.get_outgoing_table_data(self._path)

class PathSelectTableView(gutils.TableView, cmd_result.ProblemReporter):
    def __init__(self, ifce):
        self._ifce = ifce
        cmd_result.ProblemReporter.__init__(self)
        gutils.TableView.__init__(self, descr=PATH_TABLE_PRECIS_DESCR, sel_mode=gtk.SELECTION_SINGLE)
        self.populate()
        self.show_all()
    def populate(self):
        res, data, serr = self._ifce.SCM.get_path_table_data()
        if res == cmd_result.OK and data:
            self.set_contents(data)
        else:
            self.set_contents([])
    def get_selected_path_alias(self):
        data = self.get_selected_data([0])
        if len(data):
            return data[0][0]
        else:
            return ""
    def get_selected_path(self):
        data = self.get_selected_data([1])
        if len(data):
            return data[0][0]
        else:
            return ""

class PullDialog(gtk.Dialog, gutils.BusyIndicator, gutils.BusyIndicatorUser):
    def __init__(self, ifce, parent=None):
        self._ifce = ifce
        gutils.BusyIndicator.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, self)
        gtk.Dialog.__init__(self, title="gwsmg: Pull From (Up To)", parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        hbox = gtk.HBox()
        self.path_view = PathSelectTableView(ifce=ifce)
        self.path_view.get_selection().connect("changed", self._selection_cb)
        hbox.pack_start(gutils.wrap_in_scrolled_window(self.path_view))
        self._select_button = gtk.Button(label="_Select")
        self._select_button.connect("clicked", self._select_cb)
        hbox.pack_start(self._select_button, expand=False, fill=False)
        self.vbox.pack_start(hbox)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Path:"))
        self._path = gutils.EntryWithHistory()
        self._path.set_width_chars(32)
        self._path.set_text("default")
        self._path.connect("activate", self._path_cb)
        hbox.pack_start(self._path, expand=True, fill=True)
        self._browse_path_button = gtk.Button(label="_Browse")
        self._browse_path_button.connect("clicked", self._browse_path_cb)
        hbox.pack_start(self._browse_path_button, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        hbox = gtk.HBox()
        self._upto_toggle = gtk.CheckButton(label="Up To Revision:")
        self._upto_toggle.connect("toggled", self._toggle_cb)
        hbox.pack_start(self._upto_toggle, expand=False, fill=False)
        self._revision = gutils.EntryWithHistory()
        self._revision.set_width_chars(32)
        self._revision.set_sensitive(self._upto_toggle.get_active())
        self._revision.connect("activate", self._revision_cb)
        hbox.pack_start(self._revision, expand=True, fill=True)
        self._incoming_button = gtk.Button(label="_Incoming")
        self._incoming_button.connect("clicked", self._incoming_cb)
        self._incoming_button.set_sensitive(self._upto_toggle.get_active())
        hbox.pack_start(self._incoming_button, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        self.show_all()
        self.path_view.get_selection().unselect_all()
    def _selection_cb(self, selection=None):
        self._select_button.set_sensitive(selection.count_selected_rows())
    def _select_cb(self, button=None):
        path = self.path_view.get_selected_path_alias()
        self._path.set_text(path)
    def _toggle_cb(self, toggle=None):
        self._revision.set_sensitive(self._upto_toggle.get_active())
        self._incoming_button.set_sensitive(self._upto_toggle.get_active())
    def _path_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def _revision_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def _browse_path_cb(self, button=None):
        dirname = gutils.ask_dir_name("gwsmhg: Browse for Path", existing=True, parent=self)
        if dirname:
            self._path.set_text(dirname)
    def _get_incoming_data(self):
        return self._ifce.SCM.get_incoming_table_data(self.get_path())
    def _incoming_cb(self, button=None):
        self._show_busy()
        title = "Choose Revision"
        ptype = change_set.PrecisType(descr=change_set.LOG_TABLE_PRECIS_DESCR,
            get_data=self._get_incoming_data)
        dialog = change_set.SelectDialog(ifce=self._ifce, ptype=ptype, title=title, parent=self)
        self._unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self._revision.set_text(dialog.get_change_set())
        dialog.destroy()
    def get_path(self):
        path = os.path.expanduser(self._path.get_text())
        if path:
            return path
        else:
            return None
    def get_revision(self):
        revision = self._revision.get_text()
        if revision:
            return revision
        else:
            return None

