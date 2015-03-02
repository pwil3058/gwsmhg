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
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import collections, gtk, gobject, os

from gwsmhg_pkg import ifce, cmd_result, gutils, utils, icons, file_tree, diff
from gwsmhg_pkg import text_edit, ws_event, dialogue, table, actions, ws_actions
from gwsmhg_pkg import tlview

CSRow = collections.namedtuple('CSRow', [_('Rev'), _('Node'), _('Age'), _('Tags'), _('Branches'), _('Author'), _('Description')])

LOG_MODEL_DESCR = CSRow(
    Rev=gobject.TYPE_INT,
    Node=gobject.TYPE_STRING,
    Age=gobject.TYPE_STRING,
    Tags=gobject.TYPE_STRING,
    Branches=gobject.TYPE_STRING,
    Author=gobject.TYPE_STRING,
    Description=gobject.TYPE_STRING,
)

def cs_table_column(model_descr, name):
    return tlview.Column(
        title=name,
        properties={'expand' : False, 'resizable' : True},
        cells=[
            tlview.Cell(
                creator=tlview.CellCreator(
                    function=gtk.CellRendererText,
                    expand=False,
                    start=True
                ),
                properties={'editable' : False},
                renderer=None,
                attributes={'text' : tlview.model_col(model_descr, name)}
            )
        ]
    )

import re
_BASE_ENTITIES = { '&':'amp', '<':'lt', '>':'gt' }
_BASE_ENTITIES_RE = re.compile("([<>&])")
def safe_escape(string):
    return _BASE_ENTITIES_RE.sub(
        lambda m: '&%s;' % _BASE_ENTITIES[m.group(0)[0]], string)

_MARKUP_COLOURS = {_('Tags') : 'yellow', _('Branches') : 'cyan'}

def cs_description_crf(_column, cell, model, model_iter, user_data):
    mcols, colours = user_data
    markup = safe_escape(model.get_value(model_iter, mcols[0]))
    extras = mcols[1:]
    for index in range(len(extras)):
        if extras[index]:
            tags = model.get_value(model_iter, extras[index])
            for tag in tags.split():
                markup += ' <span background="%s"><b>%s</b></span>' % (colours[index], tag)
    cell.set_property('markup', markup)

def cs_description_column(model_descr, extras):
    mcols = tuple(tlview.model_col(model_descr, x) for x in (_('Description'),) + extras)
    cols = tuple(_MARKUP_COLOURS[x] for x in extras)
    return tlview.Column(
        title=_('Description'),
        properties={'expand' : False, 'resizable' : True},
        cells=[
            tlview.Cell(
                creator=tlview.CellCreator(
                    function=gtk.CellRendererText,
                    expand=False,
                    start=True
                ),
                properties={'editable' : False},
                renderer=tlview.Renderer(
                    function=cs_description_crf,
                    user_data=(mcols, cols)
                ),
                attributes={}
            )
        ]
    )

LOG_TABLE_DESCR = tlview.ViewTemplate(
    properties={
        'enable-grid-lines' : False,
        'reorderable' : False,
        'rules_hint' : False,
        'headers-visible' : True,
    },
    selection_mode=gtk.SELECTION_SINGLE,
    columns=[
        cs_table_column(LOG_MODEL_DESCR, _('Rev')),
        cs_table_column(LOG_MODEL_DESCR, _('Age')),
        cs_description_column(LOG_MODEL_DESCR, (_('Tags'), _('Branches'))),
        cs_table_column(LOG_MODEL_DESCR, _('Author')),
    ]
)

class ChangeSetTable(table.MapManagedTable):
    UI_DESCR = \
        '''
        <ui>
          <popup name="table_popup">
            <placeholder name="top">
              <menuitem action="cs_summary"/>
            </placeholder>
            <separator/>
            <placeholder name="middle"/>
            <separator/>
            <placeholder name="bottom"/>
          </popup>
        </ui>
        '''
    def __init__(self, model_descr = None,
                 table_descr = None, popup='/table_popup',
                 scroll_bar=True, busy_indicator=None, size_req=None):
        if model_descr is None:
            model_descr = LOG_MODEL_DESCR
        if table_descr is None:
            table_descr = LOG_TABLE_DESCR
        table.MapManagedTable.__init__(self, model_descr=model_descr,
                                       table_descr=table_descr, popup=popup,
                                       busy_indicator=busy_indicator,
                                       size_req=size_req,
                                       scroll_bar=scroll_bar)
        self.add_notification_cb(ws_event.REPO_MOD|ws_event.PATCH_CHANGES, self.refresh_contents_if_mapped)
    def populate_action_groups(self):
        table.MapManagedTable.populate_action_groups(self)
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_UNIQUE].add_actions(
            [
                ("cs_summary", gtk.STOCK_INFO, _('Summary'), None,
                 _('View a summary of the selected change set'), self._view_cs_summary_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + ws_actions.AC_NOT_PMIC + actions.AC_SELN_UNIQUE].add_actions(
            [
                ("cs_update_ws_to", gtk.STOCK_JUMP_TO, _('Update To'), None,
                 _('Update the work space to the selected change set'),
                 self._update_ws_to_cs_acb),
                ("cs_merge_ws_with", icons.STOCK_MERGE, _('Merge With'), None,
                 _('Merge the work space with the selected change set'),
                 self._merge_ws_with_cs_acb),
                ("cs_backout", icons.STOCK_BACKOUT, _('Backout'), None,
                 _('Backout the selected change set'),
                 self._backout_cs_acb),
                ("cs_tag_selected", icons.STOCK_TAG, _('Tag'), None,
                 _('Tag the selected change set'),
                 self._tag_cs_acb),
            ])
    def _view_cs_summary_acb(self, _):
        rev = self.get_selected_key()
        self.show_busy()
        dialog = ChangeSetSummaryDialog(rev)
        self.unshow_busy()
        dialog.show()
    def _update_ws_to_cs_acb(self, _action):
        rev = str(self.get_selected_key())
        self.show_busy()
        result = ifce.SCM.do_update_workspace(rev=rev)
        self.unshow_busy()
        if result[0] & cmd_result.SUGGEST_MERGE_OR_DISCARD:
            question = os.linesep.join(result[1:])
            ans = dialogue.ask_merge_discard_or_cancel(question, result[0])
            if ans == dialogue.RESPONSE_DISCARD:
                self.show_busy()
                result = ifce.SCM.do_update_workspace(rev=rev, discard=True)
                self.unshow_busy()
                dialogue.report_any_problems(result)
            elif ans == dialogue.RESPONSE_MERGE:
                self.show_busy()
                result = ifce.SCM.do_merge_workspace(rev=rev, force=False)
                self.unshow_busy()
                if result[0] & cmd_result.SUGGEST_FORCE:
                    if dialogue.ask_force_or_cancel(result) == dialogue.RESPONSE_FORCE:
                        self.show_busy()
                        result = ifce.SCM.do_merge_workspace(rev=rev, force=True)
                        self.unshow_busy()
                        dialogue.report_any_problems(result)
                else:
                    dialogue.report_any_problems(result)
        else:
            dialogue.report_any_problems(result)
    def _merge_ws_with_cs_acb(self, _action):
        rev = str(self.get_selected_key())
        self.show_busy()
        result = ifce.SCM.do_merge_workspace(rev=rev)
        self.unshow_busy()
        if result[0] & cmd_result.SUGGEST_FORCE:
            if dialogue.ask_force_or_cancel(result) == dialogue.RESPONSE_FORCE:
                self.show_busy()
                result = ifce.SCM.do_merge_workspace(rev=rev, force=True)
                self.unshow_busy()
                dialogue.report_any_problems(result)
        else:
            dialogue.report_any_problems(result)
    def _backout_cs_acb(self, _action):
        rev = str(self.get_selected_key())
        descr = self.get_selected_key_by_label(_('Description'))
        self.show_busy()
        BackoutDialog(rev=rev, descr=descr)
        self.unshow_busy()
    def _tag_cs_acb(self, _action=None):
        rev = self.get_selected_key()
        self.show_busy()
        SetTagDialog(rev=str(rev)).run()
        self.unshow_busy()

CS_TABLE_REFRESH_UI_DESCR = \
'''
<ui>
  <popup name="table_popup">
    <placeholder name="top"/>
    <separator/>
    <placeholder name="middle"/>
    <separator/>
    <placeholder name="bottom">
      <menuitem action="table_refresh_contents"/>
    </placeholder>
  </popup>
</ui>
'''

CS_TABLE_EXEC_UI_DESCR = \
'''
<ui>
  <popup name="table_popup">
    <placeholder name="top"/>
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

CS_TABLE_TAG_UI_DESCR = \
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

class HeadsTable(ChangeSetTable):
    def __init__(self, busy_indicator=None, size_req=None):
        ChangeSetTable.__init__(self, busy_indicator=busy_indicator, size_req=size_req)
        self.ui_manager.add_ui_from_string(CS_TABLE_EXEC_UI_DESCR)
        self.ui_manager.add_ui_from_string(CS_TABLE_REFRESH_UI_DESCR)
    def _fetch_contents(self):
        try:
            return ifce.SCM.get_heads_data()
        except cmd_result.Failure as failure:
            dialogue.report_failure(failure)
            return []

class SearchableChangeSetTable(ChangeSetTable):
    def __init__(self, busy_indicator=None, size_req=None, prefix=None, rev=True):
        ChangeSetTable.__init__(self, busy_indicator=busy_indicator, size_req=size_req)
        if rev:
            if prefix:
                self._search = gutils.LabelledEntry(prefix + _(': Find Rev/Tag/Node Id:'))
            else:
                self._search = gutils.LabelledEntry(_('Find Rev/Tag/Node Id:'))
        else:
            if prefix:
                self._search = gutils.LabelledEntry(prefix + _(': Find Tag/Node Id:'))
            else:
                self._search = gutils.LabelledEntry(_('Find Tag/Node Id:'))
        self._search.entry.connect('activate', self._search_entry_cb)
        self.header.lhs.pack_start(self._search, expand=True, fill=True)
    def _search_entry_cb(self, entry):
        text = entry.get_text_and_clear_to_history()
        if not text:
            return
        try:
            self._select_and_scroll_to_rev(int(self._fetch_rev(text)))
        except cmd_result.Failure as failure:
            dialogue.report_failure(failure)
    def _select_and_scroll_to_rev(self, rev):
        self.select_and_scroll_to_row_with_key_value(key=_('Rev'), key_value=rev)
    def _fetch_rev(self, revarg):
        assert True, 'define in child'
        return (self, revarg)

class HistoryTable(SearchableChangeSetTable):
    @staticmethod
    def search_equal_func(model, column, key, model_iter, _data=None):
        text = model.get_labelled_value(model_iter, label=_('Description'))
        return text.find(key) == -1
    def __init__(self, busy_indicator=None, size_req=None):
        SearchableChangeSetTable.__init__(self, busy_indicator=busy_indicator, size_req=size_req)
        self.view.set_search_equal_func(HistoryTable.search_equal_func)
        self._default_max = 8192
        self._current_max = self._default_max
        self.action_groups[ws_actions.AC_IN_REPO].add_actions(
            [
                ('cs_next_tranch', gtk.STOCK_GO_FORWARD, '', None,
                 _('Load the next tranche of change sets'), self._cs_next_tranche_acb),
                ('cs_load_all', gtk.STOCK_GOTO_LAST, '', None,
                 _('Load all of the remaining change sets'), self._cs_load_all_acb),
            ])
        self.ui_manager.add_ui_from_string(CS_TABLE_EXEC_UI_DESCR)
        self.ui_manager.add_ui_from_string(CS_TABLE_REFRESH_UI_DESCR)
        self.ui_manager.add_ui_from_string(CS_TABLE_TAG_UI_DESCR)
        self._button_box = self.action_groups.create_action_button_box(['cs_next_tranch', 'cs_load_all'],
                                                         expand=False)
        self.header.rhs.pack_start(gtk.VSeparator(), expand=True)
        self.header.rhs.pack_end(self._button_box, expand=False)
    def _oldest_loaded_rev(self):
        if len(self.model) == 0:
            return 0
        return int(self.model[-1][self.model.get_col(_('Rev'))])
    def _fetch_rev(self, revarg):
        return ifce.SCM.get_rev(revarg)
    def _fetch_contents(self):
        try:
            return ifce.SCM.get_history_data(maxitems=self._current_max)
        except cmd_result.Failure as failure:
            dialogue.report_failure(failure)
            return []
    def _select_and_scroll_to_rev(self, rev):
        while not self.select_and_scroll_to_row_with_key_value(key=_('Rev'), key_value=rev):
            self._append_contents(torev=rev)
    def _append_contents(self, torev=None):
        self.show_busy()
        oldest_rev = self._oldest_loaded_rev()
        start_rev = oldest_rev - 1
        if start_rev < 0:
            start_rev = 0
        if torev is None:
            count = self._default_max
        else:
            count = start_rev - torev + 1
        self._current_max += count
        data = ifce.SCM.get_history_data(rev=start_rev, maxitems=count)
        self.model.append_contents(data)
        self.view.columns_autosize()
        self._check_button_visibility()
        self.unshow_busy()
    def _check_button_visibility(self):
        if self._oldest_loaded_rev() == 0:
            self._button_box.hide()
            self._button_box.set_no_show_all(True)
            self._current_max = None
        elif self._button_box.get_no_show_all():
            self._button_box.set_no_show_all(False)
            self._button_box.show()
            if self._current_max == None:
                self._current_max = self._default_max
    def reset_contents_if_mapped(self, arg=None):
        self._current_max = self._default_max
        SearchableChangeSetTable.reset_contents_if_mapped(self, arg)
    def _set_contents(self):
        SearchableChangeSetTable._set_contents(self)
        self._check_button_visibility()
    def _cs_next_tranche_acb(self, _action=None):
        self._append_contents()
    def _cs_load_all_acb(self, _action=None):
        self._append_contents(torev=0)

class ParentsTable(ChangeSetTable):
    def __init__(self, rev=None, busy_indicator=None, size_req=None):
        ChangeSetTable.__init__(self, busy_indicator=busy_indicator,
                                size_req=size_req, scroll_bar=False)
        self._rev = rev
        self.add_notification_cb(ws_event.CHANGE_WD, self._checkout_cb)
        if rev is None:
            self.add_notification_cb(ws_event.CHECKOUT, self._checkout_cb)
    def _checkout_cb(self, arg=None):
        self.set_contents()
    def _fetch_contents(self):
        parents = ifce.SCM.get_parents_data(rev=self._rev)
        if parents:
            self.show()
        else:
            self.hide()
        return parents

TagRow = collections.namedtuple('TagRow', [_('Tag'), _('Scope'), _('Rev'), _('Branches'), _('Age'), _('Author'), _('Description')])

TAGS_MODEL_DESCR = TagRow(
    Tag=gobject.TYPE_STRING,
    Scope=gobject.TYPE_STRING,
    Rev=gobject.TYPE_INT,
    Branches=gobject.TYPE_STRING,
    Age=gobject.TYPE_STRING,
    Author=gobject.TYPE_STRING,
    Description=gobject.TYPE_STRING,
)

def cs_tag_crf(_column, cell, model, model_iter, mcols):
    markup = safe_escape(model.get_value(model_iter, mcols[0]))
    local = model.get_value(model_iter, mcols[1])
    markup += ' <span background="yellow"><b>%s</b></span>' % local
    cell.set_property('markup', markup)

def cs_tag_column(model_descr):
    mcols = ( tlview.model_col(model_descr, _('Tag')),
              tlview.model_col(model_descr, _('Scope')),
            )
    return tlview.Column(
        title=_('Tag'),
        properties={'expand' : False, 'resizable' : True},
        cells=[
            tlview.Cell(
                creator=tlview.CellCreator(
                    function=gtk.CellRendererText,
                    expand=False,
                    start=True
                ),
                properties={'editable' : False},
                renderer=tlview.Renderer(
                    function=cs_tag_crf,
                    user_data=mcols
                ),
                attributes={}
            )
        ]
    )

TAGS_TABLE_DESCR = tlview.ViewTemplate(
    properties={
        'enable-grid-lines' : False,
        'reorderable' : False,
        'rules_hint' : False,
        'headers-visible' : True,
    },
    selection_mode=gtk.SELECTION_SINGLE,
    columns=[
        cs_tag_column(TAGS_MODEL_DESCR),
        cs_table_column(TAGS_MODEL_DESCR, _('Rev')),
        cs_table_column(TAGS_MODEL_DESCR, _('Age')),
        cs_description_column(TAGS_MODEL_DESCR, (_('Branches'),)),
        cs_table_column(TAGS_MODEL_DESCR, _('Author')),
    ]
)

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

class TagsTable(ChangeSetTable):
    def __init__(self, busy_indicator=None, size_req=None):
        ChangeSetTable.__init__(self, model_descr = TAGS_MODEL_DESCR,
                                table_descr = TAGS_TABLE_DESCR,
                                busy_indicator=busy_indicator,
                                size_req=size_req)
        self.ui_manager.add_ui_from_string(CS_TABLE_EXEC_UI_DESCR)
        self.ui_manager.add_ui_from_string(CS_TABLE_REFRESH_UI_DESCR)
        self.ui_manager.add_ui_from_string(TAG_TABLE_UI_DESCR)
    def populate_action_groups(self):
        ChangeSetTable.populate_action_groups(self)
        self.action_groups[ws_actions.AC_IN_REPO + ws_actions.AC_NOT_PMIC + actions.AC_SELN_UNIQUE].add_actions(
            [
                ("cs_remove_selected_tag", icons.STOCK_REMOVE, _('Remove'), None,
                 _('Remove the selected tag from the repository'),
                 self._remove_tag_cs_acb),
                ("cs_move_selected_tag", icons.STOCK_MOVE, _('Move'), None,
                 _('Move the selected tag to another change set'),
                 self._move_tag_cs_acb),
            ])
    def _remove_tag_cs_acb(self, _action=None):
        tag = self.get_selected_key()
        local = self.get_selected_key_by_label(_('Scope'))
        self.show_busy()
        RemoveTagDialog(tag=tag, local=local).run()
        self.unshow_busy()
    def _move_tag_cs_acb(self, _action=None):
        tag = self.get_selected_key()
        self.show_busy()
        MoveTagDialog(tag=tag).run()
        self.unshow_busy()
    def _fetch_contents(self):
        try:
            return ifce.SCM.get_tags_data()
        except cmd_result.Failure as failure:
            dialogue.report_failure(failure)
            return []

BranchRow = collections.namedtuple('BranchRow', [_('Branch'), _('Rev'), _('Tags'), _('Age'), _('Author'), _('Description')])

BRANCHES_MODEL_DESCR = BranchRow(
    Branch=gobject.TYPE_STRING,
    Rev=gobject.TYPE_INT,
    Tags=gobject.TYPE_STRING,
    Age=gobject.TYPE_STRING,
    Author=gobject.TYPE_STRING,
    Description=gobject.TYPE_STRING,
)

BRANCHES_TABLE_DESCR = tlview.ViewTemplate(
    properties={
        'enable-grid-lines' : False,
        'reorderable' : False,
        'rules_hint' : False,
        'headers-visible' : True,
    },
    selection_mode=gtk.SELECTION_SINGLE,
    columns=[
        cs_table_column(BRANCHES_MODEL_DESCR, _('Branch')),
        cs_table_column(BRANCHES_MODEL_DESCR, _('Rev')),
        cs_table_column(BRANCHES_MODEL_DESCR, _('Age')),
        cs_description_column(BRANCHES_MODEL_DESCR, (_('Tags'),)),
        cs_table_column(BRANCHES_MODEL_DESCR, _('Author')),
    ]
)

class BranchesTable(ChangeSetTable):
    def __init__(self, busy_indicator=None, size_req=None):
        ChangeSetTable.__init__(self, model_descr = BRANCHES_MODEL_DESCR,
                                table_descr = BRANCHES_TABLE_DESCR,
                                busy_indicator=busy_indicator,
                                size_req=size_req)
        self.ui_manager.add_ui_from_string(CS_TABLE_EXEC_UI_DESCR)
        self.ui_manager.add_ui_from_string(CS_TABLE_REFRESH_UI_DESCR)
        self.ui_manager.add_ui_from_string(CS_TABLE_TAG_UI_DESCR)
    def _fetch_contents(self):
        try:
            return ifce.SCM.get_branches_data()
        except cmd_result.Failure as failure:
            dialogue.report_failure(failure)
            return []

class PrecisType:
    def __init__(self, get_data, model_descr=None, table_descr=None):
        if model_descr is None:
            self.model_descr = LOG_MODEL_DESCR
        else:
            self.model_descr = model_descr
        if table_descr is None:
            self.table_descr = LOG_TABLE_DESCR
        else:
            self.table_descr = table_descr
        self.get_data = get_data

class SelectTable(table.TableWithAGandUI):
    def __init__(self, ptype, size=(640, 240)):
        self._ptype = ptype
        table.TableWithAGandUI.__init__(self, model_descr = ptype.model_descr,
                                        table_descr = ptype.table_descr,
                                        size_req=size)
        self.set_contents()
        self.show_all()
    def _fetch_contents(self):
        return self._ptype.get_data()

class SelectDialog(dialogue.Dialog):
    def __init__(self, ptype, title, size=(640, 240), parent=None):
        dialogue.Dialog.__init__(self, title=_('gwsmg: Select %s') % title, parent=parent,
                                 flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                                 buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                          gtk.STOCK_OK, gtk.RESPONSE_OK)
                                )
        self._table = SelectTable(ptype=ptype, size=size)
        self.vbox.pack_start(self._table)
        self.show_all()
        self._table.seln.unselect_all()
    def get_change_set(self):
        return str(self._table.get_selected_key())

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
    def __init__(self, label=_('Message (optional)')):
        gtk.VBox.__init__(self)
        self.view = text_edit.SummaryView()
        self.view.ui_manager.add_ui_from_string(TAG_MSG_UI_DESCR)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(label), expand=False, fill=False)
        toolbar = self.view.ui_manager.get_widget("/tag_message_toolbar")
        toolbar.set_style(gtk.TOOLBAR_BOTH)
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        hbox.pack_end(toolbar, fill=False, expand=False)
        self.pack_start(hbox, expand=False)
        self.pack_start(gutils.wrap_in_scrolled_window(self.view))
        self.show_all()
    def get_msg(self):
        return self.view.get_msg()

class SetTagDialog(dialogue.ReadTextAndToggleDialog):
    def __init__(self, rev=None, parent=None):
        self._rev = rev
        dialogue.ReadTextAndToggleDialog.__init__(self, title=_('gwsmhg: Set Tag'),
            prompt=_('Tag:'), toggle_prompt=_('Local'), toggle_state=False, parent=parent)
        self.message = TagMessageWidget()
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
            result = ifce.SCM.do_set_tag(tag=tag, local=local, msg=msg,
                                         rev=self._rev)
            self.unshow_busy()
            if result[0] & cmd_result.SUGGEST_FORCE:
                ans = dialogue.ask_rename_force_or_cancel(result)
                if ans == dialogue.RESPONSE_RENAME:
                    self.show()
                    return
                if ans == dialogue.RESPONSE_FORCE:
                    self.show_busy()
                    result = ifce.SCM.do_set_tag(tag=tag, local=local, msg=msg,
                                                 rev=self._rev, force=True)
                    self.unshow_busy()
                    dialogue.report_any_problems(result)
            else:
                dialogue.report_any_problems(result)
            self.destroy()

class RemoveTagDialog(dialogue.ReadTextDialog):
    def __init__(self, tag=None, local=False, parent=None):
        self._tag = tag
        self._local = local
        dialogue.ReadTextDialog.__init__(self, title=_('gwsmhg: Remove Tag'),
            prompt=_('Removing Tag: '), suggestion=tag, parent=parent)
        self.entry.set_editable(False)
        self.message = TagMessageWidget()
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
            result = ifce.SCM.do_remove_tag(tag=self._tag, msg=msg, local=self._local)
            self.unshow_busy()
            dialogue.report_any_problems(result)
            self.destroy()

class MoveTagDialog(dialogue.ReadTextDialog):
    def __init__(self, tag=None, parent=None):
        self._tag = tag
        dialogue.ReadTextDialog.__init__(self, title=_('gwsmhg: Move Tag'),
            prompt=_('Move Tag: '), suggestion=tag, parent=parent)
        self.entry.set_editable(False)
        self._select_widget = ChangeSetSelectWidget(label=_('To Change Set:'),
            busy_indicator=self, discard_toggle=False)
        self.vbox.pack_start(self._select_widget)
        self.message = TagMessageWidget()
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
            result = ifce.SCM.do_move_tag(tag=self._tag, rev=rev, msg=msg)
            self.unshow_busy()
            dialogue.report_any_problems(result)
            self.destroy()

TagListRow = collections.namedtuple('TagListRow', [_('Tag')])

TAG_LIST_MODEL_DESCR = TagListRow(Tag=gobject.TYPE_STRING)

TAG_LIST_TABLE_DESCR = tlview.ViewTemplate(
    properties={
        'enable-grid-lines' : False,
        'reorderable' : False,
        'rules_hint' : False,
        'headers-visible' : False,
    },
    selection_mode=gtk.SELECTION_SINGLE,
    columns=[
        cs_table_column(TAG_LIST_MODEL_DESCR, _('Tag')),
    ]
)

BranchListRow = collections.namedtuple('BranchListRow', [_('Branch')])

BRANCH_LIST_MODEL_DESCR = BranchListRow(Branch=gobject.TYPE_STRING)

BRANCH_LIST_TABLE_DESCR = tlview.ViewTemplate(
    properties={
        'enable-grid-lines' : False,
        'reorderable' : False,
        'rules_hint' : False,
        'headers-visible' : False,
    },
    selection_mode=gtk.SELECTION_SINGLE,
    columns=[
        cs_table_column(BRANCH_LIST_MODEL_DESCR, _('Branch')),
    ]
)

class ChangeSetSelectWidget(gtk.VBox, dialogue.BusyIndicatorUser):
    def __init__(self, busy_indicator, label=_('Change Set:'), discard_toggle=False):
        gtk.VBox.__init__(self)
        dialogue.BusyIndicatorUser.__init__(self, busy_indicator)
        hbox = gtk.HBox()
        self._tags_button = gtk.Button(label=_('Browse _Tags'))
        self._tags_button.connect("clicked", self._browse_tags_cb)
        self._branches_button = gtk.Button(label=_('Browse _Branches'))
        self._branches_button.connect("clicked", self._browse_branches_cb)
        self._heads_button = gtk.Button(label=_('Browse _Heads'))
        self._heads_button.connect("clicked", self._browse_heads_cb)
        self._history_button = gtk.Button(label=_('Browse H_istory'))
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
            self._discard_toggle = gtk.CheckButton(_('Discard local changes'))
            self._discard_toggle.set_active(False)
            hbox.pack_start(self._discard_toggle, expand=False, fill=False)
        else:
            self._discard_toggle = None
        self.pack_start(hbox, expand=False, fill=False)
        self.show_all()
    def _browse_change_set(self, ptype, title, size=(640, 240)):
        self.show_busy()
        dialog = SelectDialog(ptype=ptype, title=title, size=size, parent=None)
        self.unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self._entry.set_text(dialog.get_change_set())
        dialog.destroy()
    def _browse_tags_cb(self, button=None):
        ptype = PrecisType(ifce.SCM.get_tags_list_for_table,
                           TAG_LIST_MODEL_DESCR, TAG_LIST_TABLE_DESCR)
        self._browse_change_set(ptype, _('Tags'), size=(160, 320))
    def _browse_branches_cb(self, button=None):
        ptype = PrecisType(ifce.SCM.get_branches_list_for_table,
                           TAG_LIST_MODEL_DESCR, TAG_LIST_TABLE_DESCR)
        self._browse_change_set(ptype, _('Branches'), size=(160, 320))
    def _browse_heads_cb(self, button=None):
        ptype = PrecisType(ifce.SCM.get_heads_data)
        self._browse_change_set(ptype, _('Heads'), size=(640, 480))
    def _browse_history_cb(self, button=None):
        ptype = PrecisType(ifce.SCM.get_history_data)
        self._browse_change_set(ptype, _('History'), size=(640, 480))
    def _entry_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def get_change_set(self):
        return self._entry.get_text()
    def get_discard(self):
        if self._discard_toggle is None:
            return False
        return self._discard_toggle.get_active()

class ChangeSetSelectDialog(dialogue.Dialog):
    def __init__(self, discard_toggle=False, parent=None):
        title = _('gwsmg: Select Change Set: %s') % utils.path_rel_home(os.getcwd())
        dialogue.Dialog.__init__(self, title=title, parent=parent,
                                 flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                                 buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                          gtk.STOCK_OK, gtk.RESPONSE_OK)
                                )
        self._widget = ChangeSetSelectWidget(busy_indicator=self,
            discard_toggle=discard_toggle)
        self.vbox.pack_start(self._widget)
        self.show_all()
    def get_change_set(self):
        return self._widget.get_change_set()
    def get_discard(self):
        return self._widget.get_discard()

class FileTreeStore(file_tree.FileTreeStore):
    def __init__(self, rev):
        self._rev = rev
        file_tree.FileTreeStore.__init__(self, show_hidden=True, populate_all=True, auto_expand=True)
        self.repopulate()
    def _get_file_db(self):
        return ifce.SCM.get_change_set_files_db(self._rev)

CHANGE_SET_FILES_UI_DESCR = \
'''
<ui>
  <popup name="files_popup">
    <placeholder name="selection">
      <menuitem action="scm_diff_files_selection"/>
      <menuitem action="scm_extdiff_files_selection"/>
    </placeholder>
    <separator/>
    <placeholder name="no_selection"/>
      <menuitem action="scm_diff_files_all"/>
      <menuitem action="scm_extdiff_files_all"/>
    <separator/>
  </popup>
</ui>
'''

class FileTreeView(file_tree.FileTreeView):
    def __init__(self, rev, busy_indicator):
        self._rev = rev
        model = FileTreeStore(rev)
        file_tree.FileTreeView.__init__(self, model=model,
                                        busy_indicator=busy_indicator,
                                        auto_refresh=False, show_status=True)
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.set_headers_visible(False)
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_MADE].add_actions(
            [
                ("scm_diff_files_selection", icons.STOCK_DIFF, _('_Diff'), None,
                 _('Display the diff for selected file(s)'), self._diff_selected_files_acb),
                ("scm_extdiff_files_selection", icons.STOCK_DIFF, _('E_xtdiff'), None,
                 _('Launch extdiff for selected file(s)'), self._extdiff_selected_files_acb),
            ])
        self.action_groups[ws_actions.AC_IN_REPO + actions.AC_SELN_NONE].add_actions(
            [
                ("scm_diff_files_all", icons.STOCK_DIFF, _('_Diff'), None,
                 _('Display the diff for all changes'), self._diff_all_files_acb),
                ("scm_extdiff_files_all", icons.STOCK_DIFF, _('E_xtdiff'), None,
                 _('Launch extdiff for all changes'), self._extdiff_all_files_acb),
            ])
        self.set_visibility_for_condns(actions.AC_DONT_CARE, False)
        if not ifce.SCM.get_extension_enabled("extdiff"):
            self.get_conditional_action("scm_extdiff_files_selection").set_visible(False)
            self.get_conditional_action("scm_extdiff_files_all").set_visible(False)
        self.scm_change_merge_id = self.ui_manager.add_ui_from_string(CHANGE_SET_FILES_UI_DESCR)
    def _diff_selected_files_acb(self, _action=None):
        parent = dialogue.main_window
        self.show_busy()
        dialog = diff.ScmDiffTextDialog(parent=parent,
                                     file_list=self.get_selected_files(),
                                     torev=self._rev)
        self.unshow_busy()
        dialog.show()
    def _diff_all_files_acb(self, _action=None):
        parent = dialogue.main_window
        self.show_busy()
        dialog = diff.ScmDiffTextDialog(parent=parent, torev=self._rev)
        self.unshow_busy()
        dialog.show()
    def _extdiff_selected_files_acb(self, _action=None):
        ifce.SCM.launch_extdiff_for_changeset(self._rev, self.get_selected_files())
    def _extdiff_all_files_acb(self, _action=None):
        ifce.SCM.launch_extdiff_for_changeset(self._rev)

class ChangeSetSummaryDialog(dialogue.AmodalDialog):
    def __init__(self, rev, parent=None):
        dialogue.AmodalDialog.__init__(self, parent=parent,
                                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                       buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE))
        self._rev = rev
        self.set_title(_('gwsmg: Change Set: %s : %s') % (rev, utils.cwd_rel_home()))
        summary = self.get_change_set_summary()
        self._add_labelled_texts([(_('Precis:'), summary['PRECIS'])])
        self._add_labelled_texts([(_('Revision:'), summary['REV']), (_('Node:'), summary['NODE'])])
        self._add_labelled_texts([(_('Date:'), summary['DATE']), (_('Age:'), summary['AGE'])])
        self._add_labelled_texts([(_('Author:'), summary['AUTHOR']), (_('Email:'), summary['EMAIL'])])
        self._add_labelled_texts([(_('Tags:'), summary['TAGS'])])
        self._add_labelled_texts([(_('Branches:'), summary['BRANCHES'])])
        vpaned1 = gtk.VPaned()
        self.vbox.pack_start(vpaned1)
        vbox = gtk.VBox()
        self._add_label(_('Description:'), vbox)
        cdv = gtk.TextView()
        cdv.set_editable(False)
        cdv.set_cursor_visible(False)
        cdv.get_buffer().set_text(summary['DESCR'])
        vbox.pack_start(gutils.wrap_in_scrolled_window(cdv), expand=True)
        vpaned1.add1(vbox)
        vpaned2 = gtk.VPaned()
        vbox = gtk.VBox()
        self._add_label(_('File(s):'), vbox)
        self.ftv = self.get_file_tree_view()
        vbox.pack_start(gutils.wrap_in_scrolled_window(self.ftv), expand=True)
        vpaned2.add1(vbox)
        vbox = gtk.VBox()
        self._add_label(_('Parent(s):'), vbox)
        ptv = self.get_parents_view()
        vbox.pack_start(ptv, expand=True)
        vpaned2.add2(vbox)
        vpaned1.add2(vpaned2)
        self.connect("response", self._close_cb)
        self.show_all()
    def get_change_set_summary(self):
        return ifce.SCM.get_change_set_summary(self._rev)
    def get_file_tree_view(self):
        return FileTreeView(self._rev, busy_indicator=self)
    def get_parents_view(self):
        return ParentsTable(self._rev, #auto_refresh_on=False,
            busy_indicator=self)
    def _add_label(self, text, component=None):
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(text), expand=False, fill=False)
        if component:
            component.pack_start(hbox, expand=False, fill=False)
        else:
            self.vbox.pack_start(hbox, expand=False)
    def _add_labelled_texts(self, labelled_text_list, component=None):
        hbox = gtk.HBox()
        for item in labelled_text_list:
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

class BackoutDialog(dialogue.ReadTextAndToggleDialog):
    def __init__(self, rev=None, descr='', parent=None):
        self._rev = rev
        dialogue.ReadTextAndToggleDialog.__init__(self, title=_('gwsmhg: Backout'),
            prompt=_('Backing Out: '), suggestion='%s: %s' % (rev, descr), parent=parent,
            toggle_prompt=_('Auto Merge'), toggle_state=False)
        self.entry.set_editable(False)
        self._radio_labels = []
        self._parent_revs = []
        parents_data = ifce.SCM.get_parents_data(rev)
        if len(parents_data) > 1:
            for data in parents_data:
                rev = str(data[tlview.model_col(LOG_MODEL_DESCR, _('Rev'))])
                descr = data[tlview.model_col(LOG_MODEL_DESCR, _('Description'))]
                self._radio_labels.append('%s: %s' % (rev, descr))
                self._parent_revs.append(rev)
            self._radio_buttons = gutils.RadioButtonFramedVBox(title=_('Choose Parent'), labels=self._radio_labels)
            self.vbox.add(self._radio_buttons)
        self.message = TagMessageWidget(label=_('Message'))
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
            dialogue.main_window.show_busy()
            result = ifce.SCM.do_backout(rev=self._rev, merge=merge, parent=parent, msg=msg)
            dialogue.main_window.unshow_busy()
            dialogue.report_any_problems(result)
            self.destroy()
