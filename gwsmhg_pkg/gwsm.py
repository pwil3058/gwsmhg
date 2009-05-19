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

import os, gtk, gobject, sys
from gwsmhg_pkg import console, change_set, file_tree, gutils, utils, patch_mgr
from gwsmhg_pkg import icons, path, cmd_result, diff

WS_TABLE_DESCR = \
[
    ["Alias", gobject.TYPE_STRING, True, [("editable", True)]],
    ["Path", gobject.TYPE_STRING, True, []],
]

WS_PATH = gutils.find_label_index(WS_TABLE_DESCR, "Path")
WS_ALIAS = gutils.find_label_index(WS_TABLE_DESCR, "Alias")

GSWMHG_D_NAME = os.sep.join([utils.HOME, ".gwsmhg.d"])
SAVED_WS_FILE_NAME = os.sep.join([GSWMHG_D_NAME, "workspaces"]) 

if not os.path.exists(GSWMHG_D_NAME):
    os.mkdir(GSWMHG_D_NAME, 0775)

class WSPathView(gutils.TableView):
    def __init__(self):
        gutils.TableView.__init__(self, WS_TABLE_DESCR,
                                  sel_mode=gtk.SELECTION_SINGLE,
                                  perm_headers=True)
        self._alias_ctr = self.get_column(WS_ALIAS).get_cell_renderers()[0]
        self._alias_ctr.connect("edited", self._edited_cb, self.get_model())
        self.set_size_request(480, 160)
#        model = self.get_model()
#        model.set_sort_func(WS_ALIAS, self._sort_func, WS_ALIAS)
#        model.set_sort_func(WS_PATH, self._sort_func, WS_PATH)
        self.read_saved_ws_file()
#        model.set_sort_column_id(WS_ALIAS, gtk.SORT_ASCENDING)
#        self.set_headers_clickable(True)
#    def _sort_func(self, model, iter1, iter2, index):
#        v1 = model.get_value(iter1, index)
#        v2 = model.get_value(iter2, index)
#        if v1 < v2:
#            return -1
#        elif v1 > v2:
#            return 1
#        else:
#            return 0
    def read_saved_ws_file(self):
        valid_ws_list = []
        if not os.path.exists(SAVED_WS_FILE_NAME):
            self.set_contents([])
            return
        file = open(SAVED_WS_FILE_NAME, 'r')
        lines = file.readlines()
        file.close()
        for line in lines:
            data = line.strip().split(os.pathsep, 1)
            if os.path.exists(os.path.expanduser(data[WS_PATH])):
                valid_ws_list.append(data)
        self.set_contents(valid_ws_list)
        self._write_list_to_file(valid_ws_list)
        self.get_selection().unselect_all()
    def _write_list_to_file(self, list):
        file = open(SAVED_WS_FILE_NAME, 'w')
        for ws in list:
            file.write(os.pathsep.join(ws))
            file.write(os.linesep)
        file.close()
    def add_ws(self, wspath, alias=""):
        if os.path.exists(wspath):
            store = self.get_model()
            iter = store.get_iter_first()
            while iter:
                if os.path.samefile(os.path.expanduser(store.get_value(iter, WS_PATH)), wspath):
                    if alias:
                        store.set_value(iter, WS_ALIAS, alias)
                    return
                iter = store.iter_next(iter)
            if not alias:
                alias = os.path.basename(wspath)
            data = ["",""]
            data[WS_PATH] = utils.path_rel_home(wspath)
            data[WS_ALIAS] = alias
            store.append(data)
            self.save_to_file()
    def save_to_file(self):
        list = self.get_contents()
        self._write_list_to_file(list)
    def get_selected_ws(self):
        data = self.get_selected_data([WS_PATH, WS_ALIAS])
        return data[0]
    def _edited_cb(self, cell, wspath, new_text, model):
        model[wspath][WS_ALIAS] = new_text
        self.save_to_file()

class WSOpenDialog(gtk.Dialog, gutils.BusyIndicator, gutils.BusyIndicatorUser):
    def __init__(self, parent=None):
        gutils.BusyIndicator.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, self)
        gtk.Dialog.__init__(self, title="gwsmg: Select Workspace/Directory", parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK)
                           )
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        hbox = gtk.HBox()
        self.wspath_view = WSPathView()
        self.wspath_view.get_selection().connect("changed", self._selection_cb)
        hbox.pack_start(gutils.wrap_in_scrolled_window(self.wspath_view))
        self._select_button = gtk.Button(label="_Select")
        self._select_button.connect("clicked", self._select_cb)
        hbox.pack_start(self._select_button, expand=False, fill=False)
        self.vbox.pack_start(hbox)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("Directory:"))
        self._wspath = gutils.EntryWithHistory()
        self._wspath.set_width_chars(32)
        self._wspath.connect("activate", self._wspath_cb)
        hbox.pack_start(self._wspath, expand=True, fill=True)
        self._browse_button = gtk.Button(label="_Browse")
        self._browse_button.connect("clicked", self._browse_cb)
        hbox.pack_start(self._browse_button, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        self.show_all()
        self.wspath_view.get_selection().unselect_all()
    def _selection_cb(self, selection=None):
        self._select_button.set_sensitive(selection.count_selected_rows())
    def _select_cb(self, button=None):
        wspath = self.wspath_view.get_selected_ws()
        self._wspath.set_text(wspath[0])
    def _wspath_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def _browse_cb(self, button=None):
        dirname = gutils.ask_dir_name("gwsmhg: Browse for Directory", existing=True, parent=self)
        if dirname:
            self._wspath.set_text(utils.path_rel_home(dirname))
    def get_wspath(self):
        return os.path.expanduser(self._wspath.get_text())

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
    </placeholder>
  </toolbar>
  <menubar name="gwsm_menubar">
    <menu name="gwsm_wd" action="gwsm_working_directory">
      <menuitem action="gwsm_change_wd"/>
      <menuitem action="gwsm_init_wd"/>
      <menuitem action="gwsm_quit"/>
    </menu>
  </menubar>
</ui>
'''

ALWAYS_AVAILABLE="gwsm_always_avail"
IN_VALID_SCM_REPO="gwsm_in_valid_repo"
NOT_IN_VALID_SCM_REPO="gwsm_not_in_valid_repo"
IN_VALID_SCM_REPO_NOT_PMIC="gwsm_in_valid_repo_not_pmic"

GWSM_CONDITIONS = [ALWAYS_AVAILABLE,
                   IN_VALID_SCM_REPO,
                   NOT_IN_VALID_SCM_REPO,
                   IN_VALID_SCM_REPO_NOT_PMIC,
                  ]

class gwsm(gtk.Window, gutils.BusyIndicator, gutils.BusyIndicatorUser, cmd_result.ProblemReporter):
    def __init__(self, ifce):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        gutils.BusyIndicator.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, self)
        cmd_result.ProblemReporter.__init__(self)
        self.set_icon_from_file(icons.app_icon_file)
        self.connect("destroy", self._quit)
        self._tooltips = gtk.Tooltips()
        self._tooltips.enable()
        self._ifce = ifce(busy_indicator=self.get_busy_indicator(), tooltips=self._tooltips)
        # see if we're in a valid work space and if not offer a selection
        rootdir = self._ifce.SCM.get_root()
        if not rootdir:
            open_dialog = WSOpenDialog()
            if open_dialog.run() == gtk.RESPONSE_OK:
                wspath = open_dialog.get_wspath()
                if wspath:
                    try:
                        os.chdir(wspath)
                        rootdir = self._ifce.SCM.get_root()
                        if rootdir:
                            os.chdir(rootdir)
                            open_dialog.wspath_view.add_ws(rootdir)
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
        for condition in GWSM_CONDITIONS:
            self._action_group[condition] = gtk.ActionGroup(condition)
            self._ui_manager.insert_action_group(self._action_group[condition], -1)
        self._action_group[ALWAYS_AVAILABLE].add_actions(
            [
                ("gwsm_working_directory", None, "_Working Directory"),
                ("gwsm_change_wd", gtk.STOCK_OPEN, "_Open", "",
                 "Change current working directory", self._change_wd_acb),
                ("gwsm_quit", gtk.STOCK_QUIT, "_Quit", "",
                 "Quit", self._quit),
            ])
        self._action_group[NOT_IN_VALID_SCM_REPO].add_actions(
            [
                ("gwsm_init_wd", gtk.STOCK_APPLY, "_Initialise", "",
                 "Initialise the current working directory", self._init_wd_acb),
            ])
        self._action_group[IN_VALID_SCM_REPO].add_actions(
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
        self._action_group[IN_VALID_SCM_REPO_NOT_PMIC].add_actions(
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
            ])
        self._ui_manager.add_ui_from_string(GWSM_UI_DESCR)
        self._menubar = self._ui_manager.get_widget("/gwsm_menubar")
        self._toolbar = self._ui_manager.get_widget("/gwsm_toolbar")
        self._update_sensitivities()
        self._parent_view = change_set.ParentsTableView(self._ifce)
        self._file_tree_widget = file_tree.ScmCwdFilesWidget(ifce=self._ifce,
            busy_indicator=self.get_busy_indicator(), tooltips=self._tooltips)
        self._notebook = gtk.Notebook()
        self._notebook.set_size_request(640, 360)
        self._patch_mgr = patch_mgr.PatchManagementWidget(ifce=self._ifce,
            busy_indicator=self.get_busy_indicator(), tooltips=self._tooltips)
        pmpage = self._notebook.append_page(self._patch_mgr, gtk.Label(self._ifce.PM.name))
        self._heads_view = change_set.HeadsTableView(self._ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._heads_view), gtk.Label("Heads"))
        self._tags_view = change_set.TagsTableView(self._ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._tags_view), gtk.Label("Tags"))
        self._branches_view = change_set.BranchesTableView(self._ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._branches_view), gtk.Label("Branches"))
        self._history_view = change_set.HistoryTableView(self._ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._history_view), gtk.Label("History"))
        self._path_view = path.PathTableView(self._ifce)
        self._notebook.append_page(gutils.wrap_in_scrolled_window(self._path_view), gtk.Label("Paths"))
        self._notebook.set_current_page(pmpage)
        # Now lay the widgets out
        vbox = gtk.VBox()
        vbox.pack_start(self._menubar, expand=False)
        vbox.pack_start(self._parent_view, expand=False)
        vbox.pack_start(self._toolbar, expand=False)
        hpane = gtk.HPaned()
        vbox.pack_start(hpane, expand=True)
        hpane.add1(self._file_tree_widget)
        vpane = gtk.VPaned()
        hpane.add2(vpane)
        vpane.add1(self._notebook)
        vpane.add2(self._ifce.log)
        self.add(vbox)
        self.show_all()
        self._update_title()
        self._parent_view.get_selection().unselect_all()
        self._ifce.PM.add_notification_cb(self._ifce.PM.tag_changing_cmds, self._update_sensitivities)
        if open_dialog:
            open_dialog._unshow_busy()
            open_dialog.destroy()
    def _quit(self, widget):
        gtk.main_quit()
    def _update_title(self):
        self.set_title("gwsm%s: %s" % (self._ifce.SCM.name, utils.path_rel_home(os.getcwd())))
    def _update_sensitivities(self):
        in_valid_repo = self._ifce.SCM.get_root() != None
        if in_valid_repo:
            pm_ic = self._ifce.PM.get_in_progress()
        else:
            pm_ic = False
        self._action_group[NOT_IN_VALID_SCM_REPO].set_sensitive(not in_valid_repo)
        self._action_group[IN_VALID_SCM_REPO].set_sensitive(in_valid_repo)
        self._action_group[IN_VALID_SCM_REPO_NOT_PMIC].set_sensitive(in_valid_repo and not pm_ic)
#    def _change_wd(self, newdir=None):
#        if newdir:
#            os.chdir(newdir)
#        else:
#            newdir = os.getcwd()
#        # This is where'll we get the appropriate SCM interface in later versions
#        newrootdir = self._ifce.SCM.get_root()
#        if newrootdir and newrootdir != newdir:
#            os.chdir(newrootdir)
    def _reset_after_cd(self):
        self._show_busy()
        self._update_sensitivities()
        self._ifce.log.append_entry("New Working Directory: %s" % os.getcwd())
        self._parent_view.update_for_chdir()
        self._history_view.update_for_chdir()
        self._heads_view.update_for_chdir()
        self._tags_view.update_for_chdir()
        self._branches_view.update_for_chdir()
        self._file_tree_widget.update_for_chdir()
        self._patch_mgr.update_for_chdir()
        self._path_view.update_for_chdir()
        self._update_title()
        self._unshow_busy()
    def _change_wd_acb(self, action=None):
        open_dialog = WSOpenDialog(parent=self)
        if open_dialog.run() == gtk.RESPONSE_OK:
            wspath = open_dialog.get_wspath()
            if not wspath:
                open_dialog.destroy()
            else:
                old_wspath = os.getcwd()
                os.chdir(wspath)
                rootdir = self._ifce.SCM.get_root()
                if rootdir:
                    os.chdir(rootdir)
                    open_dialog.wspath_view.add_ws(rootdir)
                    wspath = rootdir
                open_dialog.destroy()
                if not os.path.samefile(old_wspath, os.path.expanduser(wspath)):
                    self._reset_after_cd()
        else:
            open_dialog.destroy()
    def _init_wd_acb(self, action=None):
        result = self._ifce.SCM.do_init()
        self._report_any_problems(result)
        if self._ifce.SCM.get_root():
            file = open(SAVED_WS_FILE_NAME, 'a')
            cwd = utils.path_rel_home(os.getcwd())
            alias = os.path.basename(cwd)
            file.write(os.pathsep.join([alias, cwd]))
            file.write(os.linesep)
            file.close()
    def _diff_ws_acb(self, action=None):
        self._show_busy()
        dialog = diff.ScmDiffTextDialog(parent=self, ifce=self._ifce, modal=False)
        self._unshow_busy()
        dialog.show()
    def _commit_ws_acb(self, action=None):
        self._show_busy()
        dialog = file_tree.ScmCommitDialog(parent=self, ifce=self._ifce)
        self._unshow_busy()
        dialog.show()
    def _tag_ws_acb(self, action=None):
        self._show_busy()
        dialog = gutils.ReadTextAndToggleDialog(title="gwsmhg: Specify Tag",
            prompt="Tag:", toggle_prompt="Local", toggle_state=False, parent=self)
        self._unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
        else:
            tag = dialog.entry.get_text()
            local = dialog.toggle.get_active()
            dialog.destroy()
            self._show_busy()
            result = self._ifce.SCM.do_set_tag(tag=tag, local=local)
            self._unshow_busy()
            self._report_any_problems(result)
    def _branch_ws_acb(self, action=None):
        self._show_busy()
        dialog = gutils.ReadTextDialog(title="gwsmhg: Specify Branch",
            prompt="Branch:", parent=self)
        self._unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
        else:
            branch = dialog.entry.get_text()
            dialog.destroy()
            self._show_busy()
            result = self._ifce.SCM.do_set_branch(branch=branch)
            self._unshow_busy()
            self._report_any_problems(result)
    def _checkout_ws_acb(self, action=None):
        self._show_busy()
        dialog = change_set.ChangeSetSelectDialog(ifce=self._ifce, parent=self)
        self._unshow_busy()
        response = dialog.run()
        if response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
        else:
            rev = dialog.get_change_set()
            dialog.destroy()
            if rev:
                self._show_busy()
                result = self._ifce.SCM.do_update_workspace(rev=rev, clean=False)
                self._unshow_busy()
                self._report_any_problems(result)
    def _update_ws_acb(self, action=None):
        self._show_busy()
        result = self._ifce.SCM.do_update_workspace(rev=None, clean=False)
        self._unshow_busy()
        self._report_any_problems(result)
    def _pull_repo_acb(self, action=None):
        self._show_busy()
        result = self._ifce.SCM.do_pull_from()
        self._unshow_busy()
        self._report_any_problems(result)
    def _push_repo_acb(self, action=None):
        self._show_busy()
        result = self._ifce.SCM.do_push_to()
        self._unshow_busy()
        self._report_any_problems(result)
    def _verify_repo_acb(self, action=None):
        self._show_busy()
        result = self._ifce.SCM.do_verify_repo()
        self._unshow_busy()
        self._report_any_problems(result)

