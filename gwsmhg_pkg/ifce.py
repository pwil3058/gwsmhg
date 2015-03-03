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

in_valid_repo = False

import os

from gwsmhg_pkg import hg_mq_ifce

from gwsmhg_pkg import cmd_result
from gwsmhg_pkg import utils
from gwsmhg_pkg import options
from gwsmhg_pkg import recollect

from gwsmhg_pkg import ws_event
from gwsmhg_pkg import terminal
from gwsmhg_pkg.console import LOG

SCM = hg_mq_ifce.SCMInterface()
PM = hg_mq_ifce.PMInterface()

TERM = None

def init(log_chdir=False):
    global TERM
    global in_valid_repo
    if terminal.AVAILABLE:
        TERM = terminal.Terminal()
    result = options.load_global_options()
    in_valid_repo = SCM.is_valid_repo()
    if in_valid_repo:
        from gwsmhg_pkg import config
        root = SCM.get_root()
        os.chdir(root)
        config.WSPathTable.append_saved_wd(root)
    else:
        root = None
    if result.ecode == 0:
        result = options.reload_pgnd_options()
    if log_chdir or root:
        LOG.start_cmd('gwsmhg {0}\n'.format(os.getcwd()))
        if root:
            LOG.append_stdout('In valid hg repository\n')
        else:
            LOG.append_stderr('NOT in valid hg repository\n')
        LOG.end_cmd()
    ws_event.notify_events(ws_event.CHANGE_WD)
    # pass on any errors experienced loading options
    return result

def close():
    pass

def chdir(newdir=None):
    global in_valid_repo
    old_wd = os.getcwd()
    retval = cmd_result.Result(cmd_result.OK, "", "")
    if newdir:
        try:
            os.chdir(newdir)
        except OSError as err:
            import errno
            ecode = errno.errorcode[err.errno]
            emsg = err.strerror
            retval = cmd_result.Result(cmd_result.ERROR, "", '%s: "%s" :%s' % (ecode, newdir, emsg))
    in_valid_repo = SCM.is_valid_repo()
    if in_valid_repo:
        from gwsmhg_pkg import config
        root = SCM.get_root()
        os.chdir(root)
        config.WSPathTable.append_saved_wd(root)
    options.reload_pgnd_options()
    ws_event.notify_events(ws_event.CHANGE_WD)
    new_wd = os.getcwd()
    recollect.set("gwsmhg", "last_wd", new_wd)
    if not utils.samefile(new_wd, old_wd):
        if TERM:
            TERM.set_cwd(new_wd)
    LOG.start_cmd(_("New Working Directory: {0}\n").format(new_wd))
    LOG.append_stdout(retval.stdout)
    LOG.append_stderr(retval.stderr)
    if in_valid_repo:
        LOG.append_stdout('In valid hg repository\n')
    else:
        LOG.append_stderr('NOT in valid hg repository\n')
    LOG.end_cmd()
    return retval
