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

SCM = None
PM = None
in_valid_repo = False

import os

from gwsmhg_pkg import console, ws_event, cmd_result, terminal

log = None

def init(ifce_module):
    global SCM, PM, in_valid_repo
    SCM = ifce_module.SCMInterface()
    PM = ifce_module.PMInterface()
    root = SCM.get_root()
    if root:
        os.chdir(root)
        in_valid_repo = True
    else:
        in_valid_repo = False

def create_log(busy_indicator):
    global log
    log = console.ConsoleLog(busy_indicator=busy_indicator, runentry=not terminal.AVAILABLE)
    return log

if terminal.AVAILABLE:
    term = terminal.Terminal()
else:
    term = None

def chdir(newdir=None):
    global in_valid_repo
    if newdir:
        # TODO: pass error message if this fails
        try:
            os.chdir(newdir)
        except OSError, err:
            import errno
            ecode = errno.errorcode[err.errno]
            emsg = err.strerror
            return (cmd_result.ERROR, '', '%s: "%s" :%s' % (ecode, newdir, emsg))
    root = SCM.get_root()
    if root:
        os.chdir(root)
        in_valid_repo = True
        from gwsmhg_pkg import config
        config.append_saved_ws(root)
    else:
        in_valid_repo = False
    ws_event.notify_events(ws_event.CHANGE_WD)
    new_wd = os.getcwd()
    if term:
        term.set_cwd(new_wd)
    log.append_entry("New Working Directory: %s" % new_wd)
    return (cmd_result.OK, "", "")
