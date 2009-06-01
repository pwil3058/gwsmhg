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

import gtk
from gwsmhg_pkg import utils, cmd_result, icons, const

TORTOISE_HGTK_UI = \
'''
<ui>
  <toolbar name='gwsm_toolbar'/>
  <menubar name='gwsm_menubar'>
    <menu name='gwsm_tortoise' action='gwsm_tortoise'>
      <menuitem action='tortoise_clone'/>
      <menuitem action='tortoise_commit'/>
      <menuitem action='tortoise_datamine'/>
      <menuitem action='tortoise_guess'/>
      <menuitem action='tortoise_init'/>
      <menuitem action='tortoise_log'/>
      <menuitem action='tortoise_merge'/>
      <menuitem action='tortoise_recovery'/>
      <menuitem action='tortoise_repoconfig'/>
      <menuitem action='tortoise_serve'/>
      <menuitem action='tortoise_shelve'/>
      <menuitem action='tortoise_status'/>
      <menuitem action='tortoise_synch'/>
      <menuitem action='tortoise_update'/>
      <menuitem action='tortoise_userconfig'/>
    </menu>
  </menubar>
</ui>
'''

tool_list = ['rename', 'clone', 'commit', 'datamine', 'guess', 'init',
             'log', 'merge', 'recovery', 'repoconfig', 'serve', 'shelve',
             'status', 'synch', 'update', 'userconfig', ]

file_changers = ['commit', 'rename', 'status', 'merge', 'recovery', 'update', ]
tag_changers = ['commit', 'merge', ]
path_changers = ['repoconfig', 'userconfig', 'clone', 'init', ]
cwd_changers = ['init', 'clone', ]
parent_changers = ['log', 'merge', 'recovery', 'update', ]

is_available = utils.which('hgtk') is not None

action_notifier = utils.action_notifier()

_problem_reporter = cmd_result.ProblemReporter()

def action_tool_name(action):
    dummy, name = action.get_name().split('_')
    return name

def _tortoise_tool_modal_acb(action):
    name = action_tool_name(action)
    cmd = 'hgtk %s' % name
    result = utils.run_cmd(cmd)
    _problem_reporter._report_any_problems(result)
    action_notifier._do_cmd_notification(name)

def _tortoise_tool_bgnd_acb(action):
    name = action_tool_name(action)
    cmd = 'hgtk %s' % name
    if not utils.run_cmd_in_bgnd(cmd):
        _problem_reporter._report_any_problems((cmd_result.ERROR, '"%s" failed' % cmd, ''))

main_group_actions = {}

for condition in const.GWSM_CONDITIONS:
    main_group_actions[condition] = []

main_group_actions[const.ALWAYS_AVAILABLE] = \
    [
        ('gwsm_tortoise', None, '_Tortoise Tools'),
        ('tortoise_recovery', icons.STOCK_RECOVERY, 'Recovery', '',
         'Launch tortoise "recovery" tool', _tortoise_tool_modal_acb),
        ('tortoise_userconfig', icons.STOCK_CONFIG, 'Userconfig', '',
         'Launch tortoise "userconfig" tool', _tortoise_tool_bgnd_acb),
    ]

main_group_actions[const.NOT_IN_VALID_SCM_REPO] = \
    [
        ('tortoise_clone', icons.STOCK_CLONE, 'Clone', '',
         'Launch tortoise "clone" tool', _tortoise_tool_modal_acb),
        ('tortoise_init', icons.STOCK_INIT,'Init','',
         'Launch tortoise "init" tool', _tortoise_tool_modal_acb),
    ]

main_group_actions[const.IN_VALID_SCM_REPO] = \
    [
        ('tortoise_datamine', gtk.STOCK_EXECUTE, 'Datamine', '',
         'Launch tortoise "datamine" tool', _tortoise_tool_bgnd_acb),
        ('tortoise_guess', icons.STOCK_GUESS, 'Guess', '',
         'Launch tortoise "guess" tool', _tortoise_tool_bgnd_acb),
        ('tortoise_log', icons.STOCK_LOG, 'Log', '',
         'Launch tortoise "log" tool', _tortoise_tool_modal_acb),
        ('tortoise_repoconfig', icons.STOCK_CONFIG, 'Repoconfig', '',
         'Launch tortoise "repoconfig" tool', _tortoise_tool_modal_acb),
        ('tortoise_serve', icons.STOCK_SERVE, 'Serve', '',
         'Launch tortoise "serve" tool', _tortoise_tool_modal_acb),
        ('tortoise_shelve', icons.STOCK_SHELVE, 'Shelve', '',
         'Launch tortoise "shelve" tool', _tortoise_tool_modal_acb),
    ]

main_group_actions[const.IN_VALID_SCM_REPO_NOT_PMIC] = \
    [
        ('tortoise_commit', icons.STOCK_COMMIT, 'Commit', '',
         'Launch tortoise "commit" tool', _tortoise_tool_modal_acb),
        ('tortoise_merge', icons.STOCK_MERGE, 'Merge', '',
         'Launch tortoise "merge" tool', _tortoise_tool_modal_acb),
        ('tortoise_status', icons.STOCK_STATUS, 'Status', '',
         'Launch tortoise "status" tool', _tortoise_tool_modal_acb),
        ('tortoise_synch', icons.STOCK_SYNCH, 'Synch', '',
         'Launch tortoise "synch" tool', _tortoise_tool_modal_acb),
        ('tortoise_update', icons.STOCK_UPDATE, 'Update', '',
         'Launch tortoise "update" tool', _tortoise_tool_modal_acb),
    ]

FILES_UI_DESCR = \
'''
<ui>
  <menubar name="files_menubar">
    <menu name="tortoise_files_menu" action="tortoise_files_menu">
      <menuitem action="tortoise_commit"/>
      <menuitem action="tortoise_rename"/>
      <menuitem action="tortoise_status"/>
    </menu>
  </menubar>
</ui>
'''

from gwsmhg_pkg.const import NO_SELECTION, UNIQUE_SELECTION, SELECTION, \
    SELECTION_INDIFFERENT, NO_SELECTION_NOT_PATCHED, SELECTION_NOT_PATCHED, \
    FILE_CONDITIONS

file_group_partial_actions = {}

for condition in const.FILE_CONDITIONS:
    file_group_partial_actions[condition] = []
    
file_menu = gtk.Action("tortoise_files_menu", "_Tortoise", None, None)

file_group_partial_actions[UNIQUE_SELECTION] = \
    [
        ('tortoise_rename', icons.STOCK_RENAME, 'Rename', '',
         'Launch tortoise "rename" tool'),
    ]

file_group_partial_actions[SELECTION_NOT_PATCHED] = \
    [
        ('tortoise_commit', icons.STOCK_COMMIT, 'Commit', '',
         'Launch tortoise "commit" tool'),
        ('tortoise_status', icons.STOCK_STATUS, 'Status', '',
         'Launch tortoise "status" tool'),
    ]

def run_tool_for_files(action, file_list):
    name = action_tool_name(action)
    cmd = 'hgtk %s %s' % (name, " ".join(file_list))
    result = utils.run_cmd(cmd)
    _problem_reporter._report_any_problems(result)
    action_notifier._do_cmd_notification(name)
