# -*- python -*-

### Copyright (C) 2005 Peter Williams <peter_ono@users.sourceforge.net>

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

import subprocess, os, signal, errno, gtk, select, urlparse, gobject

HOME = os.path.expanduser("~")

def path_rel_home(path):
    if urlparse.urlparse(path).scheme:
        return path
    path = os.path.abspath(path)
    len_home = len(HOME)
    if len(path) >= len_home and HOME == path[:len_home]:
        path = "~" + path[len_home:]
    return path

def run_cmd(cmd):
    if not cmd:
        return [ 0, None, None ]
    try:
        oldterm = os.environ['TERM']
        os.environ['TERM'] = "dumb"
    except:
        oldterm = None
    is_posix = os.name is 'posix'
    if is_posix:
        savedsh = signal.getsignal(signal.SIGPIPE)
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    sub = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
          stderr=subprocess.PIPE, shell=True, close_fds=is_posix, bufsize=-1)
    outd, errd = sub.communicate()
    if is_posix:
        signal.signal(signal.SIGPIPE, savedsh)
    if oldterm:
        os.environ['TERM'] = oldterm
    return [ sub.returncode, outd, errd ]

def run_cmd_in_console(cmd, console):
    if not cmd:
        return [ 0, None, None ]
    try:
        oldterm = os.environ['TERM']
        os.environ['TERM'] = "dumb"
    except:
        oldterm = None
    is_posix = os.name is 'posix'
    if is_posix:
        savedsh = signal.getsignal(signal.SIGPIPE)
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    console.start_cmd(cmd)
    while gtk.events_pending():
        gtk.main_iteration()
    sub = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
          stderr=subprocess.PIPE, shell=True, close_fds=is_posix, bufsize=-1)
    sub.stdin.close()
    stdout_eof = stderr_eof = False
    outd = errd = ""
    while True:
        to_check_in = [sub.stdout] * (not stdout_eof) + \
                      [sub.stderr] * (not stderr_eof)
        ready = select.select(to_check_in, [], [], 0)
        if sub.stdout in ready[0]:
            ochunk = sub.stdout.readline()
            if ochunk == '':
                stdout_eof = True
            else:
                console.append_stdout(ochunk)
                outd += ochunk
        if sub.stderr in ready[0]:
            echunk = sub.stderr.readline()
            if echunk == '':
                stderr_eof = True
            else:
                console.append_stderr(echunk)
                errd += echunk
        while gtk.events_pending():
            gtk.main_iteration()
        if stdout_eof and stderr_eof:
            break
    sub.wait()
    console.end_cmd()
    if is_posix:
        signal.signal(signal.SIGPIPE, savedsh)
    if oldterm:
        os.environ['TERM'] = oldterm
    return [ sub.returncode, outd, errd ]

def _wait_for_bgnd_cmd_timeout(pid):
    try:
        rpid, status = os.waitpid(pid, os.WNOHANG)
        return rpid != pid
    except OSError:
        return False

def run_cmd_in_bgnd(cmd):
    if not cmd:
        return False
    pid = subprocess.Popen(cmd.split()).pid
    if not pid:
        return False
    gobject.timeout_add(2000, _wait_for_bgnd_cmd_timeout, pid)
    return True

def which(cmd):
    for d in os.environ['PATH'].split(os.pathsep):
        potential_path = os.path.join(d, cmd)
        if os.path.isfile(potential_path) and os.access(potential_path, os.X_OK):
            return potential_path
    return None

class action_notifier:
    def __init__(self):
        self._notification_cbs = {}
    def add_notification_cb(self, cmd_list, cb):
        for cmd in cmd_list:
            if self._notification_cbs.has_key(cmd):
                self._notification_cbs[cmd].append(cb)
            else:
                self._notification_cbs[cmd] = [cb]
    def del_notification_cb(self, cmd_list, cb):
        for cmd in cmd_list:
            if self._notification_cbs.has_key(cmd):
                try:
                    i = self._notification_cbs[cmd].index(cb)
                    del self._notification_cbs[cmd][i]
                except:
                    pass
    def del_cmd_notification_cbs(self, cmd, cb_list):
        if self._notification_cbs.has_key(cmd):
            for cb in cb_list:
                try:
                    i = self._notification_cbs[cmd].index(cb)
                    del self._notification_cbs[cmd][i]
                except:
                    pass
    def _do_cmd_notification(self, cmd, data=None):
        if self._notification_cbs.has_key(cmd):
            failures = []
            for cb in self._notification_cbs[cmd]:
                # the callee may no longer exist and may not have removed
                # its callbacks so handle failure
                try:
                    if data is not None:
                        cb(data)
                    else:
                        cb()
                except:
                    failures.append(cb)
            if failures:
                self.del_cmd_notification_cbs(cmd, failures)

