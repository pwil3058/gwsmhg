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
from gwsmhg_pkg import ifce, table, icons, ws_event, cmd_result, gutils, patch_mgr
from gwsmhg_pkg import diff, utils

PBRANCH_UI_DESCR = \
'''
<ui>
  <toolbar name='pbranch_toolbar'>
    <toolitem name='PNew' action='pbranch_pnew'/>
    <separator/>
    <toolitem name='EditMessage' action='pbranch_edit_msg'/>
    <toolitem name='PDiff' action='pbranch_pdiff'/>
    <toolitem name='PStatus' action='pbranch_pstatus'/>
    <toolitem name='PMerge' action='pbranch_pmerge'/>
    <toolitem name='PBackout' action='pbranch_pbackout'/>
    <separator/>
    <toolitem name='PGraph' action='pbranch_pgraph'/>
    <separator/>
    <toolitem name='Refresh' action='pbranch_refresh'/>
  </toolbar>
  <popup name='pbranch_popup'>
    <menuitem action='pbranch_pstatus_selection'/>
    <menuitem action='pbranch_pdiff_selection'/>
    <menuitem action='pbranch_edit_msg_selection'/>
    <menuitem action='pbranch_update_to_selection'/>
    <menuitem action='pbranch_pmerge_into_selection'/>
  </popup>
</ui>
'''

PBRANCH_LIST_MODEL_DESCR = \
[ ['pbranch', gobject.TYPE_STRING],
  ['title', gobject.TYPE_STRING],
  ['current', gobject.TYPE_BOOLEAN],
  ['status', gobject.TYPE_BOOLEAN],
]

def set_current_pixbuf(column, cell, model, iter):
    current = model.get_labelled_value(iter, 'current')
    if current:
        cell.set_property('stock-id', gtk.STOCK_YES)
    else:
        cell.set_property('stock-id', gtk.STOCK_REMOVE)

def set_status_pixbuf(column, cell, model, iter):
    status = model.get_labelled_value(iter, 'status')
    if status:
        cell.set_property('stock-id', icons.STOCK_STATUS_OK)
    else:
        cell.set_property('stock-id', icons.STOCK_STATUS_NOT_OK)

PBRANCH_LIST_TABLE_DESCR = \
[ [ ('enable-grid-lines', True), ('reorderable', False),
    ('headers-visible', False)
  ], # properties
  gtk.SELECTION_MULTIPLE, # selection mode
  [
    [ 'Current', [('expand', False), ], # column name and properties
      [ [ (gtk.CellRendererPixbuf, False, True), # renderer
          [ ], # properties
          set_current_pixbuf, # cell_renderer_function
          [ ] # attributes
        ],
      ]
    ],
    [ 'Status', [('expand', False), ], # column name and properties
      [ [ (gtk.CellRendererPixbuf, False, True), # renderer
          [ ], # properties
          set_status_pixbuf, # cell_renderer_function
          [ ] # attributes
        ],
      ]
    ],
    [ 'PBranch', [('expand', True), ], # column name and properties
      [ [ (gtk.CellRendererText, False, True), # renderer
          [ ('editable', False), ], # properties
          None, # cell_renderer_function
          [ ('text', table.model_col(PBRANCH_LIST_MODEL_DESCR, 'pbranch')), ] # attributes
        ],
      ]
    ],
    [ 'Title', [('expand', True), ], # column
      [ [ (gtk.CellRendererText, False, True), # renderer
          [ ('editable', False), ], # properties
          None, # cell_renderer_function
          [ ('text', table.model_col(PBRANCH_LIST_MODEL_DESCR, 'title')), ] # attributes
        ],
      ]
    ]
  ]
]

class PBranchTable(table.Table, cmd_result.ProblemReporter,
                   gutils.BusyIndicatorUser):
    def __init__(self, busy_indicator=None):
        cmd_result.ProblemReporter.__init__(self)
        self._local_action_group = gtk.ActionGroup('in_pbranch')
        self._local_action_group.add_actions(
            [
                ('pbranch_edit_msg', gtk.STOCK_EDIT, 'P_Message', None,
                 'Edit the message for the current patch branch',
                  self._edit_msg_acb),
                ('pbranch_pdiff', icons.STOCK_DIFF, 'P_Diff', None,
                 'Display diff for the current patch branch',
                  self._pdiff_acb),
                ('pbranch_pstatus', icons.STOCK_STATUS, 'P_Status', None,
                 'Display status message for current patch branch',
                  self._pstatus_acb),
                ('pbranch_pmerge', icons.STOCK_MERGE, 'P_Merge', None,
                 'Merge pending heads from dependencies into current patch branch',
                  self._pmerge_acb),
                ('pbranch_pbackout', icons.STOCK_BACKOUT, 'P_Backout', None,
                 'Back out the current patch branch',
                  self._pbackout_acb),
            ])
        gutils.BusyIndicatorUser.__init__(self, busy_indicator)
        table.Table.__init__(self, PBRANCH_LIST_MODEL_DESCR, PBRANCH_LIST_TABLE_DESCR)
        ws_event.add_notification_cb(ws_event.REPO_MOD|ws_event.FILE_CHANGES|ws_event.CHECKOUT, self.update_contents)
        self.action_groups[table.ALWAYS_ON].add_actions(
            [
                ('pbranch_pnew', icons.STOCK_NEW_PATCH, 'P_New', None,
                 'Start a new patch branch',
                  self._pnew_acb),
                ('pbranch_pgraph', icons.STOCK_GRAPH, 'P_Graph', None,
                 'Display pgraph output',
                  self._pgraph_acb),
                ('pbranch_refresh', gtk.STOCK_REFRESH, '_Refresh', None,
                 'Refresh patch branch display',
                  self._refresh_acb),
            ])
        self.action_groups[table.UNIQUE_SELECTION].add_actions(
            [
                ('pbranch_pstatus_selection', icons.STOCK_STATUS, 'P_Status', None,
                 'Display status message for selected patch branch',
                  self._pstatus_selection_acb),
                ('pbranch_pdiff_selection', icons.STOCK_DIFF, 'P_Diff', None,
                 'Display diff for selected patch branch',
                  self._pdiff_selection_acb),
                ('pbranch_edit_msg_selection', gtk.STOCK_EDIT, 'P_Message', None,
                 'Edit the message for the selected patch branch',
                  self._edit_msg_selection_acb),
                ('pbranch_update_to_selection', icons.STOCK_UPDATE, '_Update To', None,
                 'Update the work space to the selected patch branch',
                  self._update_to_selection_acb),
            ])
        self.action_groups[table.SELECTION].add_actions(
            [
                ('pbranch_pmerge_into_selection', icons.STOCK_MERGE, 'P_Merge', None,
                 'Merge pending heads from dependencies into selected patch branches',
                  self._pmerge_selection_acb),
            ])
        self._ui_manager = gtk.UIManager()
        for condition in [table.ALWAYS_ON, table.SELECTION, table.UNIQUE_SELECTION]:
            self._ui_manager.insert_action_group(self.action_groups[condition], -1)
        self._ui_manager.insert_action_group(self._local_action_group, -1)
        self.cwd_merge_id = self._ui_manager.add_ui_from_string(PBRANCH_UI_DESCR)
        self.action_groups[table.ALWAYS_ON].set_sensitive(ifce.SCM.is_repository())
        self.view.connect("button_press_event", self._handle_button_press_cb)
        self._tool_bar = self._ui_manager.get_widget("/pbranch_toolbar")
        self.pack_start(self._tool_bar, expand=False)
        self.reorder_child(self._tool_bar, 0)
    def _handle_button_press_cb(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 3:
                menu = self._ui_manager.get_widget("/pbranch_popup")
                menu.popup(None, None, None, event.button, event.time)
                return True
        return False
    def _fetch_contents(self):
        res, pbranches, serr = ifce.SCM.get_pbranch_table_data()
        in_pbranch_branch = False
        for pb in pbranches:
            if pb[table.model_col(PBRANCH_LIST_MODEL_DESCR, 'current')]:
                in_pbranch_branch = True
                break
        self._local_action_group.set_sensitive(in_pbranch_branch)
        return pbranches
    def update_for_chdir(self):
        self.action_groups[table.ALWAYS_ON].set_sensitive(ifce.SCM.is_repository())
        self.set_contents()
    def update_contents(self):
        # TODO something more sophisticated needed here to improve usability
        # e.g. leave selection intact
        self.set_contents()
    def get_selected_pbranch(self):
        model, paths = self.seln.get_selected_rows()
        assert len(paths) <= 1
        if len(paths) == 0:
            return None
        else:
            return model.get_labelled_value(model.get_iter(paths[0]), 'pbranch')
    def get_selected_pbranches(self):
        model, paths = self.seln.get_selected_rows()
        if len(paths) == 0:
            return []
        else:
            pbranches = []
            for path in paths:
                pbranches.append(model.get_labelled_value(model.get_iter(path), 'pbranch'))
            return pbranches
    def _pstatus_selection_acb(self, action=None):
        pbranch = self.get_selected_pbranch()
        self._show_busy()
        res, sout, serr = ifce.SCM.get_pstatus(pbranch)
        self._unshow_busy()
        if res:
            self._report_any_problems((res, sout, serr))
        else:
            gutils.inform_user(os.linesep.join([sout,serr]), problem_type=gtk.MESSAGE_INFO)
    def _pdiff_selection_acb(self, action=None):
        pbranch = self.get_selected_pbranch()
        dialog = PbDiffTextDialog(parent=ifce.main_window, pbranch=pbranch,
                                  modal=False)
        dialog.show()
    def _edit_msg_selection_acb(self, action=None):
        pbranch = self.get_selected_pbranch()
        PatchBranchDescrEditDialog(parent=None, modal=False, pbranch=pbranch).show()
    def _update_to_selection_acb(self, action=None):
        pbranch = self.get_selected_pbranch()
        self._show_busy()
        result = ifce.SCM.do_update_workspace(rev=pbranch)
        self._unshow_busy()
        self._report_any_problems(result)
    def _pmerge_selection_acb(self, action=None):
        pbranches = self.get_selected_pbranches()
        self._show_busy()
        result = ifce.SCM.do_pmerge(pbranches)
        self._unshow_busy()
        self._report_any_problems(result)
    def _pnew_acb(self, action=None):
        dialog = NewPatchBranchDialog(parent=None, modal=False)
        if dialog.run() == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return
        new_pbranch_name = dialog.get_new_patch_name()
        new_pbranch_descr = dialog.get_new_patch_descr()
        preserve = dialog.get_preserve()
        dialog.destroy()
        if not new_pbranch_name:
            return
        self._show_busy()
        result = ifce.SCM.do_new_pbranch(new_pbranch_name, new_pbranch_descr, preserve)
        self._unshow_busy()
        self._report_any_problems(result)
    def _pstatus_acb(self, action=None):
        self._show_busy()
        res, sout, serr = ifce.SCM.get_pstatus()
        self._unshow_busy()
        if res:
            self._report_any_problems((res, sout, serr))
        else:
            gutils.inform_user(os.linesep.join([sout,serr]), problem_type=gtk.MESSAGE_INFO)
    def _pdiff_acb(self, action=None):
        dialog = PbDiffTextDialog(parent=ifce.main_window, modal=False)
        dialog.show()
    def _edit_msg_acb(self, action=None):
        PatchBranchDescrEditDialog(parent=None, modal=False).show()
    def _pbackout_acb(self, action=None):
        self._show_busy()
        result = ifce.SCM.do_pbackout()
        self._unshow_busy()
        self._report_any_problems(result)
    def _pmerge_acb(self, action=None):
        self._show_busy()
        result = ifce.SCM.do_pmerge()
        self._unshow_busy()
        self._report_any_problems(result)
    def _pgraph_acb(self, action=None):
        self._show_busy()
        res, sout, serr = ifce.SCM.get_pgraph()
        self._unshow_busy()
        if res:
            self._report_any_problems((res, sout, serr))
        else:
            gutils.inform_user(os.linesep.join([sout,serr]), problem_type=gtk.MESSAGE_INFO)
    def _refresh_acb(self, action=None):
        self.update_contents()

class NewPatchBranchDialog(patch_mgr.NewPatchDialog):
    def __init__(self, parent, modal=False):
        patch_mgr.NewPatchDialog.__init__(self, parent=parent,
            modal=modal, objname='Patch Branch')
        self._preserve = gtk.CheckButton('Preserve', False)
        self._preserve.set_active(False)
        self.hbox.pack_start(self._preserve, expand=False, fill=False)
        self.hbox.show_all()
    def get_preserve(self):
        return self._preserve.get_active()

class PatchBranchDescrEditDialog(patch_mgr.GenericPatchDescrEditDialog):
    def __init__(self, parent, pbranch=None, modal=False):
        patch_mgr.GenericPatchDescrEditDialog.__init__(self,
            get_summary=ifce.SCM.get_pbranch_description,
            set_summary=ifce.SCM.do_set_pbranch_description,
            parent=parent, patch=pbranch, modal=modal)

class PbDiffTextBuffer(diff.DiffTextBuffer):
    def __init__(self, file_list=[], pbranch=None, table=None):
        diff.DiffTextBuffer.__init__(self, file_list=file_list, table=table)
        self._pbranch = pbranch
        self.a_name_list = ["diff_save", "diff_save_as", "diff_refresh"]
        self.diff_buttons = gutils.ActionButtonList([self._action_group], self.a_name_list)
    def _get_diff_text(self):
        res, text, serr = ifce.SCM.get_pdiff_for_files(self._file_list, self._pbranch)
        self._report_any_problems((res, text, serr))
        return text

class PbDiffTextView(diff.DiffTextView):
    def __init__(self, file_list=[], pbranch=None):
        buffer = PbDiffTextBuffer(file_list, pbranch=pbranch)
        diff.DiffTextView.__init__(self, buffer=buffer)

class PbDiffTextWidget(diff.DiffTextWidget):
    def __init__(self, parent, file_list=[], pbranch=None):
        diff_view = PbDiffTextView(file_list=file_list, pbranch=pbranch)
        diff.DiffTextWidget.__init__(self, parent=parent, diff_view=diff_view)

class PbDiffTextDialog(gtk.Dialog):
    def __init__(self, parent, file_list=[], pbranch=None, modal=False):
        if modal or (parent and parent.get_modal()):
            flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
        else:
            flags = gtk.DIALOG_DESTROY_WITH_PARENT
        title = "diff: %s" % utils.path_rel_home(os.getcwd())
        mutable = pbranch is None
        if pbranch:
            title += " Patch Branch: %s" % pbranch
        else:
            title += " Patch Branch: []"
        gtk.Dialog.__init__(self, title, parent, flags, ())
        dtw = PbDiffTextWidget(self, file_list, pbranch=pbranch)
        self.vbox.pack_start(dtw)
        tws_display = dtw.diff_view.get_buffer().tws_display
        self.action_area.pack_end(tws_display, expand=False, fill=False)
        for button in dtw.diff_view.get_buffer().diff_buttons.list:
            self.action_area.pack_start(button)
        self.add_buttons(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.connect("response", self._close_cb)
        self.show_all()
    def _close_cb(self, dialog, response_id):
        dialog.destroy()

