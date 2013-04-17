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
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import gtk
from gwsmhg_pkg import utils, dialogue, icons, ws_event, actions, cmd_result

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

IS_AVAILABLE = utils.which('hgtk') is not None

def _action_tool_name(action):
    dummy, name = action.get_name().split('_')
    return name

def _notify_event_by_name(name):
    if name in ['commit', 'rename', 'status', 'merge', 'recovery', 'update', ]:
        ws_event.notify_events(ws_event.FILE_CHANGES)
    elif name in ['commit', 'merge', ]:
        ws_event.notify_events(ws_event.REPO_MOD)
    elif name in ['repoconfig', 'clone', 'init', ]:
        ws_event.notify_events(ws_event.REPO_HGRC)
    elif name in ['userconfig', ]:
        ws_event.notify_events(ws_event.USER_HGRC)
    elif name in ['log', 'merge', 'recovery', 'update', ]:
        ws_event.notify_events(ws_event.CHECKOUT)
    elif name in ['init', 'clone', ]:
        ws_event.notify_events(ws_event.CHANGE_WD)

def _tortoise_tool_modal_acb(action):
    name = _action_tool_name(action)
    cmd = 'hgtk %s' % name
    result = utils.run_cmd(cmd)
    dialogue.report_any_problems(result)
    _notify_event_by_name(name)

def _tortoise_tool_bgnd_acb(action):
    name = _action_tool_name(action)
    cmd = 'hgtk %s' % name
    if not utils.run_cmd_in_bgnd(cmd):
        dialogue.report_any_problems(cmd_result.Result(cmd_result.ERROR, '"%s" failed' % cmd, ''))

actions.add_class_indep_actions(actions.Condns.DONT_CARE, [
        ('gwsm_tortoise', None, _('_Tortoise Tools')),
        ('tortoise_recovery', icons.STOCK_RECOVERY, _('Recovery'), '',
         _('Launch tortoise "recovery" tool'), _tortoise_tool_modal_acb),
        ('tortoise_userconfig', icons.STOCK_CONFIG, _('Userconfig'), '',
         _('Launch tortoise "userconfig" tool'), _tortoise_tool_bgnd_acb),
    ])

actions.add_class_indep_actions(actions.Condns.NOT_IN_REPO, [
        ('tortoise_clone', icons.STOCK_CLONE, _('Clone'), '',
         _('Launch tortoise "clone" tool'), _tortoise_tool_modal_acb),
        ('tortoise_init', icons.STOCK_INIT,_('Init'),'',
         _('Launch tortoise "init" tool'), _tortoise_tool_modal_acb),
    ])

actions.add_class_indep_actions(actions.Condns.IN_REPO, [
        ('tortoise_datamine', gtk.STOCK_EXECUTE, _('Datamine'), '',
         _('Launch tortoise "datamine" tool'), _tortoise_tool_bgnd_acb),
        ('tortoise_guess', icons.STOCK_GUESS, _('Guess'), '',
         _('Launch tortoise "guess" tool'), _tortoise_tool_bgnd_acb),
        ('tortoise_log', icons.STOCK_LOG, _('Log'), '',
         _('Launch tortoise "log" tool'), _tortoise_tool_modal_acb),
        ('tortoise_repoconfig', icons.STOCK_CONFIG, _('Repoconfig'), '',
         _('Launch tortoise "repoconfig" tool'), _tortoise_tool_modal_acb),
        ('tortoise_serve', icons.STOCK_SERVE, _('Serve'), '',
         _('Launch tortoise "serve" tool'), _tortoise_tool_modal_acb),
        ('tortoise_shelve', icons.STOCK_SHELVE, _('Shelve'), '',
         _('Launch tortoise "shelve" tool'), _tortoise_tool_modal_acb),
    ])

actions.add_class_indep_actions(actions.Condns.IN_REPO + actions.Condns.NOT_PMIC, [
        ('tortoise_commit', icons.STOCK_COMMIT, _('Commit'), '',
         _('Launch tortoise "commit" tool'), _tortoise_tool_modal_acb),
        ('tortoise_merge', icons.STOCK_MERGE, _('Merge'), '',
         _('Launch tortoise "merge" tool'), _tortoise_tool_modal_acb),
        ('tortoise_status', icons.STOCK_STATUS, _('Status'), '',
         _('Launch tortoise "status" tool'), _tortoise_tool_modal_acb),
        ('tortoise_synch', icons.STOCK_SYNCH, _('Synch'), '',
         _('Launch tortoise "synch" tool'), _tortoise_tool_modal_acb),
        ('tortoise_update', icons.STOCK_UPDATE, _('Update'), '',
         _('Launch tortoise "update" tool'), _tortoise_tool_modal_acb),
    ])

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

FILE_MENU = gtk.Action("tortoise_files_menu", _('_Tortoise'), None, None)

FILE_GROUP_PARTIAL_ACTIONS = {
    actions.Condns.IN_REPO + actions.Condns.UNIQUE_SELN: \
    [
        ('tortoise_rename', icons.STOCK_RENAME, _('Rename'), '',
         _('Launch tortoise "rename" tool')),
    ], \
    actions.Condns.IN_REPO + actions.Condns.NOT_PMIC + actions.Condns.SELN: \
    [
        ('tortoise_commit', icons.STOCK_COMMIT, _('Commit'), '',
         _('Launch tortoise "commit" tool')),
        ('tortoise_status', icons.STOCK_STATUS, _('Status'), '',
         _('Launch tortoise "status" tool')),
    ],
}

def run_tool_for_files(action, file_list):
    name = _action_tool_name(action)
    cmd = 'hgtk %s %s' % (name, utils.file_list_to_string(file_list))
    result = utils.run_cmd(cmd)
    dialogue.report_any_problems(result)
    _notify_event_by_name(name)

