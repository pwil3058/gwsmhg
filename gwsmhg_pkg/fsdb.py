### Copyright (C) 2015 Peter Williams <peter_ono@users.sourceforge.net>
###
### This program is free software; you can redistribute it and/or modify
### it under the terms of the GNU General Public License as published by
### the Free Software Foundation; version 2 of the License only.
###
### This program is distributed in the hope that it will be useful,
### but WITHOUT ANY WARRANTY; without even the implied warranty of
### MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
### GNU General Public License for more details.
###
### You should have received a copy of the GNU General Public License
### along with this program; if not, write to the Free Software
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import collections
import os
import hashlib
from itertools import ifilter

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
    @property
    def is_current(self):
        return True
    def dir_contents(self, dir_path, **kwargs):
        return ([], [])

class OsFileDb(NullFileDb):
    class FileDir(object):
        def __init__(self, name=None, dir_path=None, status=None, **kwargs):
            # DEBUG: assert dir_path is None or os.path.basename(dir_path) == name
            self._dir_path = dir_path if dir_path is not None else os.curdir
            self._is_populated = False
            self._subdirs = {}
            self._files_data = []
            self._subdirs_data = []
            self.data = None if not name else Data(name, status if status is not False else self._get_current_status(), None)
            self._dir_hash_digest = None
        @property
        def is_current(self):
            if self._get_current_hash_digest() != self._dir_hash_digest:
                return False
            for subdir in self._subdirs.values():
                if not subdir.is_current:
                    return False
            return True
        @classmethod
        def _new_dir(cls, name, dir_path, **kwargs):
            return cls(name, dir_path, **kwargs)
        def _add_subdir(self, name, dir_path=None, status=None, **kwargs):
            self._subdirs[name] = self._new_dir(name=name, dir_path=dir_path if dir_path else os.path.join(self._dir_path, name), status=status, **kwargs)
        def _add_file(self, name, status=None, related_file=None):
            self._files_data.append(Data(name=name, status=status, related_file=related_file))
        def _get_current_hash_digest(self):
            h = hashlib.sha1()
            for item in os.listdir(self._dir_path):
                h.update(item)
            return h.digest()
        def _populate(self):
            h = hashlib.sha1()
            for item in os.listdir(self._dir_path):
                h.update(item)
                dir_path = os.path.join(self._dir_path, item)
                if os.path.isdir(dir_path):
                    self._add_subdir(name=item, dir_path=dir_path)
                else:
                    self._add_file(name=item)
            self._files_data.sort()
            # presort this data for multiple access efficiency
            self._subdirs_data = sorted([s.data for s in self._subdirs.itervalues()])
            self._is_populated = True
            return h.digest()
        def find_dir(self, dir_path):
            if not dir_path:
                return self
            sep_index = dir_path.find(os.sep)
            if sep_index == -1:
                return self._subdirs[dir_path]
            return self._subdirs[dir_path[:sep_index]].find_dir(dir_path[sep_index + 1:])
        def dirs_and_files(self, show_hidden=False, **kwargs):
            if not self._is_populated:
                self._dir_hash_digest = self._populate()
            # use iterators for efficiency and data integrity
            if show_hidden:
                dirs = iter(self._subdirs_data)
                files = iter(self._files_data)
            else:
                dirs = ifilter((lambda x: x.name[0] != "."), self._subdirs_data)
                files = ifilter((lambda x: x.name[0] != "."), self._files_data)
            return (dirs, files)
    def __init__(self, **kwargs):
        NullFileDb.__init__(self)
        self.base_dir = self.FileDir(**kwargs)
    @property
    def is_current(self):
        return self.base_dir.is_current
    def dir_contents(self, dir_path='', show_hidden=False, **kwargs):
        tdir = self.base_dir.find_dir(dir_path)
        if not tdir:
            return ([], [])
        return tdir.dirs_and_files(show_hidden=show_hidden, **kwargs)

class GenericWsFileDb(OsFileDb):
    class FileDir(OsFileDb.FileDir):
        IGNORED_STATUS_SET = set()
        CLEAN_STATUS_SET = set()
        SIGNIFICANT_STATUS_SET = set()
        def __init__(self, name=None, dir_path=None, status=False, **kwargs):
            OsFileDb.FileDir.__init__(self, name=name, dir_path=dir_path, status=status)
        @property
        def is_current(self):
            if not self._is_populated:
                return self._get_current_status() == self.data.status
            if self._get_current_hash_digest() != self._dir_hash_digest:
                return False
            for subdir in self._subdirs.values():
                if not subdir.is_current:
                    return False
            return True
        def _add_subdir(self, name, dir_path=None, status=False, **kwargs):
            # NB: default status has been changed to False
            OsFileDb.FileDir._add_subdir(self, name=name, dir_path=dir_path, status=status, **kwargs)
        def _get_current_status(self):
            assert False, "_get_current_status() must be defined in children"
        def _get_current_hash_digest(self):
            h = hashlib.sha1()
            assert False, "_get_current_hash_digest() must be defined in child"
            return h.digest()
        def _populate(self):
            h = hashlib.sha1()
            assert False, "_populate() must be defined in child"
            self._is_populated = True
            return h.digest()
        def _is_hidden_dir(self, ddata):
            if ddata.name[0] == '.':
                return ddata.status not in self.SIGNIFICANT_STATUS_SET
            return False
        def _is_hidden_file(self, fdata):
            if fdata.name[0] == ".":
                return fdata.status not in self.SIGNIFICANT_STATUS_SET
            return fdata.status in self.IGNORED_STATUS_SET
        def _is_clean_dir(self, ddata):
            return ddata.status in self.CLEAN_STATUS_SET
        def _is_clean_file(self, fdata):
            return fdata.status in self.CLEAN_STATUS_SET
        def dirs_and_files(self, show_hidden=False, hide_clean=False):
            if not self._is_populated:
                self._dir_hash_digest = self._populate()
            if show_hidden:
                if hide_clean:
                    dirs = ifilter((lambda x: x.status not in self.CLEAN_STATUS_SET), self._subdirs_data)
                    files = ifilter((lambda x: x.status not in self.CLEAN_STATUS_SET), self._files_data)
                else:
                    dirs = iter(self._subdirs_data)
                    files = iter(self._files_data)
            elif hide_clean:
                dirs = ifilter((lambda x: not (x.status in self.CLEAN_STATUS_SET or self._is_hidden_dir(x))), self._subdirs_data)
                files = ifilter((lambda x: not (x.status in self.CLEAN_STATUS_SET or self._is_hidden_file(x))), self._files_data)
            else:
                dirs = ifilter((lambda x: not self._is_hidden_dir(x)), self._subdirs_data)
                files = ifilter((lambda x: not self._is_hidden_file(x)), self._files_data)
            return (dirs, files)

class GenericChangeFileDb(object):
    class FileDir(object):
        CLEAN_STATUS_SET = frozenset()
        def __init__(self, name=None, **kwargs):
            self._subdirs = {}
            self._subdirs_data = []
            self._files_data = []
            self._status_set = set()
            self.data = Data(name, None, None)
        @classmethod
        def _new_dir(cls, name, **kwargs):
            return cls(name, **kwargs)
        def finalize(self):
            self._subdirs_data = sorted([s.data for s in self._subdirs.itervalues()])
            self._files_data.sort()
            status = self._calculate_status()
            self.data = Data(self.data.name, status, None)
            for subdir in self._subdirs.itervalues():
                subdir.finalize()
        def add_file(self, path_parts, status, related_file=None):
            self._status_set.add(status)
            name = path_parts[0]
            if len(path_parts) == 1:
                self._files_data.append(Data(name=name, status=status, related_file=related_file))
            else:
                if name not in self._subdirs:
                    self._subdirs[name] = self._new_dir(name)
                self._subdirs[name].add_file(path_parts[1:], status, related_file)
        def _calculate_status(self):
            assert False, "_calculate_status() must be defined in child"
        def find_dir(self, dir_path):
            if not dir_path:
                return self
            sep_index = dir_path.find(os.sep)
            if sep_index == -1:
                return self._subdirs[dir_path]
            return self._subdirs[dir_path[:sep_index]].find_dir(dir_path[sep_index + 1:])
        def dirs_and_files(self, show_hidden=False, hide_clean=False):
            if hide_clean:
                dirs = ifilter((lambda x: x.status not in self.CLEAN_STATUS_SET), self._subdirs_data)
                files = ifilter((lambda x: x.status not in self.CLEAN_STATUS_SET), self._files_data)
            else:
                dirs = iter(self._subdirs_data)
                files = iter(self._files_data)
            return (dirs, files)
    def __init__(self, **kwargs):
        self._args = kwargs
        h = hashlib.sha1()
        pdt = self._get_patch_data_text(h)
        self._db_hash_digest = h.digest()
        self._base_dir = self.FileDir()
        for file_path, status, related_file in self._iterate_file_data(pdt):
            self._base_dir.add_file(split_path(file_path), status, related_file)
        self._base_dir.finalize()
    @property
    def is_current(self):
        h = hashlib.sha1()
        self._get_patch_data_text(h)
        return h.digest() == self._db_hash_digest
    def dir_contents(self, dirpath='', hide_clean=False, **kwargs):
        tdir = self._base_dir.find_dir(dirpath)
        if not tdir:
            return ([], [])
        return tdir.dirs_and_files(hide_clean=hide_clean)
    def _get_patch_data_text(self, h):
        assert False, "_get_patch_data_text() must be defined in child"
    @staticmethod
    def _iterate_file_data(pdt):
        assert False, "iterate_file_data() must be defined in child"
