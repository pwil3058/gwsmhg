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

import os, gtk, gobject, sys
from gwsmhg_pkg import ifce, console, change_set, file_tree, gutils, utils
from gwsmhg_pkg import icons, path, cmd_result, diff, config, tortoise, const
from gwsmhg_pkg import ws_event, patch_mgr, pbranch

GWSM_UI_DESCR = \
'''
<ui>
  <toolbar name="gwsm_toolbar">
    <placeholder name="gwsm_ws_tools">
      <toolitem name="Diff" action="gwsm_diff_ws"/>
      <toolitem name="Commit" action="gwsm_commit_ws"/>
      <toolitem name="Tag" action="gwsm_tag_ws"/>
      <toolitem name="Branch" action="gwsm_branch_ws"/>
      <toolitem name="Checkout" action="gwsm_checkout_ws"/>
      <toolitem name="Update" action="gwsm_update_ws"/>
    </placeholder>
    <separator/>
    <placeholder name="gwsm_repo_tools">
      <toolitem name="Pull" action="gwsm_pull_repo"/>
      <toolitem name="Push" action="gwsm_push_repo"/>
      <toolitem name="Verify" action="gwsm_verify_repo"/>
      <separator/>
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
  </menubar>
  <menubar name="gwsm_right_side_menubar">
    <menu name="gwsm_config" action="gwsm_configuration">
      <menuitem action="gwsm_config_editors"/>
    </menu>
  </menubar>
</ui>
'''

class gwsm(gtk.Window, cmd_result.ProblemReporter):
    def __init__(self, ifce_module):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        ifce.init(ifce_module, console.ConsoleLog(), self)
        cmd_result.ProblemReporter.__init__(self)
        self.set_icon_from_file(icons.app_icon_file)
        self.connect("destroy", self._quit)
        # see if we're in a valid work space and if not offer a selection
        rootdir = ifce.SCM.get_root()
        if not rootdir:
            open_dialog = config.WSOpenDialog()
            if open_dialog.run() == gtk.RESPONSE_OK:
                wspath = open_dialog.get_path()
                if wspath:
                    try:
                        os.chdir(wspath)
                        rootdir = ifce.SCM.get_root()
                        if rootdir:
                            os.chdir(rootdir)
                            open_dialog.ap_view.add_ap(rootdir)
                    except:
                        pass
            else:
                sys.exit()
            open_dialog._show_busy()
        else:
            os.chdir(rootdir)
            open_dialog = None # we need this later
        self._action_group = {}
        self._ui_manager = gtk.UIManager()
        for condition in const.GWSM_CONDITIONS:
            self._action_group[condition] = gtk.ActionGroup(condition)
            self._ui_manager.insert_action_group(self._action_group[condition], -1)
        self._action_group[const.ALWAYS_AVAILABLE].add_actions(
            [
                ("gwsm_working_directory", None, "_Working Directory"),
                ("gwsm_configuration", None, "_Configuration"),
                ("gwsm_change_wd", gtk.STOCK_OPEN, "_Open", "",
                 "Change current working directory", self._change_wd_acb),
                ("gwsm_config_editors", gtk.STOCK_PREFERENCES, "_Editor Allocation", "",
                 "Allocate editors to file types", self._config_editors_acb),
                ("gwsm_quit", gtk.STOCK_QUIT, "_Quit", "",
                 "Quit", self._quit),
            ])
        self._action_group[const.NOT_IN_VALID_SCM_REPO].add_actions(
            [
                ("gwsm_init_wd", icons.STOCK_INIT, "_Initialise", "",
                 "Initialise the current working directory", self._init_wd_acb),
                ("gwsm_clone_repo_in_wd", icons.STOCK_CLONE, "_Clone", "",
                 "Clone a repository cd into the resultant working directory",
                 self._clone_repo_acb),
            ])
        self._action_group[const.IN_VALID_SCM_REPO].add_actions(
            [
                ("gwsm_diff_ws", icons.STOCK_DIFF, "Diff", "",
                 "View diff(s) for the current working directory",
                 self._diff_ws_acb),
                ("gwsm_pull_repo", icons.STOCK_PULL, "Pull", "",
                 "Pull all available changes from the default path",
                 self._pull_repo_acb),
                ("gwsm_verify_repo", icons.STOCK_VERIFY, "Verify", "",
                 "Verify the integrity of the repository",
                 self._verify_repo_acb),
            ])
        self._action_group[const.IN_VALID_SCM_REPO_NOT_PMIC].add_actions(
            [
                ("gwsm_commit_ws", icons.STOCK_COMMIT, "Commit", "",
                 "Commit all changes in the current working directory", 
                 self._commit_ws_acb),
                ("gwsm_tag_ws", icons.STOCK_TAG, "Tag", "",
                 "Tag the parent of the current working directory", 
                 self._tag_ws_acb),
                ("gwsm_branch_ws", icons.STOCK_BRANCH, "Branch", "",
                 "Set the branch for the current working directory", 
                 self._branch_ws_acb),
                ("gwsm_checkout_ws", icons.STOCK_CHECKOUT, "Checkout", "",
                 "Check out a different revision in the current working directory", 
                 self._checkout_ws_acb),
                ("gwsm_update_ws", icons.STOCK_UPDATE, "Update", "",
                 "Update the current working directory to the tip of the current branch", 
                 self._update_ws_acb),
                ("gwsm_push_repo", icons.STOCK_PUSH, "Push", "",
                 "Push all available changes to the default path",
                 self._push_repo_acb),
                ("gwsm_rollback_repo", icons.STOCK_ROLLBACK, "Rollback", "",
                 "Roll back the last transaction",
                 self._rollback_repo_acb),
            ])
        self._ui_manager.add_ui_from_string(GWSM_UI_DESCR)
        if tortoise.is_available:
            for condition in const.GWSM_CONDITIONS:
                self._action_group[condition].add_actions(tortoise.main_group_actions[condition])
            self._ui_manager.add_ui_from_string(tortoise.TORTOISE_HGTK_UI)
        self._menubar = self._ui_manager.get_widget("/gwsm_menubar")
        self._rhs_menubar = self._ui_manager.get_widget("/gwsm_right_side_menubar")
        self._toolbar = self._ui_manager.get_widget("/gwsm_toolbar")
        self._update_sensitivities()
        self._parent_view = change_set.ParentsTableView()
        self._file_tree_widget = file_tree.ScmCwdFilesWidget()
        self._notebook = gtk.Notebook()
        self._notebook.set_size_request(640, 360)
        self._patch_mgr = patch_mgr.PatchManagementWidget()
        pmpage = self._notebook.append_page(self._patch_mgr, gtk.Label(ifce.PM.name))
        self._heads_view = change_set.HeadsTableView()
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._heads_view), gtk.Label("Heads"))
        self._tags_view = change_set.TagsTableView()
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._tags_view), gtk.Label("Tags"))
        self._branches_view = change_set.BranchesTableView()
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._branches_view), gtk.Label("Branches"))
        self._history_view = change_set.HistoryTableView()
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._history_view), gtk.Label("History"))
        self._path_view = path.PathTableView()
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._path_view), gtk.Label("Paths"))
        if ifce.SCM.get_extension_enabled('pbranch'):
            self._pbranch = pbranch.PBranchTable()
            self._notebook.append_page(self._pbranch, gtk.Label("PBranch"))
        self._notebook.set_current_page(pmpage)
        # Now lay the widgets out
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        hbox.pack_start(self._menubar, expand=False)
        hbox.pack_end(self._rhs_menubar, expand=False)
        vbox.pack_start(hbox, expand=False)
        vbox.pack_start(self._parent_view, expand=False)
        vbox.pack_start(self._toolbar, expand=False)
        hpane = gtk.HPaned()
        vbox.pack_start(hpane, expand=True)
        hpane.add1(self._file_tree_widget)
        vpane = gtk.VPaned()
        hpane.add2(vpane)
        vpane.add1(self._notebook)
        vpane.add2(ifce.log)
        self.add(vbox)
        self.show_all()
        self._update_title()
        self._parent_view.get_selection().unselect_all()
        ws_event.add_notification_cb(ws_event.PMIC_CHANGE, self._update_sensitivities)
        if open_dialog:
            open_dialog._unshow_busy()
            open_dialog.destroy()
    def _quit(self, widget):
        gtk.main_quit()
    def _update_title(self):
        self.set_title("gwsm%s: %s" % (ifce.SCM.name, utils.path_rel_home(os.getcwd())))
    def _update_sensitivities(self):
        in_valid_repo = ifce.SCM.get_root() != None
        if in_valid_repo:
            pm_ic = ifce.PM.get_in_progress()
        else:
            pm_ic = False
        self._action_group[const.NOT_IN_VALID_SCM_REPO].set_sensitive(not in_valid_repo)
        self._action_group[const.IN_VALID_SCM_REPO].set_sensitive(in_valid_repo)
        self._action_group[const.IN_VALID_SCM_REPO_NOT_PMIC].set_sensitive(in_valid_repo and not pm_ic)
#    def _change_wd(self, newdir=None):
#        if newdir:
#            os.chdir(newdir)
#        else:
#            newdir = os.getcwd()
#        # This is where'll we get the appropriate SCM interface in later versions
#        newrootdir = ifce.SCM.get_root()
#        if newrootdir and newrootdir != newdir:
#            os.chdir(newrootdir)
    def _reset_after_cd(self):
        ifce.show_busy()
        self._update_sensitivities()
        ifce.log.append_entry("New Working Directory: %s" % os.getcwd())
        self._parent_view.update_for_chdir()
        self._history_view.update_for_chdir()
        self._heads_view.update_for_chdir()
        self._tags_view.update_for_chdir()
        self._branches_view.update_for_chdir()
        self._file_tree_widget.update_for_chdir()
        self._patch_mgr.update_for_chdir()
        self._path_view.update_for_chdir()
        if ifce.SCM.get_extension_enabled('pbranch'):
            self._pbranch.update_for_chdir()
        self._update_title()
        ifce.unshow_busy()
    def _change_wd_acb(self, action=None):
        open_dialog = config.WSOpenDialog(parent=self)
        if open_dialog.run() == gtk.RESPONSE_OK:
            wspath = open_dialog.get_path()
            if not wspath:
                open_dialog.destroy()
            else:
                old_wspath = os.getcwd()
                os.chdir(wspath)
                rootdir = ifce.SCM.get_root()
                if rootdir:
                    os.chdir(rootdir)
                    open_dialog.ap_view.add_ap(rootdir)
                    wspath = rootdir
                open_dialog.destroy()
                if not os.path.samefile(old_wspath, os.path.expanduser(wspath)):
                    self._reset_after_cd()
        else:
            open_dialog.destroy()
    def _init_wd_acb(self, action=None):
        result = ifce.SCM.do_init()
        self._report_any_problems(result)
        if ifce.SCM.get_root():
            config.append_saved_ws(path=os.getcwd())
    def _clone_repo_acb(self, action=None):
        clone_dialog = config.RepoSelectDialog(parent=self)
        if clone_dialog.run() == gtk.RESPONSE_OK:
            clone_dialog.hide()
            cloned_path = clone_dialog.get_path()
            if not cloned_path:
                clone_dialog.destroy()
                return
            target = clone_dialog.get_target()
            ifce.show_busy()
            result = ifce.SCM.do_clone_as(cloned_path, target)
            ifce.unshow_busy()
            if result[0]:
                self._report_any_problems(result)
                return
            os.chdir(target)
            config.append_saved_ws(path=os.getcwd(), alias=target)
            self._reset_after_cd()
            clone_dialog.ap_view.add_ap(cloned_path)
            clone_dialog.destroy()
        else:
            clone_dialog.destroy()
    def _diff_ws_acb(self, action=None):
        ifce.show_busy()
        dialog = diff.ScmDiffTextDialog(parent=self, modal=False)
        ifce.unshow_busy()
        dialog.show()
    def _commit_ws_acb(self, action=None):
        ifce.show_busy()
        dialog = file_tree.ScmCommitDialog(parent=self)
        ifce.unshow_busy()
        dialog.show()
    def _tag_ws_acb(self, action=None):
        ifce.show_busy()
        change_set.SetTagDialog(parent=self).run()
        ifce.unshow_busy()
    def _branch_ws_acb(self, action=None):
        ifce.show_busy()
        dialog = gutils.ReadTextDialog(title="gwsmhg: Specify Branch",
            prompt="Branch:", parent=self)
        ifce.unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
        else:
            branch = dialog.entry.get_text()
            dialog.destroy()
            ifce.show_busy()
            result = ifce.SCM.do_set_branch(branch=branch)
            ifce.unshow_busy()
            self._report_any_problems(result)
    def _checkout_ws_acb(self, action=None):
        ifce.show_busy()
        dialog = change_set.ChangeSetSelectDialog(discard_toggle=True, parent=self)
        ifce.unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
        else:
            rev = dialog.get_change_set()
            dialog.destroy()
            if rev:
                discard = dialog.get_discard()
                ifce.show_busy()
                result = ifce.SCM.do_update_workspace(rev=rev, discard=discard)
                ifce.unshow_busy()
                self._report_any_problems(result)
    def _update_ws_acb(self, action=None):
        ifce.show_busy()
        result = ifce.SCM.do_update_workspace(rev=None, discard=False)
        ifce.unshow_busy()
        if result[0] & cmd_result.SUGGEST_MERGE_OR_DISCARD:
            question = os.linesep.join(result[1:])
            ans = gutils.ask_merge_discard_or_cancel(question, result[0], parent=self)
            if ans == gutils.DISCARD:
                ifce.show_busy()
                result = ifce.SCM.do_update_workspace(rev=None, discard=True)
                ifce.unshow_busy()
                self._report_any_problems(result)
            elif ans == gutils.MERGE:
                ifce.show_busy()
                result = ifce.SCM.do_merge_workspace(rev=None, force=False)
                ifce.unshow_busy()
                if result[0] & cmd_result.SUGGEST_FORCE:
                    question = os.linesep.join(result[1:])
                    ans = gutils.ask_force_or_cancel(question, parent=self)
                    if ans == gutils.FORCE:
                        ifce.show_busy()
                        result = ifce.SCM.do_merge_workspace(rev=None, force=True)
                        ifce.unshow_busy()
                        self._report_any_problems(result)
                else:
                    self._report_any_problems(result)
        else:
            self._report_any_problems(result)
    def _pull_repo_acb(self, action=None):
        ifce.show_busy()
        result = ifce.SCM.do_pull_from()
        ifce.unshow_busy()
        self._report_any_problems(result)
    def _push_repo_acb(self, action=None):
        ifce.show_busy()
        result = ifce.SCM.do_push_to()
        ifce.unshow_busy()
        self._report_any_problems(result)
    def _verify_repo_acb(self, action=None):
        ifce.show_busy()
        result = ifce.SCM.do_verify_repo()
        ifce.unshow_busy()
        self._report_any_problems(result)
    def _rollback_repo_acb(self, action=None):
        question = os.linesep.join(['About to roll back last transaction',
                                    'This action is irreversible! Continue?'])
        if gutils.ask_yes_no(question, parent=self):
            ifce.show_busy()
            result = ifce.SCM.do_rollback_repo()
            ifce.unshow_busy()
            self._report_any_problems(result)
    def _config_editors_acb(self, action=None):
        config.EditorAllocationDialog(self).show()

