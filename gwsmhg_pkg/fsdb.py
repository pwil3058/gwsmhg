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
Data = collections.namedtuple('Data', ['name', 'status', 'related_file_data'])
Deco = collections.namedtuple('Deco', ['style', 'foreground'])

# Contained File Relative Data
CFRD = collections.namedtuple("CFRD", ["sub_dir_relpath", "name"])
def get_file_path_relative_data(file_path, base_dir_path=None):
    data = CFRD(*os.path.split(os.path.relpath(file_path, os.curdir if base_dir_path is None else base_dir_path)))
    return None if data.sub_dir_relpath.startswith(os.pardir) else data

def split_path(path):
    if os.path.isabs(path):
        path = os.path.relpath(path)
    parts = []
    while path:
        path, tail = os.path.split(path)
        parts.insert(0, tail)
    return parts

def file_path_belongs_here(file_path, base_dir_path=None):
    return not os.path.relpath(file_path, os.curdir if base_dir_path is None else base_dir_path).startswith(os.pardir)

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
            self.data = None if not name else Data(name, status if status is not False else self._get_initial_status(), None)
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
        def _add_file(self, name, status=None, related_file_data=None):
            self._files_data.append(Data(name=name, status=status, related_file_data=related_file_data))
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
        def _get_initial_status(self):
            assert False, "_get_initial_status() must be defined in children"
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

class Snapshot(object):
    def __init__(self, file_status_data, relevant_keys=None):
        self._file_status_data = file_status_data
        self._relevant_keys = file_status_data.keys() if relevant_keys is None else relevant_keys
        self._status_set = frozenset(file_status_data[key][0] for key in self._relevant_keys)
    @property
    def status_set(self):
        return self._status_set
    def iterate_data(self):
        for file_path in self._relevant_keys:
            status, related_file_data = self._file_status_data[file_path]
            yield (file_path, status, related_file_data)
    def narrowed_for_subdir(self, dir_path):
        relevant_keys = [file_path for file_path in self._relevant_keys if file_path_belongs_here(file_path, dir_path)]
        return self.__class__(self._file_status_data, relevant_keys)

class GenericSnapshotWsFileDb(GenericWsFileDb):
    class FileDir(GenericWsFileDb.FileDir):
        IGNORED_STATUS_SET = frozenset()
        CLEAN_STATUS_SET = frozenset()
        SIGNIFICANT_DATA_SET = frozenset()
        DEFAULT_FILE_STATUS = None
        DEFAULT_DIR_STATUS = None
        def __init__(self, name=None, dir_path=None, status=False, parent_file_status_snapshot=None):
            self._file_status_snapshot = parent_file_status_snapshot.narrowed_for_subdir(dir_path)
            self._exists = os.path.isdir(dir_path if dir_path else os.curdir)
            GenericWsFileDb.FileDir.__init__(self, name, dir_path, status=status)
        def _get_initial_status(self):
            return self.DEFAULT_DIR_STATUS
        def _get_current_status(self):
            # SCM related status changes will be detected at Db level
            if self._exists and not os.path.isdir(self._dir_path):
                return None
            return self.data.status
        def _add_subdir(self, name, dir_path=None, status=False, **kwargs):
            if not dir_path:
                dir_path = os.path.join(self._dir_path, name)
            self._subdirs[name] = self._new_dir(name=name, dir_path=dir_path, status=status, parent_file_status_snapshot=self._file_status_snapshot, **kwargs)
        def _get_current_hash_digest(self):
            h = hashlib.sha1()
            for item in os.listdir(self._dir_path):
                h.update(item)
            return h.digest()
        def _populate(self):
            h = hashlib.sha1()
            files_dict = {}
            for item in os.listdir(self._dir_path):
                h.update(item)
                dir_path = os.path.join(self._dir_path, item)
                if os.path.isdir(dir_path):
                    self._add_subdir(name=item, dir_path=dir_path)
                else:
                    files_dict[item] = Data(name=item, status=self.DEFAULT_FILE_STATUS, related_file_data=None)
            for file_path, status, rfd in self._file_status_snapshot.iterate_data():
                subdir, name = os.path.split(os.path.relpath(file_path, self._dir_path))
                if subdir:
                    while subdir:
                        base_sub_dir = subdir
                        subdir = os.path.dirname(subdir)
                    if base_sub_dir not in self._subdirs:
                        self._add_sub_dir(name=base_subdir, status=False)
                else:
                    if rfd:
                        rfd = RFD(path=os.path.relpath(rfd.path, self._dir_path), relation=rfd.relation)
                    files_dict[name] = Data(name=name, status=status, related_file_data=rfd)
            # presort this data for multiple access efficiency
            self._files_data = sorted(files_dict.itervalues())
            self._subdirs_data = sorted([s.data for s in self._subdirs.itervalues()])
            self._is_populated = True
            return h.digest()
    def __init__(self, **kwargs):
        h = hashlib.sha1()
        self._file_status_snapshot = self._extract_file_status_snapshot(self._get_file_data_text(h))
        self._db_digest = h.digest()
        GenericWsFileDb.__init__(self, parent_file_status_snapshot=self._file_status_snapshot)
    # NB the fetching of data is done in two steps to allow efficient "is_current" computation
    def _get_file_data_text(self, h):
        assert False, "_get_file_data_text() must be defined in child"
    def _extract_file_status_snapshot(self, file_data_text):
        assert False, "_extract_file_status_snapshot() must be defined in child"
    @property
    def is_current(self):
        h = hashlib.sha1()
        self._get_file_data_text(h)
        return h.digest() == self._db_digest and self.base_dir.is_current

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
        def add_file(self, path_parts, status, related_file_data=None):
            self._status_set.add(status)
            name = path_parts[0]
            if len(path_parts) == 1:
                self._files_data.append(Data(name=name, status=status, related_file_data=related_file_data))
            else:
                if name not in self._subdirs:
                    self._subdirs[name] = self._new_dir(name)
                self._subdirs[name].add_file(path_parts[1:], status, related_file_data)
        def _calculate_status(self):
            assert False, "_calculate_status() must be defined in child"
        def find_dir(self, dir_path):
            if not dir_path:
                return self
            sep_index = dir_path.find(os.sep)
            if sep_index == -1:
                return self._subdirs[dir_path]
            return self._subdirs[dir_path[:sep_index]].find_dir(dir_path[sep_index + 1:])
        def dirs_and_files(self, hide_clean=False, **kwargs):
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
        for file_path, status, related_file_data in self._iterate_file_data(pdt):
            self._base_dir.add_file(split_path(file_path), status, related_file_data)
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
    def dir_contents(self, dir_path='', hide_clean=False, **kwargs):
        tdir = self._base_dir.find_dir(dir_path)
        if not tdir:
            return ([], [])
        return tdir.dirs_and_files(hide_clean=hide_clean, **kwargs)
