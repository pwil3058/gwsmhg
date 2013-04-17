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

import os, gtk, sys
from gwsmhg_pkg import dialogue, icons, ifce, actions, change_set, file_tree
from gwsmhg_pkg import path, cmd_result, diff, config, tortoise
from gwsmhg_pkg import ws_event, patch_mgr, utils

GWSM_UI_DESCR = \
'''
<ui>
  <toolbar name="gwsm_toolbar">
    <placeholder name="gwsm_ws_tools">
      <toolitem name="Diff" action="gwsm_diff_ws"/>
      <toolitem name="Revert" action="gwsm_revert_ws"/>
      <toolitem name="Commit" action="gwsm_commit_ws"/>
      <toolitem name="Tag" action="gwsm_tag_ws"/>
      <toolitem name="Branch" action="gwsm_branch_ws"/>
      <toolitem name='Merge' action='gwsm_merge_ws'/>
      <toolitem name='Resolve' action='gwsm_resolve_ws'/>
      <toolitem name="Checkout" action="gwsm_checkout_ws"/>
      <toolitem name="Update" action="gwsm_update_ws"/>
      <separator/>
      <toolitem name="Refresh" action="gwsm_refresh_ws"/>
    </placeholder>
    <separator/>
    <placeholder name="gwsm_repo_tools">
      <toolitem name="Pull" action="gwsm_pull_repo"/>
      <toolitem name="Push" action="gwsm_push_repo"/>
      <separator/>
      <toolitem name="Verify" action="gwsm_verify_repo"/>
      <toolitem name="Rollback" action="gwsm_rollback_repo"/>
    </placeholder>
  </toolbar>
  <menubar name="gwsm_menubar">
    <menu name="gwsm_wd" action="gwsm_working_directory">
      <menuitem action="gwsm_change_wd"/>
      <menuitem action="gwsm_init_wd"/>
      <menuitem action="gwsm_clone_repo_in_wd"/>
      <menuitem action="gwsm_quit"/>
    </menu>
    <menu name='gwsm_repo_menu' action='gwsm_repo_menu'>
      <menuitem action='gwsm_verify_repo'/>
      <menuitem action='gwsm_rollback_repo'/>
      <menuitem action='gwsm_edit_repo_config'/>
    </menu>
  </menubar>
  <menubar name="gwsm_right_side_menubar">
    <menu name="gwsm_config" action="gwsm_configuration">
      <menuitem action="gwsm_config_editors"/>
    </menu>
  </menubar>
</ui>
'''

class gwsm(gtk.Window, dialogue.BusyIndicator, actions.AGandUIManager):
    def __init__(self, dir_specified):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_icon_from_file(icons.APP_ICON_FILE)
        dialogue.BusyIndicator.__init__(self)
        ifce.create_log(self)
        self.connect("destroy", self._quit)
        # see if we're in a valid work space and if not offer a selection
        # unless a directory was specified on the command line
        open_dialog = None # we need this later
        if dir_specified:
            if ifce.term:
                ifce.term.set_cwd(os.getcwd())
        elif not ifce.in_valid_repo:
            open_dialog = config.WSOpenDialog()
            if open_dialog.run() == gtk.RESPONSE_OK:
                wspath = open_dialog.get_path()
                if wspath:
                    open_dialog.show_busy()
                    result = ifce.chdir(wspath)
                    open_dialog.unshow_busy()
                    dialogue.report_any_problems(result)
            else:
                sys.exit()
            open_dialog.show_busy()
        dialogue.init(self)
        actions.AGandUIManager.__init__(self)
        actions.add_class_indep_actions(actions.Condns.DONT_CARE,
            [
                ("gwsm_working_directory", None, _('_Working Directory')),
                ("gwsm_configuration", None, _('_Configuration')),
                ("gwsm_change_wd", gtk.STOCK_OPEN, _('_Open'), "",
                 _('Change current working directory'), self._change_wd_acb),
                ("gwsm_config_editors", gtk.STOCK_PREFERENCES, _('_Editor Allocation'), "",
                 _('Allocate editors to file types'), self._config_editors_acb),
                ("gwsm_quit", gtk.STOCK_QUIT, _('_Quit'), "",
                 _('Quit'), self._quit),
            ])
        actions.add_class_indep_actions(actions.Condns.NOT_IN_REPO,
            [
                ("gwsm_init_wd", icons.STOCK_INIT, _('_Initialise'), "",
                 _('Initialise the current working directory'), self._init_wd_acb),
                ("gwsm_clone_repo_in_wd", icons.STOCK_CLONE, _('_Clone'), "",
                 _('Clone a repository cd into the resultant working directory'),
                 self._clone_repo_acb),
            ])
        actions.add_class_indep_actions(actions.Condns.IN_REPO,
            [
                ('gwsm_repo_menu', None, _('_Repository')),
                ("gwsm_diff_ws", icons.STOCK_DIFF, _('Diff'), "",
                 _('View diff(s) for the current working directory'),
                 self._diff_ws_acb),
                ("gwsm_pull_repo", icons.STOCK_PULL, _('Pull'), "",
                 _('Pull all available changes from the default path'),
                 self._pull_repo_acb),
                ("gwsm_verify_repo", icons.STOCK_VERIFY, _('Verify'), "",
                 _('Verify the integrity of the repository'),
                 self._verify_repo_acb),
                ('gwsm_edit_repo_config', icons.STOCK_EDIT, _('Edit _Configuration'), '',
                 _('Edit the repository configuration file'),
                 self._edit_repo_config_acb),
                ("gwsm_refresh_ws", icons.STOCK_SYNCH, _('Refresh'), "",
                 _('Refresh the displayed data. Useful after external actions change workspace/repository state.'),
                 self._refresh_displayed_data_acb),
            ])
        actions.add_class_indep_actions(actions.Condns.IN_REPO + actions.Condns.NOT_PMIC,
            [
                ("gwsm_revert_ws", icons.STOCK_REVERT, _('Revert'), "",
                 _('Revert all changes in the current working directory'),
                 self._revert_ws_acb),
                ("gwsm_commit_ws", icons.STOCK_COMMIT, _('Commit'), "",
                 _('Commit all changes in the current working directory'),
                 self._commit_ws_acb),
                ("gwsm_tag_ws", icons.STOCK_TAG, _('Tag'), "",
                 _('Tag the parent of the current working directory'),
                 self._tag_ws_acb),
                ("gwsm_branch_ws", icons.STOCK_BRANCH, _('Branch'), "",
                 _('Set the branch for the current working directory'),
                 self._branch_ws_acb),
                ('gwsm_merge_ws', icons.STOCK_MERGE, _('Merge'), '',
                 _('Merge the current working directory with default alternative head'),
                 self._merge_ws_acb),
                ('gwsm_resolve_ws', icons.STOCK_RESOLVE, None, '',
                 _('Resolve any unresolve merge conflicts in the current working directory'),
                 self._resolve_ws_acb),
                ("gwsm_checkout_ws", icons.STOCK_CHECKOUT, _('Checkout'), "",
                 _('Check out a different revision in the current working directory'),
                 self._checkout_ws_acb),
                ("gwsm_update_ws", icons.STOCK_UPDATE, _('Update'), "",
                 _('Update the current working directory to the tip of the current branch'),
                 self._update_ws_acb),
                ("gwsm_push_repo", icons.STOCK_PUSH, _('Push'), "",
                 _('Push all available changes to the default path'),
                 self._push_repo_acb),
                ("gwsm_rollback_repo", icons.STOCK_ROLLBACK, _('Rollback'), "",
                 _('Roll back the last transaction'),
                 self._rollback_repo_acb),
            ])
        self.ui_manager.add_ui_from_string(GWSM_UI_DESCR)
        if tortoise.IS_AVAILABLE:
            self.ui_manager.add_ui_from_string(tortoise.TORTOISE_HGTK_UI)
        self._menubar = self.ui_manager.get_widget("/gwsm_menubar")
        self._rhs_menubar = self.ui_manager.get_widget("/gwsm_right_side_menubar")
        self._toolbar = self.ui_manager.get_widget("/gwsm_toolbar")
        self._toolbar.set_style(gtk.TOOLBAR_BOTH)
        self._parent_table = change_set.ParentsTable()
        self._file_tree_widget = file_tree.ScmCwdFilesWidget()
        self._notebook = gtk.Notebook()
        self._notebook.set_size_request(640, 360)
        self._patch_mgr = patch_mgr.PatchManagementWidget()
        pmpage = self._notebook.append_page(self._patch_mgr, gtk.Label(ifce.PM.name))
        self._heads_table = change_set.HeadsTable()
        self._notebook.append_page(self._heads_table, gtk.Label(_('Heads')))
        self._tags_table = change_set.TagsTable()
        self._notebook.append_page(self._tags_table, gtk.Label(_('Tags')))
        self._branches_table = change_set.BranchesTable()
        self._notebook.append_page(self._branches_table, gtk.Label(_('Branches')))
        self._history_table = change_set.HistoryTable()
        self._notebook.append_page(self._history_table, gtk.Label(_('History')))
        self._path_table = path.PathTable()
        self._notebook.append_page(self._path_table, gtk.Label(_('Paths')))
        self._notebook.set_current_page(pmpage)
        # Now lay the widgets out
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        hbox.pack_start(self._menubar, expand=True)
        hbox.pack_end(self._rhs_menubar, expand=False)
        vbox.pack_start(hbox, expand=False)
        vbox.pack_start(self._parent_table, expand=False)
        vbox.pack_start(self._toolbar, expand=False)
        hpane = gtk.HPaned()
        vbox.pack_start(hpane, expand=True)
        hpane.add1(self._file_tree_widget)
        vpane = gtk.VPaned()
        hpane.add2(vpane)
        vpane.add1(self._notebook)
        if ifce.term:
            self._tl_notebook = gtk.Notebook()
            self._tl_notebook.append_page(ifce.log, gtk.Label(_('Transactions')))
            self._tl_notebook.append_page(ifce.term, gtk.Label(_('Terminal')))
            vpane.add2(self._tl_notebook)
        else:
            vpane.add2(ifce.log)
        self.add(vbox)
        self.show_all()
        self._update_title()
        self._parent_table.seln.unselect_all()
        self.add_notification_cb(ws_event.CHANGE_WD, self._reset_after_cd)
        if open_dialog:
            open_dialog.unshow_busy()
            open_dialog.destroy()
    def _quit(self, _widget):
        gtk.main_quit()
    def _update_title(self):
        self.set_title("gwsm%s: %s" % (ifce.SCM.name, utils.path_rel_home(os.getcwd())))
    def _reset_after_cd(self, _arg=None):
        self.show_busy()
        self._update_title()
        self.unshow_busy()
    def _change_wd_acb(self, _action=None):
        open_dialog = config.WSOpenDialog(parent=self)
        if open_dialog.run() == gtk.RESPONSE_OK:
            wspath = open_dialog.get_path()
            if wspath:
                open_dialog.show_busy()
                result = ifce.chdir(wspath)
                open_dialog.unshow_busy()
                dialogue.report_any_problems(result)
        open_dialog.destroy()
    def _init_wd_acb(self, _action=None):
        result = ifce.SCM.do_init()
        dialogue.report_any_problems(result)
        ifce.chdir()
    def _clone_repo_acb(self, _action=None):
        clone_dialog = config.RepoSelectDialog(parent=self)
        if clone_dialog.run() == gtk.RESPONSE_OK:
            clone_dialog.hide()
            cloned_path = clone_dialog.get_path()
            if not cloned_path:
                clone_dialog.destroy()
                return
            target = clone_dialog.get_target()
            self.show_busy()
            result = ifce.SCM.do_clone_as(cloned_path, target)
            self.unshow_busy()
            if result[0]:
                dialogue.report_any_problems(result)
                return
            clone_dialog.show_busy()
            result = ifce.chdir(target)
            clone_dialog.unshow_busy()
            dialogue.report_any_problems(result)
            clone_dialog.ap_table.add_ap(cloned_path)
            clone_dialog.destroy()
        else:
            clone_dialog.destroy()
    def _diff_ws_acb(self, _action=None):
        self.show_busy()
        dialog = diff.ScmDiffTextDialog(parent=self)
        self.unshow_busy()
        dialog.show()
    def _commit_ws_acb(self, _action=None):
        self.show_busy()
        dialog = file_tree.ScmCommitDialog(parent=self)
        self.unshow_busy()
        dialog.show()
    def _revert_ws_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_revert_files(dry_run=True)
        self.unshow_busy()
        if cmd_result.is_less_than_error(result):
            if result.stdout:
                is_ok = dialogue.confirm_list_action(result.stdout.splitlines(), _('About to be actioned. OK?'))
                if not is_ok:
                    return
                self.show_busy()
                result = ifce.SCM.do_revert_files(dry_run=False)
                self.unshow_busy()
            else:
                dialogue.inform_user(_('Nothing to revert'))
                return
        dialogue.report_any_problems(result)
    def _tag_ws_acb(self, _action=None):
        self.show_busy()
        change_set.SetTagDialog(parent=self).run()
        self.unshow_busy()
    def _branch_ws_acb(self, _action=None):
        self.show_busy()
        dialog = dialogue.ReadTextDialog(title=_('gwsmhg: Specify Branch'),
            prompt=_('Branch:'), parent=self)
        self.unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
        else:
            branch = dialog.entry.get_text()
            dialog.destroy()
            self.show_busy()
            result = ifce.SCM.do_set_branch(branch=branch)
            self.unshow_busy()
            dialogue.report_any_problems(result)
    def _checkout_ws_acb(self, _action=None):
        self.show_busy()
        dialog = change_set.ChangeSetSelectDialog(discard_toggle=True, parent=self)
        self.unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
        else:
            rev = dialog.get_change_set()
            dialog.destroy()
            if rev:
                discard = dialog.get_discard()
                self.show_busy()
                result = ifce.SCM.do_update_workspace(rev=rev, discard=discard)
                self.unshow_busy()
                dialogue.report_any_problems(result)
    def _update_ws_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_update_workspace(rev=None, discard=False)
        self.unshow_busy()
        if result[0] & cmd_result.SUGGEST_MERGE_OR_DISCARD:
            question = os.linesep.join(result[1:])
            ans = dialogue.ask_merge_discard_or_cancel(question, result[0], parent=self)
            if ans == dialogue.RESPONSE_DISCARD:
                self.show_busy()
                result = ifce.SCM.do_update_workspace(rev=None, discard=True)
                self.unshow_busy()
                dialogue.report_any_problems(result)
            elif ans == dialogue.RESPONSE_MERGE:
                self.show_busy()
                result = ifce.SCM.do_merge_workspace(rev=None, force=False)
                self.unshow_busy()
                if result[0] & cmd_result.SUGGEST_FORCE:
                    if dialogue.ask_force_or_cancel(result, parent=self) == dialogue.RESPONSE_FORCE:
                        self.show_busy()
                        result = ifce.SCM.do_merge_workspace(rev=None, force=True)
                        self.unshow_busy()
                        dialogue.report_any_problems(result)
                else:
                    dialogue.report_any_problems(result)
        else:
            dialogue.report_any_problems(result)
    def _pull_repo_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_pull_from()
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def _merge_ws_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_merge_workspace()
        self.unshow_busy()
        if result[0] & cmd_result.SUGGEST_FORCE:
            if dialogue.ask_force_or_cancel(result) == dialogue.RESPONSE_FORCE:
                self.show_busy()
                result = ifce.SCM.do_merge_workspace(force=True)
                self.unshow_busy()
                dialogue.report_any_problems(result)
        else:
            dialogue.report_any_problems(result)
    def _resolve_ws_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_resolve_workspace()
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def _push_repo_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_push_to()
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def _verify_repo_acb(self, _action=None):
        self.show_busy()
        result = ifce.SCM.do_verify_repo()
        self.unshow_busy()
        dialogue.report_any_problems(result)
    def _refresh_displayed_data_acb(self, _action=None):
        ws_event.notify_events(ws_event.CHANGE_WD)
    def _edit_repo_config_acb(self, _action=None):
        from gwsmhg_pkg import text_edit
        text_edit.edit_files_extern(['.hg/hgrc'])
    def _rollback_repo_acb(self, _action=None):
        question = os.linesep.join([_('About to roll back last transaction'),
                                    _('This action is irreversible! Continue?')])
        if dialogue.ask_yes_no(question, parent=self):
            self.show_busy()
            result = ifce.SCM.do_rollback_repo()
            self.unshow_busy()
            dialogue.report_any_problems(result)
    def _config_editors_acb(self, _action=None):
        config.EditorAllocationDialog(parent=self).show()
