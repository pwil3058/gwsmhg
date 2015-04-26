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
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import gtk, gobject, os, collections
from gwsmhg_pkg import dialogue, gutils, cmd_result, change_set, icons
from gwsmhg_pkg import file_tree, diff, ws_event, ifce, utils, actions, ws_actions, table
from gwsmhg_pkg import tlview

class PathTableView(table.MapManagedTableView):
    class Model(tlview.NamedListStore):
        Row = collections.namedtuple('Row', [_('Alias'), _('Path')])
        types = Row(
            Alias=gobject.TYPE_STRING,
            Path=gobject.TYPE_STRING,
        )
    specification = tlview.ViewSpec(
        properties={
            'enable-grid-lines' : False,
            'reorderable' : False,
            'rules_hint' : False,
            'headers-visible' : True,
        },
        selection_mode=gtk.SELECTION_SINGLE,
        columns=[
            tlview.ColumnSpec(
                title=_('Alias'),
                properties={'expand': False, 'resizable' : True},
                cells=[
                    tlview.CellSpec(
                        cell_renderer_spec=tlview.CellRendererSpec(
                            cell_renderer=gtk.CellRendererText,
                            expand=False,
                            start=True
                        ),
                        properties={'editable' : False},
                        cell_data_function_spec=None,
                        attributes = {'text' : Model.col_index(_('Alias'))}
                    ),
                ],
            ),
            tlview.ColumnSpec(
                title=_('Path'),
                properties={'expand': False, 'resizable' : True},
                cells=[
                    tlview.CellSpec(
                        cell_renderer_spec=tlview.CellRendererSpec(
                            cell_renderer=gtk.CellRendererText,
                            expand=False,
                            start=True
                        ),
                        properties={'editable' : False},
                        cell_data_function_spec=None,
                        attributes = {'text' : Model.col_index(_('Path'))}
                    ),
                ],
            ),
        ]
    )
    PopUp = "/table_popup"
    UI_DESCR = \
        '''
        <ui>
          <popup name="table_popup">
            <menuitem action="remote_repo_mgmt"/>
            <separator/>
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
    def __init__(self, busy_indicator=None):
        table.MapManagedTableView.__init__(self, busy_indicator=busy_indicator)
        self.add_notification_cb(ws_event.REPO_HGRC, self.refresh_contents_if_mapped)
        self.show_all()
    def populate_action_groups(self):
        table.MapManagedTableView.populate_action_groups(self)
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_UNIQUE].add_actions(
            [
                ("remote_repo_mgmt", gtk.STOCK_EXECUTE, _('Manage'), None,
                 _('Open remote management for selected repository'),
                 self._manage_repo_acb),
                ("view_incoming_from_path", gtk.STOCK_INFO, _('Incoming'), None,
                 _('View the incoming change sets available to pull from the selected path'),
                 self._view_incoming_acb),
                ("view_outgoing_to_path", gtk.STOCK_INFO, _('Outgoing'), None,
                 _('View the outgoing change sets ready to push to the selected path'),
                 self._view_outgoing_acb),
                ("pull_from_path", gtk.STOCK_EXECUTE, _('Pull'), None,
                 _('Pull all available change sets from the selected path'),
                 self._pull_from_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + ws_actions.AC_NOT_PMIC + actions.AC_SELN_UNIQUE].add_actions(
            [
                ("push_to_path", gtk.STOCK_EXECUTE, _('Push'), None,
                 _('Push all available change sets to the selected path'),
                 self._push_to_acb),
            ])
    def _fetch_contents(self):
        return ifce.SCM.get_path_table_data()
    def get_selected_path_alias(self):
        return self.get_selected_key_by_label(_('Alias'))
    def get_selected_path(self):
        return self.get_selected_key_by_label(_('Path'))
    def _manage_repo_acb(self, _action):
        alias, path = self.get_selected_data()[0]
        self.show_busy()
        dialog = RemoteRepoManagementDialog(path, alias)
        self.unshow_busy()
        dialog.show()
    def _view_incoming_acb(self, _action):
        path = self.get_selected_path()
        self.show_busy()
        dialog = IncomingCSDialog(path)
        self.unshow_busy()
        dialog.show()
    def _view_outgoing_acb(self, _action):
        path = self.get_selected_path()
        self.show_busy()
        dialog = OutgoingCSDialog(path)
        self.unshow_busy()
        dialog.show()
    def _pull_from_acb(self, _action):
        path = self.get_selected_path()
        self.show_busy()
        result = ifce.SCM.do_pull_from(source=path)
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def _push_to_acb(self, _action):
        path = self.get_selected_path()
        self.show_busy()
        result = ifce.SCM.do_push_to(path=path)
        self.unshow_busy()
        dialogue.report_any_problems(result)

class IncomingParentsTable(change_set.ChangeSetTable):
    class View(change_set.ChangeSetTable.View):
        def __init__(self, busy_indicator=None, size_req=None, rev=None, path=None):
            self._path = path
            self._rev = rev
            change_set.ChangeSetTable.View.__init__(self, busy_indicator=busy_indicator, size_req=size_req)
        def _fetch_contents(self):
            try:
                return ifce.SCM.get_incoming_parents_table_data(self._rev, self._path)
            except cmd_result.Failure as failure:
                dialogue.report_failure(failure)
                return []
    def __init__(self, rev, path=None, busy_indicator=None):
        self._path = path
        self._rev = rev
        change_set.ChangeSetTable.__init__(self, busy_indicator=busy_indicator,
                                           scroll_bar=False, rev=rev, path=path)
    def _view_cs_summary_acb(self, _action):
        rev = self.get_selected_key()
        self.show_busy()
        # a parent might be local so let's check
        if ifce.SCM.get_is_incoming(rev, self._path):
            dialog = IncomingCSSummaryDialog(rev, self._path)
        else:
            dialog = change_set.ChangeSetSummaryDialog(rev)
        self.unshow_busy()
        dialog.show()

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

class IncomingFileTreeView(file_tree.Tree):
    AUTO_EXPAND = True
    def __init__(self, rev, path, busy_indicator):
        self._rev = rev
        self._path = path
        file_tree.Tree.__init__(self, busy_indicator=busy_indicator, show_status=True, show_hidden=True)
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.set_headers_visible(False)
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_NONE].add_actions(
            [
                ("incoming_diff_files_all", icons.STOCK_DIFF, "_Diff", None,
                 _('Display the diff for all changes'), self._diff_all_files_acb),
            ])
        self.set_visibility_for_condns(actions.AC_DONT_CARE, False)
        self.scm_change_merge_id = self.ui_manager.add_ui_from_string(INCOMING_CS_FILES_UI_DESCR)
    def _diff_all_files_acb(self, _action=None):
        parent = dialogue.main_window
        self.show_busy()
        dialog = diff.IncomingDiffTextDialog(parent=parent, rev=self._rev, path=self._path)
        self.unshow_busy()
        dialog.show()
    def _get_file_db(self):
        return ifce.SCM.get_incoming_change_set_files_db(self._rev)

class IncomingCSSummaryDialog(change_set.ChangeSetSummaryDialog):
    def __init__(self, rev, path, parent=None):
        self._path = path
        change_set.ChangeSetSummaryDialog.__init__(self, rev=rev, parent=parent)
        self.set_title(_('gwsmg: Change Set: %s : %s') % (rev, path))
    def get_change_set_summary(self):
        return ifce.SCM.get_incoming_change_set_summary(self._rev, self._path)
    def get_file_tree_view(self):
        return IncomingFileTreeView(self._rev, self._path, busy_indicator=self)
    def get_parents_view(self):
        return IncomingParentsTable(self._rev, self._path, busy_indicator=self)

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

class IncomingTable(change_set.SearchableChangeSetTable):
    class View(change_set.SearchableChangeSetTable.View):
        def __init__(self, path, busy_indicator=None, size_req=None):
            self._path = path
            change_set.SearchableChangeSetTable.View.__init__(self, busy_indicator=busy_indicator, size_req=size_req)
        def _fetch_contents(self):
            try:
                return ifce.SCM.get_incoming_table_data(self._path)
            except cmd_result.Failure as failure:
                dialogue.report_failure(failure)
                return []
    def __init__(self, path=None, busy_indicator=None):
        self._path = path
        change_set.SearchableChangeSetTable.__init__(self, busy_indicator=busy_indicator,
                                                     size_req = (640, 120),
                                                     prefix = _('Incoming'), rev=False, path=path)
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_UNIQUE].add_actions(
           [
                ("cs_pull_to", gtk.STOCK_EXECUTE, _('Pull To'), None,
                 _('Pull up to the selected change set'), self._pull_to_cs_acb),
            ])
        self.ui_manager.add_ui_from_string(INCOMING_TABLE_UI_DESCR)
        self.ui_manager.add_ui_from_string(change_set.CS_TABLE_REFRESH_UI_DESCR)
    def _fetch_rev(self, revarg):
        return ifce.SCM.get_incoming_rev(revarg)
    def _pull_to_cs_acb(self, _action):
        rev = self.get_selected_key_by_label(_('Node'))
        self.show_busy()
        ifce.SCM.do_pull_from(rev=rev, source=self._path)
        self.refresh_contents()
        self.unshow_busy()
    def _view_cs_summary_acb(self, _action):
        rev = self.get_selected_key_by_label(_('Node'))
        self.show_busy()
        dialog = IncomingCSSummaryDialog(rev, self._path)
        self.unshow_busy()
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

class OutgoingTable(change_set.SearchableChangeSetTable):
    class View(change_set.SearchableChangeSetTable.View):
        def __init__(self, busy_indicator=None, size_req=None, path=None):
            self._path = path
            change_set.SearchableChangeSetTable.View.__init__(self, busy_indicator=busy_indicator, size_req=size_req)
        def _fetch_contents(self):
            try:
                return ifce.SCM.get_outgoing_table_data(self._path)
            except cmd_result.Failure as failure:
                dialogue.report_failure(failure)
                return []
    def __init__(self, path=None, busy_indicator=None):
        self._path = path
        change_set.SearchableChangeSetTable.__init__(self, busy_indicator=busy_indicator,
                                                     size_req = (640, 120),
                                                     prefix = _('Outgoing'), path=path)
        self.action_groups[ws_actions.AC_IN_REPO + ws_actions.AC_NOT_PMIC + actions.AC_SELN_UNIQUE].add_actions(
            [
                ("cs_push_to", gtk.STOCK_EXECUTE, _('Push To'), None,
                 _('Push up to the selected change set'), self._push_to_cs_acb),
            ])
        self.ui_manager.add_ui_from_string(OUTGOING_TABLE_UI_DESCR)
        self.ui_manager.add_ui_from_string(change_set.CS_TABLE_REFRESH_UI_DESCR)
    def _fetch_rev(self, revarg):
        return ifce.SCM.get_outgoing_rev(revarg)
    def _push_to_cs_acb(self, _action):
        rev = self.get_selected_key()
        self.show_busy()
        ifce.SCM.do_push_to(rev=rev, path=self._path)
        self.refresh_contents()
        self.unshow_busy()

class PathCSDialog(dialogue.AmodalDialog):
    def __init__(self, title, path=None, table_type=None, parent=None):
        dialogue.AmodalDialog.__init__(self, title=title, parent=parent,
                                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                       buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE))
        self._path = path
        self.set_title('gwsmg: %s(%s): %s' % (title, utils.cwd_rel_home(), utils.path_rel_home(path)))
        self._table = table_type( path=path, busy_indicator=self)
        self.vbox.pack_start(self._table)
        self.show_all()
        self._table.seln.unselect_all()
        self.connect("response", self._close_cb)
    def _close_cb(self, dialog, response_id):
        self.destroy()

class IncomingCSDialog(PathCSDialog):
    def __init__(self, path):
        PathCSDialog.__init__(self, path=path, title=_('Incoming To'),
                              table_type=IncomingTable)

class OutgoingCSDialog(PathCSDialog):
    def __init__(self, path):
        PathCSDialog.__init__(self, path=path, title=_('Outgoing From'),
                              table_type=OutgoingTable)

class PathSelectTableView(table.TableView):
    def __init__(self, size_req=(640, 240), busy_indicator=None):
        table.TableView.__init__(self, model_descr=PATH_PRECIS_MODEL_DESCR,
                                             table_descr=PATH_PRECIS_TABLE_DESCR,
                                             size_req=size_req, busy_indicator=busy_indicator)
        self.set_contents()
        self.show_all()
    def _fetch_contents(self):
        return ifce.SCM.get_path_table_data()
    def get_selected_path_alias(self):
        return self.get_selected_key_by_label(_('Alias'))
    def get_selected_path(self):
        return self.get_selected_key_by_label(_('Path'))

class PullDialog(dialogue.Dialog):
    def __init__(self, parent=None):
        dialogue.Dialog.__init__(self, title=_('gwsmg: Pull From (Up To)'), parent=parent,
                                 flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                                 buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                          gtk.STOCK_OK, gtk.RESPONSE_OK)
                                )
        hbox = gtk.HBox()
        self.path_table = PathSelectTableView()
        self.path_table.seln.connect("changed", self._selection_cb)
        hbox.pack_start(self.path_table)
        self._select_button = gtk.Button(label=_('_Select'))
        self._select_button.connect("clicked", self._select_cb)
        hbox.pack_start(self._select_button, expand=False, fill=False)
        self.vbox.pack_start(hbox)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(_('Path:')))
        self._path = gutils.EntryWithHistory()
        self._path.set_width_chars(32)
        self._path.set_text("default")
        self._path.connect("activate", self._path_cb)
        hbox.pack_start(self._path, expand=True, fill=True)
        self._browse_path_button = gtk.Button(label=_('_Browse'))
        self._browse_path_button.connect("clicked", self._browse_path_cb)
        hbox.pack_start(self._browse_path_button, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        hbox = gtk.HBox()
        self._upto_toggle = gtk.CheckButton(label=_('Up To Revision:'))
        self._upto_toggle.connect("toggled", self._toggle_cb)
        hbox.pack_start(self._upto_toggle, expand=False, fill=False)
        self._revision = gutils.EntryWithHistory()
        self._revision.set_width_chars(32)
        self._revision.set_sensitive(self._upto_toggle.get_active())
        self._revision.connect("activate", self._revision_cb)
        hbox.pack_start(self._revision, expand=True, fill=True)
        self._incoming_button = gtk.Button(label=_('_Incoming'))
        self._incoming_button.connect("clicked", self._incoming_cb)
        self._incoming_button.set_sensitive(self._upto_toggle.get_active())
        hbox.pack_start(self._incoming_button, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        self.show_all()
        self.path_table.seln.unselect_all()
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
        dirname = dialogue.ask_dir_name(_('gwsmhg: Browse for Path'), existing=True, parent=self)
        if dirname:
            self._path.set_text(dirname)
    def _get_incoming_data(self):
        try:
            return ifce.SCM.get_incoming_table_data(self.get_path())
        except cmd_result.Failure as failure:
            dialogue.report_failure(failure)
            return []
    def _incoming_cb(self, button=None):
        self.show_busy()
        title = _('Choose Revision')
        dialog = change_set.SelectDialog(title=title, get_data=self._get_incoming_data, parent=self)
        self.unshow_busy()
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

class RemoteRepoManagementWidget(gtk.VBox, ws_actions.AGandUIManager, dialogue.BusyIndicatorUser):
    UI_DESCR = \
        '''
        <ui>
          <menubar name="remote_menubar">
          </menubar>
          <toolbar name="remote_toolbar">
            <toolitem name="Refresh" action="path_refresh_remote"/>
            <toolitem name="Push" action="path_remote_push"/>
            <toolitem name="Pull" action="path_remote_pull"/>
          </toolbar>
        </ui>
        '''
    def __init__(self, path, alias, busy_indicator=None):
        gtk.VBox.__init__(self)
        ws_actions.AGandUIManager.__init__(self)
        dialogue.BusyIndicatorUser.__init__(self, busy_indicator)
        self._path = path
        hbox = gtk.HBox()
        hbox.pack_start(gutils.LabelledText(label=_('Path:'), text=path, min_chars=52))
        hbox.pack_start(gutils.LabelledText(label=_('Alias:'), text=alias, min_chars=12))
        self.pack_start(hbox, expand=False)
        self._tool_bar = self.ui_manager.get_widget("/remote_toolbar")
        self._tool_bar.set_style(gtk.TOOLBAR_BOTH)
        self.pack_start(self._tool_bar, expand=False)
        self._incoming = IncomingTable(path=path, busy_indicator=busy_indicator)
        self._outgoing = OutgoingTable(path=path, busy_indicator=busy_indicator)
        vpane = gtk.VPaned()
        vpane.add1(self._incoming)
        vpane.add2(self._outgoing)
        self.pack_start(vpane)
    def populate_action_groups(self):
        self.action_groups[ws_actions.AC_IN_REPO].add_actions(
            [
                ("path_refresh_remote", gtk.STOCK_REFRESH, _('_Refresh'), None,
                 _('Refresh remote repository date'), self._refresh_data_acb),
                ("path_remote_pull", icons.STOCK_PULL, _('Pull'), "",
                 _('Pull all available changes from  remote repository'),
                 self._pull_repo_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + ws_actions.AC_NOT_PMIC].add_actions(
            [
                ("path_remote_push", icons.STOCK_PUSH, _('Push'), '',
                 _('Push all available changes to remote repository'),
                 self._push_repo_acb),
            ])
    def _refresh_data_acb(self, _action=None):
        self._incoming.refresh_contents()
        self._outgoing.refresh_contents()
    def _pull_repo_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_pull_from(source=self._path)
        self._refresh_data_acb()
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def _push_repo_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_push_to(path=self._path)
        self._refresh_data_acb()
        self.unshow_busy()
        dialogue.report_any_problems(result)

class RemoteRepoManagementDialog(dialogue.AmodalDialog):
    def __init__(self, path, alias, parent=None):
        dialogue.AmodalDialog.__init__(self, parent=parent,
                                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                       buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE))
        self._path = path
        self.set_title(_('gwsmg: Remote(%s): %s (%s)') % (utils.cwd_rel_home(), utils.path_rel_home(path), alias))
        self._manager = RemoteRepoManagementWidget(path=path, alias=alias, busy_indicator=self)
        self.vbox.pack_start(self._manager)
        self.show_all()
        self.connect("response", self._close_cb)
    def _close_cb(self, dialog, response_id):
        self.destroy()
