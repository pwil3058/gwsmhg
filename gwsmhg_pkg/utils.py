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

import subprocess, os, signal, errno, gtk, select, urlparse, gobject, os.path
import cmd_result, ws_event

HOME = os.path.expanduser("~")

def path_rel_home(path):
    if urlparse.urlparse(path).scheme:
        return path
    path = os.path.abspath(path)
    len_home = len(HOME)
    if len(path) >= len_home and HOME == path[:len_home]:
        path = "~" + path[len_home:]
    return path

# handle the fact os.path.samefile is not available on all operating systems
def samefile(filename1, filename2):
    try:
        return os.path.samefile(filename1, filename2)
    except:
        return os.path.abspath(filename1) == os.path.abspath(filename2)

def create_file(name, console=None):
    if not os.path.exists(name):
        try:
            if console:
                console.start_cmd('create %s' % name)
            open(name, 'w').close()
            if console:
                console.end_cmd()
            ws_event.notify_events(ws_event.FILE_ADD)
            return (cmd_result.OK, '', '')
        except (IOError, OSError), msg:
            return (cmd_result.ERROR, '', '"%": %s' (name, msg))
    else:
        return (cmd_result.WARNING, '', '"%s": file already exists' % name)

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
    if os.name == 'nt' or os.name == 'dos':
        return run_cmd_in_console_nt(cmd, console)
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


if os.name == 'nt' or os.name == 'dos':
    def run_cmd_in_console_nt(cmd, console):
        console.start_cmd(cmd)
        res, sout, serr = run_cmd(cmd)
        console.append_stdout(sout)
        console.append_stderr(serr)
        console.end_cmd()
        return (res, sout, serr)
    def _which(cmd):
        main, ext = os.path.splitext(cmd)
        for d in os.environ['PATH'].split(os.pathsep):
            potential_path = os.path.join(d, cmd)
            if os.path.isfile(potential_path) and os.access(potential_path, os.X_OK):
                return potential_path
        return None
    nt_exts = ['.bat', '.bin', '.exe']
    def which(cmd):
        path = _which(cmd)
        if path:
            return path
        main, ext = os.path.splitext(cmd)
        if ext in nt_exts:
            return None
        for ext in nt_exts:
            path = _which(cmd + ext)
            if path is not None:
                return path
        return None
else:
    def which(cmd):
        for d in os.environ['PATH'].split(os.pathsep):
            potential_path = os.path.join(d, cmd)
            if os.path.isfile(potential_path) and os.access(potential_path, os.X_OK):
                return potential_path
        return None

