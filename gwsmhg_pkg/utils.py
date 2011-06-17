# -*- python -*-

### Copyright (C) 2005-2011 Peter Williams <peter_ono@users.sourceforge.net>

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
"""Provide general utility functions."""

import subprocess
import os
import sys
import os.path
import signal
import select
import time
import zlib
import gzip
import bz2

import gtk
import gobject

from gwsmhg_pkg import cmd_result, ws_event, urlops

HOME = os.path.expanduser("~")

BENCHMARK = False

def path_rel_home(path):
    """Return the given path as a path relative to user's home directory."""
    if urlops.parse_url(path).scheme:
        return path
    path = os.path.abspath(path)
    len_home = len(HOME)
    if len(path) >= len_home and HOME == path[:len_home]:
        path = "~" + path[len_home:]
    return path

def cwd_rel_home():
    """Return path of current working directory relative to user's home
    directory.
    """
    return path_rel_home(os.getcwd())


def file_list_to_string(file_list):
    """Return the given list of file names as a single string:
    - using a single space as a separator, and
    - placing double quotes around file names that contain spaces.
    """
    mod_file_list = []
    for fname in file_list:
        if fname.count(' ') == 0:
            mod_file_list.append(fname)
        else:
            mod_file_list.append('"%s"' % fname)
    return ' '.join(mod_file_list)


def string_to_file_list(string):
    """Return a list of the file names in the given string:
    - assuming names are separated by spaces, and
    - file names that contain spaces are inside double quotes.
    """
    if string.count('"') == 0:
        return string.split()
    file_list = []
    index = 0
    lqi = string.rfind('"')
    while index < lqi:
        qib = string.find('"', index)
        file_list += string[index:qib].split()
        index = string.find('"', qib + 1) + 1
        file_list.append(string[qib+1:index-1])
    if index < len(string):
        file_list += string[index:].split()
    return file_list


# handle the fact os.path.samefile is not available on all operating systems
def samefile(filename1, filename2):
    """Return whether the given paths refer to the same file or not."""
    try:
        return os.path.samefile(filename1, filename2)
    except AttributeError:
        return os.path.abspath(filename1) == os.path.abspath(filename2)


def create_file(name, console=None):
    """Attempt to create a file with the given name and report the outcome as
    a cmd_result tuple.
    1. If console is not None print report of successful creation on it.
    2. If a file with same name already exists fail and report a warning.
    3. If file creation fails for other reasons report an error.
    """
    if not os.path.exists(name):
        try:
            if console:
                console.start_cmd('create "%s"' % name)
            open(name, 'w').close()
            if console:
                console.end_cmd()
            ws_event.notify_events(ws_event.FILE_ADD)
            return cmd_result.Result(cmd_result.OK, '', '')
        except (IOError, OSError) as msg:
            return cmd_result.Result(cmd_result.ERROR, '', '"%s": %s' % (name, msg))
    else:
        return cmd_result.Result(cmd_result.WARNING, '', '"%s": file already exists' % name)


def run_cmd(cmd, input_text=None):
    """Run the given command and report the outcome as a cmd_result tuple.
    If input_text is not None pas it to the command as standard input.
    """
    if BENCHMARK:
        start_time = time.clock()
    try:
        oldterm = os.environ['TERM']
        os.environ['TERM'] = "dumb"
    except LookupError:
        oldterm = None
    is_posix = os.name == 'posix'
    if is_posix:
        savedsh = signal.getsignal(signal.SIGPIPE)
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    sub = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
          stderr=subprocess.PIPE, shell=True, close_fds=is_posix, bufsize=-1)
    outd, errd = sub.communicate(input_text)
    if is_posix:
        signal.signal(signal.SIGPIPE, savedsh)
    if oldterm:
        os.environ['TERM'] = oldterm
    if BENCHMARK:
        print 'run:', time.clock() - start_time, sub.returncode, len(outd), len(errd), ':', cmd
    return cmd_result.Result(sub.returncode, outd, errd)


def run_cmd_in_console(cmd, console, input_text=None):
    """Run the given command in the given console and report the outcome as a
    cmd_result tuple.
    If input_text is not None pas it to the command as standard input.
    """
    if os.name == 'nt' or os.name == 'dos':
        return run_cmd_in_console_nt(cmd, console, input_text=input_text)
    if BENCHMARK:
        start_time = time.clock()
    try:
        oldterm = os.environ['TERM']
        os.environ['TERM'] = "dumb"
    except LookupError:
        oldterm = None
    is_posix = os.name == 'posix'
    if is_posix:
        savedsh = signal.getsignal(signal.SIGPIPE)
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    console.start_cmd(cmd)
    while gtk.events_pending():
        gtk.main_iteration()
    sub = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
          stderr=subprocess.PIPE, shell=True, close_fds=is_posix, bufsize=-1)
    if input_text is not None:
        sub.stdin.write(input_text)
        console.append_stdin(input_text)
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
    if BENCHMARK:
        print 'console:', time.clock() - start_time, sub.returncode, len(outd), len(errd), ':', cmd
    return cmd_result.Result(sub.returncode, outd, errd)


def _wait_for_bgnd_cmd_timeout(pid):
    """Callback to clean up after background tasks complete"""
    try:
        if os.name == 'nt' or os.name == 'dos':
            rpid, _ = os.waitpid(pid, 0)
        else:
            rpid, _ = os.waitpid(pid, os.WNOHANG)
        return rpid != pid
    except OSError:
        return False


def run_cmd_in_bgnd(cmd):
    """Run the given command in the background and poll for its exit using
    _wait_for_bgnd_timeout() as a callback.
    """
    if not cmd:
        return False
    pid = subprocess.Popen(string_to_file_list(cmd)).pid
    if not pid:
        return False
    gobject.timeout_add(2000, _wait_for_bgnd_cmd_timeout, pid)
    return True

if os.name == 'nt' or os.name == 'dos':
    def run_cmd_in_console_nt(cmd, console, input_text=None):
        """Run the given command in the given console and report the
        outcome as a cmd_result tuple.
        If input_text is not None pas it to the command as standard input.
        """
        console.start_cmd(cmd)
        if input_text is not None:
            console.append_stdin(input_text)
        res, sout, serr = run_cmd(cmd, input_text=input_text)
        console.append_stdout(sout)
        console.append_stderr(serr)
        console.end_cmd()
        return cmd_result.Result(res, sout, serr)


    def _which(cmd):
        """Return the path of the executable for the given command"""
        for dirpath in os.environ['PATH'].split(os.pathsep):
            potential_path = os.path.join(dirpath, cmd)
            if os.path.isfile(potential_path) and \
               os.access(potential_path, os.X_OK):
                return potential_path
        return None


    NT_EXTS = ['.bat', '.bin', '.exe']


    def which(cmd):
        """Return the path of the executable for the given command"""
        path = _which(cmd)
        if path:
            return path
        _, ext = os.path.splitext(cmd)
        if ext in NT_EXTS:
            return None
        for ext in NT_EXTS:
            path = _which(cmd + ext)
            if path is not None:
                return path
        return None
else:
    def which(cmd):
        """Return the path of the executable for the given command"""
        for dirpath in os.environ['PATH'].split(os.pathsep):
            potential_path = os.path.join(dirpath, cmd)
            if os.path.isfile(potential_path) and \
               os.access(potential_path, os.X_OK):
                return potential_path
        return None

def get_first_in_envar(envar_list):
    for envar in envar_list:
        try:
            value = os.environ[envar]
            if value != '':
                return value
        except KeyError:
            continue
    return ''

def get_file_contents(srcfile, decompress=False):
    '''
    Get the contents of filename to text after (optionally) applying
    decompression as indicated by filename's suffix.
    '''
    if decompress:
        _root, ext = os.path.splitext(srcfile)
        res = 0
        if ext == '.gz':
            return gzip.open(srcfile).read()
        elif ext == '.bz2':
            bz2f = bz2.BZ2File(srcfile, 'r')
            text = bz2f.read()
            bz2f.close()
            return text
        elif ext == '.xz':
            res, text, serr = run_cmd('xz -cd %s' % srcfile)
        elif ext == '.lzma':
            res, text, serr = run_cmd('lzma -cd %s' % srcfile)
        else:
            return open(srcfile).read()
        if res != 0:
            sys.stderr.write(serr)
        return text
    else:
        return open(srcfile).read()

def set_file_contents(filename, text, compress=False):
    '''
    Set the contents of filename to text after (optionally) applying
    compression as indicated by filename's suffix.
    '''
    if compress:
        _root, ext = os.path.splitext(filename)
        res = 0
        if ext == '.gz':
            try:
                gzip.open(filename, 'wb').write(text)
                return True
            except (IOError, zlib.error):
                return False
        elif ext == '.bz2':
            try:
                bz2f = bz2.BZ2File(filename, 'w')
                text = bz2f.write(text)
                bz2f.close()
                return True
            except IOError:
                return False
        elif ext == '.xz':
            res, text, serr = run_cmd('xz -c', text)
        elif ext == '.lzma':
            res, text, serr = run_cmd('lzma -c', text)
        if res != 0:
            sys.stderr.write(serr)
            return False
    try:
        open(filename, 'w').write(text)
    except IOError:
        return False
    return True

def is_utf8_compliant(text):
    try:
        _ = text.decode('utf-8')
    except UnicodeError:
        return False
    return True

ISO_8859_CODECS = ['iso-8859-{0}'.format(x) for x in range(1, 17)]
ISO_2022_CODECS = ['iso-2022-jp', 'iso-2022-kr'] + \
    ['iso-2022-jp-{0}'.format(x) for x in range(1, 3) + ['2004', 'ext']]

def make_utf8_compliant(text):
    '''Return a UTF-8 compliant version of text'''
    if is_utf8_compliant(text):
        return text
    for codec in ISO_8859_CODECS + ISO_2022_CODECS:
        try:
            text = unicode(text, codec).encode('utf-8')
            return text
        except UnicodeError:
            continue
    raise UnicodeError
