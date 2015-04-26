### Copyright (C) 2010 Peter Williams <peter_ono@users.sourceforge.net>

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

import collections
import os
import hashlib

class Relation(object):
    COPIED_FROM = '<<-'
    COPIED_TO = '->>'
    MOVED_FROM = '<-'
    MOVED_TO = '->'

RFD = collections.namedtuple('RFD', ['path', 'relation'])
Data = collections.namedtuple('Data', ['name', 'status', 'related_file'])
Deco = collections.namedtuple('Deco', ['style', 'foreground'])

def split_path(path):
    if os.path.isabs(path):
        path = os.path.relpath(path)
    parts = []
    while path:
        path, tail = os.path.split(path)
        parts.insert(0, tail)
    return parts

class NullFileDb:
    def __init__(self):
        pass
    def dir_contents(self, dirpath, show_hidden=False):
        return ([], [])

class OsFileDb:
    def __init__(self):
        pass
    def _is_not_hidden_file(self, filepath):
        return filepath[0] != '.'
    def dir_contents(self, dirpath, show_hidden=False):
        files = []
        dirs = []
        if not dirpath:
            dirpath = os.curdir
        elements = os.listdir(dirpath)
        for element in elements:
            if os.path.isdir(os.path.join(dirpath, element)):
                if self._is_not_hidden_file(element) or show_hidden:
                    dirs.append(Data(element, None, None))
            elif self._is_not_hidden_file(element) or show_hidden:
                files.append(Data(element, None, None))
        dirs.sort()
        files.sort()
        return (dirs, files)

class GenDir:
    def __init__(self):
        self.status = None
        self.status_set = set()
        self.subdirs = {}
        self.files = {}
    def _new_dir(self):
        return GenDir()
    def add_file(self, path_parts, status, related_file=None):
        self.status_set.add(status)
        name = path_parts[0]
        if len(path_parts) == 1:
            self.files[name] = Data(name=name, status=status, related_file=related_file)
        else:
            if name not in self.subdirs:
                self.subdirs[name] = self._new_dir()
            self.subdirs[name].add_file(path_parts[1:], status, related_file)
    def _update_own_status(self):
        if len(self.status_set) > 0:
            self.status = self.status_set.pop()
            self.status_set.add(self.status)
        else:
            self.status = None
    def update_status(self):
        self._update_own_status()
        for key in list(self.subdirs.keys()):
            self.subdirs[key].update_status()
    def _find_dir(self, dirpath_parts):
        if not dirpath_parts:
            return self
        elif dirpath_parts[0] in self.subdirs:
            return self.subdirs[dirpath_parts[0]]._find_dir(dirpath_parts[1:])
        else:
            return None
    def find_dir(self, dirpath):
        if not dirpath:
            return self
        return self._find_dir(split_path(dirpath))
    def _is_hidden_dir(self, dkey):
        return dkey[0] == '.'
    def _is_hidden_file(self, fkey):
        return fkey[0] == '.'
    def dirs_and_files(self, show_hidden=False):
        if show_hidden:
            dirs = [Data(name=dkey, status=self.subdirs[dkey].status, related_file=None) for dkey in sorted(self.subdirs)]
            files = [self.files[fkey] for fkey in sorted(self.files)]
        else:
            dirs = [Data(name=dkey, status=self.subdirs[dkey].status, related_file=None) for dkey in sorted(self.subdirs) if not self._is_hidden_dir(dkey)]
            files = [self.files[fkey] for fkey in sorted(self.files) if not self._is_hidden_file(fkey)]
        return (dirs, files)

class GenFileDb:
    DIR_TYPE = GenDir
    def __init__(self):
        self.base_dir = self.DIR_TYPE()
    def add_file(self, filepath, status, related_file=None):
        self.base_dir.add_file(split_path(filepath), status, related_file)
    def decorate_dirs(self):
        self.base_dir.update_status()
    def dir_contents(self, dirpath='', show_hidden=False):
        tdir = self.base_dir.find_dir(dirpath)
        if not tdir:
            return ([], [])
        return tdir.dirs_and_files(show_hidden)

class GenSnapshotFileDb(GenFileDb):
    def __init__(self, default_status=None):
        GenFileDb.__init__(self)
        self.tree_hash = hashlib.sha1()
    def _get_current_tree_hash(self):
        assert False, _("_get_current_tree_hash() must be defined in child")
    @property
    def is_current(self):
        h = self._get_current_tree_hash()
        return h.digest() == self.tree_hash.digest()

class GenSnapshotDir(object):
    def __init__(self, dir_path=None):
        self._dir_path = dir_path if dir_path is not None else os.curdir
        self._is_populated = False
        self._status = self._get_dir_current_status()
        self._subdirs = {}
        self._files = {}
        self.dir_hash = hashlib.sha1()
    def _get_os_current_dirs_and_files(self):
        # return a tuple containing the directory and filenames sorted alphabetically
        files = []
        dirs = []
        try:
            items = os.listdir(self._dir_path)
        except OSError:
            return ([], [])
        for item in items:
            if os.path.isdir(os.path.join(self._dir_path, item)):
                dirs.append(item)
            else:
                files.append(item)
        dirs.sort()
        files.sort()
        return (dirs, files)
    def _get_current_hash(self):
        h = hashlib.sha1()
        assert False, "needs to be defined in children"
        return h
    def _populate(self):
        h = hashlib.sha1()
        assert False, "needs to be defined in children"
        return h
    @property
    def is_current(self):
        if not self._is_populated:
            return self._get_dir_current_status() == self._status
        elif self._get_current_hash().digest() != self.dir_hash.digest():
            return False
        for subdir in self._subdirs.values():
            if not subdir.is_current:
                return False
        return True
    def _find_dir(self, dirpath_parts):
        if not dirpath_parts:
            return self
        elif dirpath_parts[0] in self._subdirs:
            return self._subdirs[dirpath_parts[0]]._find_dir(dirpath_parts[1:])
        else:
            return None
    def find_dir(self, dirpath):
        if not dirpath:
            return self
        return self._find_dir(split_path(dirpath))
    def _is_hidden_dir(self, dkey):
        return dkey[0] == '.'
    def _is_hidden_file(self, fkey):
        assert False, "needs to be defined in children"
    def dirs_and_files(self, show_hidden=False):
        if not self._is_populated:
            self.dir_hash = self._populate()
        if show_hidden:
            dirs = [Data(name=dkey, status=self._subdirs[dkey]._status, related_file=None) for dkey in sorted(self._subdirs)]
            files = [self._files[fkey] for fkey in sorted(self._files)]
        else:
            dirs = [Data(name=dkey, status=self._subdirs[dkey]._status, related_file=None) for dkey in sorted(self._subdirs) if not self._is_hidden_dir(dkey)]
            files = [self._files[fkey] for fkey in sorted(self._files) if not self._is_hidden_file(fkey)]
        return (dirs, files)

class NewGenSnapshotFileDb(GenFileDb):
    DIR_TYPE = GenSnapshotDir
    def __init__(self):
        GenFileDb.__init__(self)
    @property
    def is_current(self):
        return self.base_dir.is_current

class OsSnapshotDir(GenSnapshotDir):
    def __init__(self, dir_path=None):
        GenSnapshotDir.__init__(self, dir_path)
    def _get_dir_current_status(self):
        return None if os.path.isdir(self._dir_path) else False
    def _get_current_hash(self):
        h = hashlib.sha1()
        cur_dirs, cur_files = self._get_os_current_dirs_and_files()
        for cur_dir in cur_dirs:
            h.update(cur_dir)
        for cur_file in cur_files:
            h.update(cur_file)
        return h
    def _populate(self):
        h = hashlib.sha1()
        cur_dirs, cur_files = self._get_os_current_dirs_and_files()
        for cur_dir in cur_dirs:
            self._subdirs[cur_dir] = OsSnapshotDir(os.path.join(self._dir_path, cur_dir))
            h.update(cur_dir)
        for cur_file in cur_files:
            self._files[cur_file] = Data(name=cur_file, status=None, related_file=None)
            h.update(cur_file)
        self._is_populated = True
        return h
    def _is_hidden_file(self, fkey):
        return fkey[0] == '.'

class OsSnapshotFileDb(NewGenSnapshotFileDb):
    DIR_TYPE = OsSnapshotDir
