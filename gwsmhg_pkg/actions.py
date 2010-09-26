### Copyright (C) 2009 Peter Williams <peter_ono@users.sourceforge.net>

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

ON_REPO_INDEP = 'ag_on_repo_indep'
ON_IN_REPO = 'ag_on_in_repo'
ON_NOT_IN_REPO = 'ag_on_not_in_repo'
ON_IN_REPO_PMIC = ON_IN_REPO + '_pmic'
ON_IN_REPO_NOT_PMIC = ON_IN_REPO + '_not_pmic'

CLASS_INDEP_CONDS = [
        ON_REPO_INDEP, ON_IN_REPO, ON_NOT_IN_REPO,
        ON_IN_REPO_PMIC, ON_IN_REPO_NOT_PMIC,
    ]

ON_REPO_INDEP_SELN_INDEP = ON_REPO_INDEP + '_seln_indep'
ON_IN_REPO_SELN_INDEP = ON_IN_REPO + '_seln_indep'
ON_NOT_IN_REPO_SELN_INDEP = ON_NOT_IN_REPO + '_seln_indep'
ON_IN_REPO_PMIC_SELN_INDEP = ON_IN_REPO_PMIC + '_seln_indep'
ON_IN_REPO_NOT_PMIC_SELN_INDEP = ON_IN_REPO_NOT_PMIC + '_seln_indep'

ON_REPO_INDEP_SELN = ON_REPO_INDEP + '_seln'
ON_IN_REPO_SELN = ON_IN_REPO + '_seln'
ON_NOT_IN_REPO_SELN = ON_NOT_IN_REPO + '_seln'
ON_IN_REPO_PMIC_SELN = ON_IN_REPO_PMIC + '_seln'
ON_IN_REPO_NOT_PMIC_SELN = ON_IN_REPO_NOT_PMIC + '_seln'

ON_REPO_INDEP_NO_SELN = ON_REPO_INDEP + '_no_seln'
ON_IN_REPO_NO_SELN = ON_IN_REPO + '_no_seln'
ON_NOT_IN_REPO_NO_SELN = ON_NOT_IN_REPO + '_no_seln'
ON_IN_REPO_PMIC_NO_SELN = ON_IN_REPO_PMIC + '_no_seln'
ON_IN_REPO_NOT_PMIC_NO_SELN = ON_IN_REPO_NOT_PMIC + '_no_seln'

ON_REPO_INDEP_UNIQUE_SELN = ON_REPO_INDEP + '_unique_seln'
ON_IN_REPO_UNIQUE_SELN = ON_IN_REPO + '_unique_seln'
ON_NOT_IN_REPO_UNIQUE_SELN = ON_NOT_IN_REPO + '_unique_seln'
ON_IN_REPO_PMIC_UNIQUE_SELN = ON_IN_REPO_PMIC + '_unique_seln'
ON_IN_REPO_NOT_PMIC_UNIQUE_SELN = ON_IN_REPO_NOT_PMIC + '_unique_seln'

CLASS_DEP_SELN_INDEP_CONDS = [
        ON_REPO_INDEP_SELN_INDEP, ON_IN_REPO_SELN_INDEP,
        ON_NOT_IN_REPO_SELN_INDEP, ON_IN_REPO_PMIC_SELN_INDEP,
        ON_IN_REPO_NOT_PMIC_SELN_INDEP,
    ]

CLASS_DEP_SELN_DEP_CONDS = [
        ON_REPO_INDEP_SELN, ON_IN_REPO_SELN, ON_NOT_IN_REPO_SELN,
        ON_IN_REPO_PMIC_SELN, ON_IN_REPO_NOT_PMIC_SELN,
        ON_REPO_INDEP_NO_SELN, ON_IN_REPO_NO_SELN, ON_NOT_IN_REPO_NO_SELN,
        ON_IN_REPO_PMIC_NO_SELN, ON_IN_REPO_NOT_PMIC_NO_SELN,
        ON_REPO_INDEP_UNIQUE_SELN, ON_IN_REPO_UNIQUE_SELN, ON_NOT_IN_REPO_UNIQUE_SELN,
        ON_IN_REPO_PMIC_UNIQUE_SELN, ON_IN_REPO_NOT_PMIC_UNIQUE_SELN,
    ]

class_indep_ags = {}

import gtk

for condition in CLASS_INDEP_CONDS:
    class_indep_ags[condition] = gtk.ActionGroup(condition)

from gwsmhg_pkg import ifce, ws_event, gutils

def update_class_indep_sensitivities(_arg=None):
    in_repo = ifce.in_valid_repo
    pmic = in_repo and ifce.PM.get_in_progress()
    class_indep_ags[ON_IN_REPO].set_sensitive(in_repo)
    class_indep_ags[ON_NOT_IN_REPO].set_sensitive(not in_repo)
    class_indep_ags[ON_IN_REPO_PMIC].set_sensitive(pmic)
    class_indep_ags[ON_IN_REPO_NOT_PMIC].set_sensitive(in_repo and not pmic)

def add_class_indep_action(cond, action):
    class_indep_ags[cond].add_action(action)

def add_class_indep_actions(cond, actions):
    class_indep_ags[cond].add_actions(actions)

def get_class_indep_action(action_name):
    for cond in CLASS_INDEP_CONDS:
        action = class_indep_ags[cond].get_action(action_name)
        if action:
            return action
    return None

update_class_indep_sensitivities()

ws_event.add_notification_cb(ws_event.CHANGE_WD|ws_event.PMIC_CHANGE,
                             update_class_indep_sensitivities)

class AGandUIManager(ws_event.Listener):
    def __init__(self, selection=None):
        ws_event.Listener.__init__(self)
        self.ui_manager = gutils.UIManager()
        for cond in CLASS_INDEP_CONDS:
            self.ui_manager.insert_action_group(class_indep_ags[cond], -1)
        self.seln = selection
        self._action_groups = {}
        for cond in CLASS_DEP_SELN_INDEP_CONDS:
            self._action_groups[cond] = gtk.ActionGroup(cond)
            self.ui_manager.insert_action_group(self._action_groups[cond], -1)
        if self.seln:
            for cond in CLASS_DEP_SELN_DEP_CONDS:
                self._action_groups[cond] = gtk.ActionGroup(cond)
                self.ui_manager.insert_action_group(self._action_groups[cond], -1)
            self.seln.connect('changed', self._seln_cond_change_cb)
        self.add_notification_cb(ws_event.CHANGE_WD|ws_event.PMIC_CHANGE,
                                 self._event_cond_change_cb)
        self.init_action_states()
    def _seln_cond_change_update(self, seln, in_repo, pmic):
        selsz = seln.count_selected_rows()
        self._action_groups[ON_REPO_INDEP_SELN].set_sensitive(selsz > 0)
        self._action_groups[ON_REPO_INDEP_NO_SELN].set_sensitive(selsz == 0)
        self._action_groups[ON_REPO_INDEP_UNIQUE_SELN].set_sensitive(selsz == 1)
        if in_repo:
            self._action_groups[ON_IN_REPO_SELN].set_sensitive(selsz > 0)
            self._action_groups[ON_IN_REPO_NO_SELN].set_sensitive(selsz == 0)
            self._action_groups[ON_IN_REPO_UNIQUE_SELN].set_sensitive(selsz == 1)
            for cond in [ON_NOT_IN_REPO_SELN, ON_NOT_IN_REPO_NO_SELN, ON_NOT_IN_REPO_UNIQUE_SELN]:
                self._action_groups[cond].set_sensitive(False)
            if pmic:
                self._action_groups[ON_IN_REPO_PMIC_SELN].set_sensitive(selsz > 0)
                self._action_groups[ON_IN_REPO_PMIC_NO_SELN].set_sensitive(selsz == 0)
                self._action_groups[ON_IN_REPO_PMIC_UNIQUE_SELN].set_sensitive(selsz == 1)
                for cond in [ON_IN_REPO_NOT_PMIC_SELN, ON_IN_REPO_NOT_PMIC_NO_SELN, ON_IN_REPO_NOT_PMIC_UNIQUE_SELN]:
                    self._action_groups[cond].set_sensitive(False)
            else:
                self._action_groups[ON_IN_REPO_NOT_PMIC_SELN].set_sensitive(selsz > 0)
                self._action_groups[ON_IN_REPO_NOT_PMIC_NO_SELN].set_sensitive(selsz == 0)
                self._action_groups[ON_IN_REPO_NOT_PMIC_UNIQUE_SELN].set_sensitive(selsz == 1)
                for cond in [ON_IN_REPO_PMIC_SELN, ON_IN_REPO_PMIC_NO_SELN, ON_IN_REPO_PMIC_UNIQUE_SELN]:
                    self._action_groups[cond].set_sensitive(False)
        else:
            self._action_groups[ON_NOT_IN_REPO_SELN].set_sensitive(selsz > 0)
            self._action_groups[ON_NOT_IN_REPO_NO_SELN].set_sensitive(selsz == 0)
            self._action_groups[ON_NOT_IN_REPO_UNIQUE_SELN].set_sensitive(selsz == 1)
            for cond in [ON_IN_REPO_SELN, ON_IN_REPO_NO_SELN, ON_IN_REPO_UNIQUE_SELN]:
                self._action_groups[cond].set_sensitive(False)
            for cond in [ON_IN_REPO_NOT_PMIC_SELN, ON_IN_REPO_NOT_PMIC_NO_SELN, ON_IN_REPO_NOT_PMIC_UNIQUE_SELN]:
                self._action_groups[cond].set_sensitive(False)
            for cond in [ON_IN_REPO_PMIC_SELN, ON_IN_REPO_PMIC_NO_SELN, ON_IN_REPO_PMIC_UNIQUE_SELN]:
                self._action_groups[cond].set_sensitive(False)
    def _seln_cond_change_cb(self, seln):
        in_repo = ifce.in_valid_repo
        pmic = in_repo and ifce.PM.get_in_progress()
        self._seln_cond_change_update(seln, in_repo, pmic)
    def _event_cond_change_cb(self, arg=None):
        in_repo = ifce.in_valid_repo
        pmic = in_repo and ifce.PM.get_in_progress()
        self._action_groups[ON_IN_REPO_SELN_INDEP].set_sensitive(in_repo)
        self._action_groups[ON_NOT_IN_REPO_SELN_INDEP].set_sensitive(not in_repo)
        self._action_groups[ON_IN_REPO_PMIC_SELN_INDEP].set_sensitive(pmic)
        self._action_groups[ON_IN_REPO_NOT_PMIC_SELN_INDEP].set_sensitive(in_repo and not pmic)
        if self.seln:
            self._seln_cond_change_update(self.seln, in_repo, pmic)
    def add_new_action_group(self, cond):
        self._action_groups[cond] = gtk.ActionGroup(cond)
        self.ui_manager.insert_action_group(self._action_groups[cond], -1)
    def add_conditional_action(self, cond, action):
        self._action_groups[cond].add_action(action)
    def add_conditional_actions(self, cond, actions):
        self._action_groups[cond].add_actions(actions)
    def get_conditional_action(self, action_name):
        conditions = CLASS_DEP_SELN_INDEP_CONDS[:]
        if self.seln:
            conditions += CLASS_DEP_SELN_DEP_CONDS
        for cond in conditions:
            action = self._action_groups[cond].get_action(action_name)
            if action:
                return action
    def copy_conditional_action(self, action_name, new_cond):
        conditions = CLASS_DEP_SELN_INDEP_CONDS[:]
        if self.seln:
            conditions += CLASS_DEP_SELN_DEP_CONDS
        for cond in conditions:
            action = self._action_groups[cond].get_action(action_name)
            if action:
                self._action_groups[new_cond].add_action(action)
                return
    def move_conditional_action(self, action_name, new_cond):
        conditions = CLASS_DEP_SELN_INDEP_CONDS[:]
        if self.seln:
            conditions += CLASS_DEP_SELN_DEP_CONDS
        for cond in conditions:
            action = self._action_groups[cond].get_action(action_name)
            if action:
                self._action_groups[cond].remove_action(action)
                self._action_groups[new_cond].add_action(action)
                return
    def init_action_states(self):
        self._event_cond_change_cb()
    def create_action_button(self, action_name, use_underline=True):
        action = self.get_conditional_action(action_name)
        return gutils.ActionButton(action, use_underline=use_underline)
    def create_action_button_box(self, action_name_list, use_underline=True,
                                 horizontal=True,
                                 expand=True, fill=True, padding=0):
        if horizontal:
            box = gtk.HBox()
        else:
            box = gtk.VBox()
        for action_name in action_name_list:
            button = self.create_action_button(action_name, use_underline)
            box.pack_start(button, expand, fill, padding)
        return box
