# -*- python -*-

### Copyright (C) 2005 Peter Williams <pwil3058@bigpond.net.au>

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

import subprocess, os, signal, errno, gtk, select

HOME = os.path.expanduser("~")

def path_rel_home(path):
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

def run_cmd_in_console(cmd, console, interactive=False):
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
            ochunk = sub.stdout.read(1)
            if ochunk == '':
                stdout_eof = True
            else:
                console.append_stdout(ochunk)
                outd += ochunk
        if sub.stderr in ready[0]:
            echunk = sub.stderr.read(1)
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

