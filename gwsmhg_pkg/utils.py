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
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
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
import shutil

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
        return cmd_result.Result(cmd_result.WARNING, '', _('"%s": file already exists') % name)

if os.name == 'nt' or os.name == 'dos':
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
    if text is None:
        return ''
    if is_utf8_compliant(text):
        return text
    for codec in ISO_8859_CODECS + ISO_2022_CODECS:
        try:
            text = unicode(text, codec).encode('utf-8')
            return text
        except UnicodeError:
            continue
    raise UnicodeError

def os_move_or_copy_file(self, file_path, dest, opsym, force=False, dry_run=False, extra_checks=None, verbose=False):
    assert opsym in (fsdb.Relation.RENAMED_TO, fsdb.Relation.COPIED_TO), _("Invalid operation requested")
    if os.path.isdir(dest):
        dest = os.path.join(dest, os.path.basename(file_path))
    omsg = "{0} {1} {2}.".format(file_path, opsym, dest) if verbose else ""
    if dry_run:
        if os.path.exists(dest):
            return cmd_result.Result(cmd_result.ERROR_SUGGEST_FORCE, omsg, _('File "{0}" already exists. Select "force" to overwrite.').format(dest))
        else:
            return cmd_result.Result(cmd_result.OK, omsg, "")
    from gquilt_pkg import console
    console.LOG.start_cmd("{0} {1} {2}\n".format(file_path, opsym, dest))
    if not force and os.path.exists(dest):
        emsg = _('File "{0}" already exists. Select "force" to overwrite.').format(dest)
        result = cmd_result.Result(cmd_result.ERROR_SUGGEST_FORCE, omsg, emsg)
        console.LOG.end_cmd(result)
        return result
    if extra_checks:
        result = extra_check([(file_path, dest)])
        if result.ecode is not cmd_result.OK:
            console.LOG.end_cmd(result)
            return result
    try:
        if opsym is fsdb.MOVED_TO:
            os.rename(file_path, dest)
        elif opsym is fsdb.COPIED_TO:
            shutil.copy(file_path, dest)
        result = cmd_result.Result(cmd_result.OK, omsg, "")
    except (IOError, os.error, shutil.Error) as why:
        result = cmd_result.Result(cmd_result.ERROR, omsg, _('"{0}" {1} "{2}" failed. {3}.\n') % (file_path, opsym, dest, str(why)))
    console.LOG.end_cmd(result)
    ws_event.notify_events(ws_event.FILE_ADD|ws_event.FILE_DEL)
    return result

def os_move_or_copy_files(self, file_path_list, dest, opsym, force=False, dry_run=False, extra_checks=None, verbose=False):
    assert opsym in (fsdb.MOVED_TO, fsdb.COPIED_TO), _("Invalid operation requested")
    if len(file_path_list) == 1:
        return _os_move_or_copy_file(file_path_list[0], dest, force=force, dry_run=dry_run, extra_checks=extra_checks)
    from gquilt_pkg import console
    if not dry_run:
        console.LOG.start_cmd("{0} {1} {2}\n".format(file_list_to_string(file_path_list), opsym, dest))
    if not os.path.isdir(dest):
        result = cmd_result.Result(cmd_result.ERROR, '', _('"{0}": Destination must be a directory for multifile rename.').format(dest))
        if not dry_run:
            console.LOG.end_cmd(result)
        return result
    opn_paths_list = [(file_path, os.path.join(dest, os.path.basename(file_path))) for file_path in file_path_list]
    omsg = "\n".join(["{0} {1} {2}.".format(src, opsym, dest) for (src, dest) in opn_paths_list]) if verbose else ""
    if dry_run:
        overwrites = [dest for (src, dest) in opn_paths_list if os.path.exists(dest)]
        if len(overwrites) > 0:
            emsg = _("File(s) {0} already exist(s). Select \"force\" to overwrite.").format(", ".join(["\"" + fp + "\"" for fp in overwrites]))
            return cmd_result.Result(cmd_result.ERROR_SUGGEST_FORCE, omsg, emsg)
        else:
            return cmd_result.Result(cmd_result.OK, omsg, "")
    if not force:
        overwrites = [dest for (src, dest) in opn_paths_list if os.path.exists(dest)]
        if len(overwrites) > 0:
            result = cmd_result.Result(cmd_result.ERROR_SUGGEST_FORCE, omsg, _("File(s) {0} already exist(s). Select \"force\" to overwrite.").format(", ".join(["\"" + fp + "\"" for fp in overwrites])))
            console.LOG.end_cmd(result)
            return result
    if extra_checks:
        result = extra_check(opn_paths_list)
        if result.ecode is not cmd_result.OK:
            console.LOG.end_cmd(result)
            return result
    failed_opns_str = ""
    for (src, dest) in opn_paths_list:
        if verbose:
            console.LOG.append_stdout("{0} {1} {2}.".format(src, opsym, dest))
        try:
            if opsym is fsdb.MOVED_TO:
                os.rename(src, dest)
            elif opsym is fsdb.COPIED_TO:
                if os.path.isdir(src):
                    shutil.copytree(src, dest)
                else:
                    shutil.copy2(src, dest)
        except (IOError, os.error, shutil.Error) as why:
            serr = _('"{0}" {1} "{2}" failed. {3}.\n').format(src, opsym, dest, str(why))
            console.LOG.append_stderr(serr)
            failed_opns_str += serr
            continue
    console.LOG.end_cmd()
    ws_event.notify_events(ws_event.FILE_ADD|ws_event.FILE_DEL)
    if failed_opns_str:
        return cmd_result.Result(cmd_result.ERROR, omsg, failed_opns_str)
    return cmd_result.Result(cmd_result.OK, omsg, "")

def os_copy_file(file_path, dest, force=False, dry_run=False):
    return os_move_or_copy_file(file_path, dest, opsym=fsdb.COPIED_TO, force=force, dry_run=dry_run)

def os_copy_files(file_path_list, dest, force=False, dry_run=False):
    return os_move_or_copy_files(file_path_list, dest, opsym=fsdb.COPIED_TO, force=force, dry_run=dry_run)

def os_move_file(file_path, dest, force=False, dry_run=False):
    return os_move_or_copy_file(file_path, dest, opsym=fsdb.MOVED_TO, force=force, dry_run=dry_run)

def os_move_files(file_path_list, dest, force=False, dry_run=False):
    return os_move_or_copy_files(file_path_list, dest, opsym=fsdb.MOVED_TO, force=force, dry_run=dry_run)
