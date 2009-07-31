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

import os, os.path, tempfile, pango, re
from gwsmhg_pkg import ifce, text_edit, utils, cmd_result, putils, ws_event

DEFAULT_NAME_EVARS = ["GIT_AUTHOR_NAME", "GECOS"]
DEFAULT_EMAIL_VARS = ["GIT_AUTHOR_EMAIL", "EMAIL_ADDRESS"]

FSTATUS_MODIFIED = 'M'
FSTATUS_ADDED = 'A'
FSTATUS_REMOVED = 'R'
FSTATUS_CLEAN = 'C'
FSTATUS_MISSING = '!'
FSTATUS_NOT_TRACKED = '?'
FSTATUS_IGNORED = 'I'
FSTATUS_ORIGIN = ' '
FSTATUS_UNRESOLVED = 'U'

FSTATUS_MODIFIED_SET = set([FSTATUS_MODIFIED, FSTATUS_ADDED, FSTATUS_REMOVED,
                           FSTATUS_MISSING, FSTATUS_UNRESOLVED])

class ScmDir:
    def __init__(self):
        self.status = None
        self.status_set = set()
        self.subdirs = {}
        self.files = {}
    def add_file(self, path_parts, status, origin=None):
        self.status_set.add(status)
        if len(path_parts) == 1:
            self.files[path_parts[0]] = (status, origin)
        else:
            if not self.subdirs.has_key(path_parts[0]):
                self.subdirs[path_parts[0]] = ScmDir()
            self.subdirs[path_parts[0]].add_file(path_parts[1:], status, origin)
    def update_status(self):
        if FSTATUS_UNRESOLVED in self.status_set:
            self.status = FSTATUS_UNRESOLVED
        elif self.status_set & FSTATUS_MODIFIED_SET:
            self.status = FSTATUS_MODIFIED
        elif self.status_set == set([FSTATUS_IGNORED]):
            self.status = FSTATUS_IGNORED
        elif self.status_set in [set([FSTATUS_NOT_TRACKED]), set([FSTATUS_NOT_TRACKED, FSTATUS_IGNORED])]:
            self.status = FSTATUS_NOT_TRACKED
        for key in self.subdirs.keys():
            self.subdirs[key].update_status()
    def _find_dir(self, dirpath_parts):
        if not dirpath_parts:
            return self
        elif self.subdirs.has_key(dirpath_parts[0]):
            return self.subdirs[dirpath_parts[0]]._find_dir(dirpath_parts[1:])
        else:
            return None
    def find_dir(self, dirpath):
        if not dirpath:
            return self
        return self._find_dir(dirpath.split(os.sep))
    def dirs_and_files(self, show_hidden=False):
        dkeys = self.subdirs.keys()
        dkeys.sort()
        dirs = []
        for dkey in dkeys:
            status = self.subdirs[dkey].status
            if not show_hidden and not status in [FSTATUS_UNRESOLVED, FSTATUS_MODIFIED]:
                if dkey[0] == '.' or status == FSTATUS_IGNORED:
                    continue
            dirs.append((dkey, status, None))
        files = []
        fkeys = self.files.keys()
        fkeys.sort()
        for fkey in fkeys:
            status = self.files[fkey][0]
            if not show_hidden and not status in FSTATUS_MODIFIED_SET:
                if fkey[0] == '.' or status == FSTATUS_IGNORED:
                    continue
            files.append((fkey, status, self.files[fkey][1]))
        return (dirs, files)

class ScmFileDb:
    def __init__(self, file_list, unresolved_file_list=[]):
        self.base_dir = ScmDir()
        lfile_list = len(file_list)
        index = 0
        while index < lfile_list:
            item = file_list[index]
            index += 1
            filename = item[2:]
            status = item[0]
            origin = None
            if status == FSTATUS_ADDED and index < lfile_list:
                if file_list[index][0] == FSTATUS_ORIGIN:
                    origin = file_list[index][2:]
                    index += 1
            elif filename in unresolved_file_list:
                status = FSTATUS_UNRESOLVED
            parts = filename.split(os.sep)
            self.base_dir.add_file(parts, status, origin)
    def add_file(self, filepath, status, origin=None):
        self.base_dir.add_file(filepath.split(os.sep), status, origin)
    def decorate_dirs(self):
        self.base_dir.update_status()
    def dir_contents(self, dirpath='', show_hidden=False):
        tdir = self.base_dir.find_dir(dirpath)
        if not tdir:
            return ([], [])
        return tdir.dirs_and_files(show_hidden)

class BaseInterface:
    def __init__(self, name):
        self.name = name
        self.status_deco_map = {
            None: (pango.STYLE_NORMAL, "black"),
            FSTATUS_CLEAN: (pango.STYLE_NORMAL, "black"),
            FSTATUS_MODIFIED: (pango.STYLE_NORMAL, "blue"),
            FSTATUS_ADDED: (pango.STYLE_NORMAL, "darkgreen"),
            FSTATUS_REMOVED: (pango.STYLE_NORMAL, "red"),
            FSTATUS_UNRESOLVED: (pango.STYLE_NORMAL, "magenta"),
            FSTATUS_MISSING: (pango.STYLE_ITALIC, "pink"),
            FSTATUS_NOT_TRACKED: (pango.STYLE_ITALIC, "cyan"),
            FSTATUS_IGNORED: (pango.STYLE_ITALIC, "grey"),
        }
        self.extra_info_sep = " <- "
        self._name_envars = DEFAULT_NAME_EVARS
        self._email_envars = DEFAULT_EMAIL_VARS
    def _inotify_warning(self, serr):
        return serr.strip() in ['(found dead inotify server socket; removing it)',
            '(inotify: received response from incompatible server version 1)']
    def get_extensions(self):
        res, sout, serr = utils.run_cmd("hg showconfig extensions")
        extens = []
        for line in sout.splitlines():
            preeq, posteq = line.split('=')
            extens.append(preeq.split('.')[-1])
        return extens
    def get_extension_enabled(self, exten):
        return exten in self.get_extensions()
    def get_author_name_and_email(self):
        cmd = 'hg showconfig ui.username'
        res, uiusername, serr = utils.run_cmd(cmd)
        if res == 0 and uiusername:
            return uiusername.strip()
        name = self._get_first_in_envar(self._name_envars)
        if not name:
            name = "UNKNOWN"
        email = self._get_first_in_envar(self._email_envars)
        if not email:
            email = "UNKNOWN"
        return "%s <%s>" % (name, email)
    def get_status_row_data(self):
        return (self.status_deco_map, self.extra_info_sep)
    def _map_result(self, result, ignore_err_re=None):
        outres, sout, serr = cmd_result.map_cmd_result(result, ignore_err_re)
        if outres != cmd_result.OK:
            for force_suggested in ["use -f to force", "not overwriting - file exists"]:
                if serr.find(force_suggested) != -1 or sout.find(force_suggested) != -1:
                    outres += cmd_result.SUGGEST_FORCE
        return (outres, sout, serr)
    def _file_list_to_I_string(self, file_list):
        return ' -I "%s"' % '" -I "'.join(file_list)
    def do_add_files(self, file_list, dry_run=False):
        cmd = 'hg add'
        if dry_run:
            cmd += ' -n --verbose'
        if file_list:
            cmd += utils.file_list_to_string(file_list)
        if dry_run:
            return self._map_result(utils.run_cmd(cmd))
        else:
            result = self._run_cmd_on_console(cmd)
            ws_event.notify_events(ws_event.FILE_ADD)
            return result
    def do_copy_files(self, file_list, target, force=False, dry_run=False):
        cmd = 'hg copy'
        if dry_run:
            cmd += ' -n --verbose'
        if force:
            cmd += ' -f'
        cmd += utils.file_list_to_string(file_list + [target])
        if dry_run:
            return self._map_result(utils.run_cmd(cmd))
        else:
            result = self._run_cmd_on_console(cmd)
            ws_event.notify_events(ws_event.FILE_ADD)
            return result
    def do_move_files(self, file_list, target, force=False, dry_run=False):
        cmd = 'hg rename'
        if dry_run:
            cmd += ' -n --verbose'
        if force:
            cmd += ' -f'
        cmd += utils.file_list_to_string(file_list + [target])
        if dry_run:
            return self._map_result(utils.run_cmd(cmd))
        else:
            result = self._run_cmd_on_console(cmd)
            ws_event.notify_events(ws_event.FILE_DEL|ws_event.FILE_ADD)
            return result
    def do_revert_files(self, file_list=[], dry_run=False):
        cmd = 'hg revert'
        if dry_run:
            cmd += ' -n --verbose'
        if file_list:
            cmd += utils.file_list_to_string(file_list)
        else:
            cmd += ' --all'
        if dry_run:
            return self._map_result(utils.run_cmd(cmd))
        else:
            result = self._run_cmd_on_console(cmd)
            ws_event.notify_events(ws_event.FILE_CHANGES)
            return result
    def do_delete_files(self, file_list):
        if ifce.log:
            ifce.log.start_cmd("Deleting: %s" % " ".join(file_list))
        serr = ""
        for filename in file_list:
            try:
                os.remove(filename)
                if ifce.log:
                    ifce.log.append_stdout(('Deleted: %s\n') % filename)
            except os.error, value:
                errmsg = ('%s: "%s"\n') % (value[1], filename)
                serr += errmsg
                if ifce.log:
                    ifce.log.append_stderr(errmsg)
        if ifce.log:
            ifce.log.end_cmd()
        ws_event.notify_events(ws_event.FILE_DEL)
        if serr:
            return (cmd_result.ERROR, "", serr)
        return (cmd_result.OK, "", "")
    def do_pull_from(self, rev=None, update=False, source=None):
        cmd = 'hg pull'
        if update:
            cmd += ' -u'
        if rev is not None:
            cmd += ' -r %s' % rev
        if source:
            cmd += ' "%s"' % source
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result[0]):
            events = ws_event.REPO_MOD
            if update:
                events |= ws_event.FILE_CHANGES
            ws_event.notify_events(events)
        return result

class SCMInterface(BaseInterface):
    def __init__(self):
        BaseInterface.__init__(self, "hg")
        self.cs_summary_template_lines = \
            [
                '{desc|firstline}',
                '{rev}',
                '{node}',
                '{date|isodate}',
                '{date|age}',
                '{author|person}',
                '{author|email}',
                '{tags}',
                '{branches}',
                '{desc}',
                '',
            ]
        self.cs_summary_template = '\\n'.join(self.cs_summary_template_lines)
        self.cs_table_template = '{rev}:{date|age}:{tags}:{branches}:{author|person}:{desc|firstline}\\n'
    def _map_cmd_result(self, result, ignore_err_re=None):
        if not result[0]:
            if self._inotify_warning(result[2]):
                return result
            return cmd_result.map_cmd_result(result, ignore_err_re=ignore_err_re)
        else:
            flags = cmd_result.ERROR
            if result[2].find('use -f to force') != -1:
                flags |= cmd_result.SUGGEST_FORCE
            if result[2].find('already exists') != -1:
                flags |= cmd_result.SUGGEST_RENAME
            if result[2].find('use \'hg merge\' or \'hg update -C\'') != -1:
                flags |= cmd_result.SUGGEST_MERGE_OR_DISCARD
            elif result[2].find('use \'hg update -C\'') != -1:
                flags |= cmd_result.SUGGEST_DISCARD
            return (flags, result[1], result[2])
    def _run_cmd_on_console(self, cmd):
        result = utils.run_cmd_in_console(cmd, ifce.log)
        return self._map_cmd_result(result)
    def get_default_commit_save_file(self):
        return os.path.join('.hg', 'gwsmhg.saved.commit')
    def _get_first_in_envar(self, envar_list):
        for envar in envar_list:
            try:
                value = os.environ[envar]
                if value != '':
                    return value
            except KeyError:
                continue
        return ''
    def get_root(self):
        cmd = 'hg root'
        res, root, serr = utils.run_cmd(cmd)
        if res != 0:
            return None
        return root.strip()
    def _get_qbase(self):
        cmd = 'hg log --template "{rev}" -r qbase'
        res, rev, serr = utils.run_cmd(cmd)
        if not res:
            return rev
        return None
    def _get_qparent(self):
        cmd = 'hg log --template "{rev}" -r qparent'
        res, rev, serr = utils.run_cmd(cmd)
        if not res:
            return rev
        return None
    def get_parents(self, rev=None):
        cmd = 'hg parents --template "{rev}\\n"'
        if rev is None:
            qbase = self._get_qbase()
            if qbase:
                rev = qbase
        if rev is not None:
            cmd += ' -r %s' % rev
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            revs = [sout]
        else:
            revs = []
            for line in sout.splitlines():
                revs.append(line)
        return (res, revs, serr)
    def _get_qbase_parents(self):
        res, parents, serr = self.get_parents('qbase')
        if res:
            # probably should pop up a problem report
            return []
        else:
            return parents
    def _unresolved_file_list(self,  fspath_list=[]):
        cmd = 'hg resolve --list'
        if fspath_list:
            cmd += utils.file_list_to_string(fspath_list)
        res, sout, serr = utils.run_cmd(cmd)
        files = []
        for line in sout.splitlines():
            if line[0] == FSTATUS_UNRESOLVED:
                files.append(line[2:])
        return files
    def get_ws_file_db(self):
        cmd = 'hg status -AC'
        qprev = self._get_qparent()
        if qprev is not None:
            cmd += ' --rev %s' % qprev
        res, sout, serr = utils.run_cmd(cmd)
        scm_file_db = ScmFileDb(sout.splitlines(), self._unresolved_file_list())
        scm_file_db.decorate_dirs()
        return scm_file_db
    def get_commit_file_db(self, fspath_list=[]):
        cmd = 'hg status -mardC'
        if fspath_list:
            cmd += utils.file_list_to_string(fspath_list)
        res, sout, serr = utils.run_cmd(cmd)
        scm_file_db = ScmFileDb(sout.splitlines(), self._unresolved_file_list())
        return scm_file_db
    def _css_line_index(self, tempfrag):
        return self.cs_summary_template_lines.index(tempfrag)
    def _process_change_set_summary(self, res, sout, serr):
        lines = sout.splitlines()
        summary = {}
        summary['PRECIS'] = lines[self._css_line_index('{desc|firstline}')]
        summary['REV'] = lines[self._css_line_index('{rev}')]
        summary['NODE'] = lines[self._css_line_index('{node}')]
        summary['DATE'] = lines[self._css_line_index('{date|isodate}')]
        summary['AGE'] = lines[self._css_line_index('{date|age}')]
        summary['AUTHOR'] = lines[self._css_line_index('{author|person}')]
        summary['EMAIL'] = lines[self._css_line_index('{author|email}')]
        summary['TAGS'] = lines[self._css_line_index('{tags}')]
        summary['BRANCHES'] = lines[self._css_line_index('{branches}')]
        summary['DESCR'] = '\n'.join(lines[self._css_line_index('{desc}'):])
        return (res, summary, serr)
    def get_change_set_summary(self, rev):
        cmd = 'hg log --template "%s" --rev %s' % (self.cs_summary_template, rev)
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        return self._process_change_set_summary(res, sout, serr)
    def get_change_set_files_db(self, rev):
        res, parents, serr = self.get_parents(rev)
        template = '{files}\\n{file_adds}\\n{file_dels}\\n'
        cmd = 'hg log --template "%s" --rev %s' % (template, rev)
        cs_file_db = ScmFileDb([])
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return cs_file_db
        lines = sout.splitlines()
        file_names = utils.string_to_file_list(lines[0])
        added_files = utils.string_to_file_list(lines[1])
        deleted_files = utils.string_to_file_list(lines[2])
        for name in file_names:
            if name in added_files:
                extra_info = None
                for parent in parents:
                    cmd = 'hg status -aC --rev %s --rev %s "%s"' % (parent, rev, name)
                    res, sout, serr = utils.run_cmd(cmd)
                    lines = sout.splitlines()
                    if len(lines) > 1 and lines[1][0] == ' ':
                        extra_info = lines[1].strip()
                        break
                cs_file_db.add_file(name, FSTATUS_ADDED, extra_info)
            elif name in deleted_files:
                cs_file_db.add_file(name, FSTATUS_REMOVED, None)
            else:
                cs_file_db.add_file(name, FSTATUS_MODIFIED, None)
        return cs_file_db
    def get_parents_data(self, rev=None):
        cmd = 'hg parents --template "%s"' % self.cs_table_template
        if rev is None:
            qbase = self._get_qbase()
            if qbase:
                rev = qbase
        if rev is not None:
            cmd += ' --rev %s' % str(rev)
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(':', 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_path_table_data(self):
        path_re = re.compile('^(\S*)\s+=\s+(\S*)\s*$')
        cmd = 'hg paths'
        res, sout, serr = utils.run_cmd(cmd)
        paths = []
        for line in sout.splitlines():
            match = path_re.match(line)
            if match:
                paths.append([match.group(1), match.group(2)])
        return (res, paths, serr)
    def get_outgoing_table_data(self, path=None):
        cmd = 'hg -q outgoing --template "%s"' % self.cs_table_template
        if path:
            cmd += ' "%s"' % path
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            if res == 1:
                return (cmd_result.OK, [], '')
            else:
                return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(':', 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_outgoing_rev(self, revarg):
        cmd = 'hg -q outgoing -n -l 1 --template "{rev}" --rev %s' % revarg
        return utils.run_cmd(cmd)
    def get_incoming_table_data(self, path=None):
        cmd = 'hg -q incoming --template "%s"' % self.cs_table_template
        if path:
            cmd += ' "%s"' % path
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            if res == 1:
                return (cmd_result.OK, [], '')
            else:
                return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(":", 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_incoming_rev(self, revarg):
        cmd = 'hg -q incoming -n -l 1 --template "{rev}" --rev %s' % revarg
        return utils.run_cmd(cmd)
    def get_is_incoming(self, rev, path=None):
        cmd = 'hg incoming -qnl1 --template "{rev}" --rev %s' % str(rev)
        if path:
            cmd += ' "%s"' % path
        res, sout, serr = utils.run_cmd(cmd)
        return sout == str(rev)
    def get_incoming_change_set_summary(self, rev, path=None):
        cmd = 'hg -q incoming --template "%s" -nl 1 --rev %s' % (self.cs_summary_template, rev)
        if path:
            cmd += ' "%s"' % path
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        return self._process_change_set_summary(res, sout, serr)
    def get_incoming_change_set_files_db(self, rev, path=None):
        template = '{files}\\n{file_adds}\\n{file_dels}\\n'
        cmd = 'hg -q incoming --template "%s" -nl 1 --rev %s' % (template, rev)
        if path:
            cmd += ' "%s"' % path
        cs_file_db = ScmFileDb([])
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return cs_file_db
        lines = sout.splitlines()
        file_names = utils.string_to_file_list(lines[0])
        added_files = utils.string_to_file_list(lines[1])
        deleted_files = utils.string_to_file_list(lines[2])
        files = []
        for name in file_names:
            if name in added_files:
                cs_file_db.add_file(name, FSTATUS_ADDED, None)
            elif name in deleted_files:
                cs_file_db.add_file(name, FSTATUS_REMOVED, None)
            else:
                cs_file_db.add_file(name, FSTATUS_MODIFIED, None)
        return cs_file_db
    def get_incoming_parents(self, rev, path=None):
        cmd = 'hg -q incoming --template "{parents}" -nl 1 --rev %s' % rev
        if path:
            cmd += ' "%s"' % path
        res, psout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, psout, serr)
        parents = []
        if psout:
            for item in psout.split():
                parents.append(item.split(':')[0])
        else:
            irev = int(rev)
            if irev > 0:
                parents = [str(irev - 1)]
        return (res, parents, serr)
    def get_incoming_parents_table_data(self, rev, path=None):
        res, parents, serr = self.get_incoming_parents(rev, path)
        if res != 0:
            return (res, parents, serr)
        plist = []
        base_cmd = 'hg -q incoming --template "%s" -nl 1' % self.cs_table_template
        for parent in parents:
            if not self.get_is_incoming(parent, path):
                # the parent is local
                res, sublist, serr = self.get_history_data(rev=parent)
                plist += sublist
                continue
            if path:
                cmd = base_cmd + ' --rev %s "%s"' % (parent, path)
            else:
                cmd = base_cmd + ' --rev %s' % parent
            res, sout, serr = utils.run_cmd(cmd)
            if res != 0:
                return (res, sout, serr)
            pdata = sout.strip().split(':', 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_incoming_diff(self, rev, path=None):
        cmd = 'hg incoming --patch -nl 1 --rev %s' % rev
        if path:
            cmd += ' "%s"' % path
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        lines = sout.splitlines()
        diffstat_si, patch_data = putils.trisect_patch_lines(lines)
        if not patch_data:
            return (res, '', err)
        else:
            patch = '\n'.join(lines[patch_data[0]:])
            return (res, patch, serr)
    def get_heads_data(self):
        if not self.get_root(): return (cmd_result.OK, [], '')
        cmd = 'hg heads --template "%s"' % self.cs_table_template
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(':', 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_history_data(self, rev=None, maxitems=None):
        if not self.get_root(): return (cmd_result.OK, [], '')
        cmd = 'hg log --template "%s"' % self.cs_table_template
        if maxitems:
            if rev is not None:
                rev2 = max(int(rev) - maxitems + 1, 0)
                cmd += ' --rev %d:%d' % (int(rev), rev2)
            else:
                cmd += ' -l %d' % maxitems
        elif rev is not None:
            cmd += ' --rev %s' % rev
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(':', 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_rev(self, revarg):
        cmd = 'hg log --template "{rev}" --rev %s' % revarg
        return utils.run_cmd(cmd)
    def get_tags_data(self):
        if not self.get_root(): return (cmd_result.OK, [], '')
        cmd = 'hg -v tags'
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        de = re.compile('^(\S+)\s*(\d+):(\S+)\s*(\S*)')
        tag_list = []
        template = '{rev}:{branches}:{date|age}:{author|person}:{desc|firstline}\\n'
        cmd = 'hg log --template "%s"' % template
        lastrev = None
        for line in sout.splitlines():
            dat = de.match(line)
            if dat:
                rev = dat.group(2)
                if rev != lastrev:
                    cmd += ' -r %s' % rev
                    lastrev = rev
                tag_list.append([dat.group(1), dat.group(4), int(dat.group(2))])
        res, sout, serr = utils.run_cmd(cmd)
        index = 0
        ntags = len(tag_list)
        for line in sout.splitlines():
            fields = line.split(':', 4)
            rev = int(fields[0])
            addon = fields[1:]
            while index < ntags and tag_list[index][2] == rev:
                tag_list[index].extend(addon)
                index += 1
        return (res, tag_list, serr)
    def get_tags_list_for_table(self):
        cmd = 'hg tags'
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        de = re.compile('^(\S+)\s*\d+:')
        tag_list = []
        for line in sout.splitlines():
            dat = de.match(line)
            if dat:
                tag_list.append([dat.group(1)])
        return (res, tag_list, serr)
    def get_branches_data(self):
        if not self.get_root(): return (cmd_result.OK, [], '')
        cmd = 'hg branches'
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        de = re.compile('^(\S+)\s*(\d+):')
        branch_list = []
        for line in sout.splitlines():
            dat = de.match(line)
            branch_list.append([dat.group(1), int(dat.group(2))])
        cmd = 'hg log --template "{tags}:{date|age}:{author|person}:{desc|firstline}" --rev '
        for branch in branch_list:
            res, sout, serr = utils.run_cmd(cmd + str(branch[1]))
            branch += sout.split(':', 3)
        return (res, branch_list, serr)
    def get_branches_list_for_table(self):
        cmd = 'hg branches'
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        de = re.compile('^(\S+)\s*\d+:')
        tag_list = []
        for line in sout.splitlines():
            dat = de.match(line)
            tag_list.append([dat.group(1)])
        return (res, tag_list, serr)
    def do_init(self, dir=None):
        if dir:
            cmd = "hg init %s" % dir
        else:
            cmd = "hg init"
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD|ws_event.CHECKOUT)
        return result
    def do_commit_change(self, msg, file_list=[]):
        cmd = 'hg -v commit'
        if msg:
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        if file_list:
            cmd += self._file_list_to_I_string(file_list)
        res, sout, serr = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD|ws_event.CHECKOUT)
        return (res, sout, serr)
    def do_remove_files(self, file_list, force=False):
        if force:
            cmd = 'hg remove -f'
        else:
            cmd = 'hg remove'
        result = self._run_cmd_on_console(cmd + utils.file_list_to_string(file_list))
        ws_event.notify_events(ws_event.FILE_DEL)
        return result
    def get_diff_for_files(self, file_list, fromrev, torev=None):
        # because of the likelihood of a multiple parents we'll never use the
        # zero rev option so fromrev is compulsory (except when there are no
        # revisions yet e.g. in a brand new repository)
        cmd = 'hg diff'
        if fromrev:
            cmd += ' --rev %s' % fromrev
        else:
            assert self.get_parents() == (0, [], '')
        if torev:
            cmd += ' --rev %s' % torev
        if file_list:
            cmd += utils.file_list_to_string(file_list)
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            res = cmd_result.ERROR
        return (res, sout, serr)
    def do_update_workspace(self, rev=None, discard=False):
        cmd = 'hg update'
        if discard:
            cmd += ' -C'
        if rev is not None:
            cmd += ' -r %s' %rev
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.CHECKOUT)
        return result
    def do_merge_workspace(self, rev=None, force=False):
        cmd = 'hg merge'
        if force:
            cmd += ' -f'
        if rev is not None:
            cmd += ' -r %s' %rev
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.CHECKOUT)
        return result
    def do_push_to(self, rev=None, force=False, path=None):
        cmd = cmd = 'hg push'
        if force:
            cmd += ' -f'
        if rev is not None:
            cmd += ' -r %s' %rev
        if path:
            cmd += ' "%s"' % path
        return self._run_cmd_on_console(cmd)
    def do_verify_repo(self):
        return self._run_cmd_on_console('hg verify')
    def do_rollback_repo(self):
        result = self._run_cmd_on_console('hg rollback')
        ws_event.notify_events(ws_event.REPO_MOD|ws_event.CHECKOUT)
        return result
    def do_set_tag(self, tag, rev=None, local=False, force=False, msg=None):
        if not tag:
            return (cmd_result.OK, "", "")
        cmd = 'hg tag'
        if force:
            cmd += ' -f'
        if local:
            cmd += ' -l'
        if rev is not None:
            cmd += ' -r %s' % rev
        if msg:
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        cmd += ' %s' % tag
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result[0]):
            ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_remove_tag(self, tag, local=False, msg=None):
        cmd = 'hg tag --remove'
        if local:
            cmd += ' -l'
        if msg:
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        cmd += ' %s' % tag
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result[0]):
            ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_move_tag(self, tag, rev, msg=None):
        cmd = 'hg tag -f -r %s' % rev
        if msg:
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        cmd += " %s" % tag
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result[0]):
            ws_event.notify_events(ws_event.REPO_MOD)
        return result        
    def do_set_branch(self, branch, force=False):
        cmd = 'hg branch'
        if force:
            cmd += ' -f'
        cmd += ' %s' % branch
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_clone_as(self, path, target=None):
        cmd = 'hg clone "%s"' % path
        if target:
            cmd += ' "%s"' % target
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_backout(self, rev, msg, merge=False, parent=None):
        cmd = 'hg backout'
        if msg:
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        if merge:
            cmd += ' --merge'
        if parent:
            cmd += ' --parent %s' % parent
        if rev is not None:
            cmd += ' %s' % rev
        result = self._run_cmd_on_console(cmd)
        if merge:
            ws_event.notify_events(ws_event.REPO_MOD|ws_event.FILE_CHANGES)
        else:
            ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def get_pbranch_table_data(self):
        if not self.get_root(): return (cmd_result.OK, [], '')
        cmd = 'hg pgraph --title --with-name'
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        de = re.compile('^([^]]*)\[(\S+)\]\s*(.*)')
        branch_list = []
        for line in sout.splitlines():
            dat = de.match(line)
            if dat:
                branch_list.append([dat.group(2), dat.group(3), dat.group(1).find('@') >= 0])
        cmd = 'hg pstatus %s'
        for branch in branch_list:
            res, sout, serr = utils.run_cmd(cmd % branch[0])
            branch.append(sout.strip() == '')
        return (res, branch_list, serr)
    def get_pbranch_description(self, pbranch):
        if pbranch:
            cmd = 'hg pmessage %s' % pbranch
        else:
            cmd = 'hg pmessage'
        res, sout, serr = utils.run_cmd(cmd)
        descr_lines = sout.splitlines()[1:]
        return (res, '\n'.join(descr_lines), serr)
    def get_pdiff_for_files(self, file_list=[], pbranch=None):
        cmd = 'hg pdiff'
        if pbranch:
            cmd += ' %s' % pbranch
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
        return utils.run_cmd(cmd)
    def get_pstatus(self, pbranch=None):
        cmd = 'hg pstatus'
        if pbranch:
            cmd += ' %s' % pbranch
        return utils.run_cmd(cmd)
    def get_pgraph(self):
        cmd = 'hg pgraph --title --with-name'
        return utils.run_cmd(cmd)
    def do_set_pbranch_description(self, pbranch, descr):
        cmd = 'hg peditmessage -t "%s"' % descr.replace('"', '\\"')
        if pbranch:
            cmd += ' %s' % pbranch
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_new_pbranch(self, name, msg, preserve=False):
        cmd = 'hg pnew'
        if msg:
            cmd += ' -t "%s"' % msg.replace('"', '\\"')
        if preserve:
            cmd += ' --preserve'
        cmd += ' %s' % name
        result = self._run_cmd_on_console(cmd)
        events = ws_event.REPO_MOD|ws_event.CHECKOUT
        if not preserve:
            events |= ws_event.FILE_CHANGES
        ws_event.notify_events(events)
        return result
    def do_pmerge(self, pbranches=[]):
        cmd = 'hg pmerge'
        if pbranches:
            cmd += ' %s' % ' '.join(pbranches)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD|ws_event.CHECKOUT|ws_event.FILE_CHANGES)
        return result
    def do_pbackout(self, files=[]):
        cmd = 'hg pbackout'
        if files:
            cmd += ' %s' % utils.file_list_to_string(files)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD|ws_event.CHECKOUT|ws_event.FILE_CHANGES)
        return result

class _WsUpdateStateMgr:
    # We save this data in a file so that it survives closing/opening the GUI
    def __init__(self):
        self._saved_state_msg = 'hg patches saved state'
        self._state_file = '.hg/gwsmhg.pm.wsu.state'
        self._copy_file = '.hg/gwsmhg.pm.wsu.patches.copy'
        self._get_copy_re = re.compile('^copy\s*\S*\s*to\s*(\S*)\n$')
    def _write_to_named_file(self, fname, text):
        file = open(fname, 'w')
        file.write(text)
        file.close()
    def _read_from_named_file(self, fname):
        file = open(fname, 'r')
        text = file.read()
        file.close()
        return text.strip()
    def start(self, serr, state):
        match = self._get_copy_re.match(serr)
        if match:
            self._write_to_named_file(self._copy_file, os.path.basename(match.group(1)))
        self.set_state(state)
    def is_in_progress(self):
        return os.path.exists(self._state_file)
    def tip_is_patches_saved_state(self):
        cmd = 'hg log --template "{desc|firstline}" --rev tip'
        res, sout, serr = utils.run_cmd(cmd)
        return sout == self._saved_state_msg
    def parent_is_patches_saved_state(self):
        cmd = 'hg parent --template "{desc|firstline}"'
        res, sout, serr = utils.run_cmd(cmd)
        return sout == self._saved_state_msg
    def set_state(self, state):
        self._write_to_named_file(self._state_file, state)
    def get_state_is_in(self, state_list):
        if not os.path.exists(self._state_file):
            return False
        state = self._read_from_named_file(self._state_file)
        return state in state_list
    def get_patches_copy_dir(self):
        return self._read_from_named_file(self._copy_file)
    def finish(self):
        for path in self._copy_file, self._state_file:
            if os.path.exists(path):
                os.remove(path)

ENABLE_MQ_MSG = \
'''
This functionality requires Mercurial Queues (mq) to be enabled.
To enable mq add the line:

hgext.mq=

to the [extensions] section of your ~.hgrc file.  e.g.

[extensions]
hgext.mq=
'''

class PMInterface(BaseInterface):
    def __init__(self):
        BaseInterface.__init__(self, "MQ")
        self._ws_update_mgr = _WsUpdateStateMgr()
        self.not_enabled_response = (cmd_result.ERROR, ENABLE_MQ_MSG, "")
        self._adding_re = re.compile("^adding\s.*$")
        self._qpush_re = re.compile("^(merging|applying)\s.*$", re.M)
    def _map_cmd_result(self, result, ignore_err_re=None):
        if not result[0]:
            if self._inotify_warning(result[1]):
                return result
            return cmd_result.map_cmd_result(result, ignore_err_re=ignore_err_re)
        else:
            flags = cmd_result.ERROR
            if result[2].find('use -f to force') != -1:
                flags |= cmd_result.SUGGEST_FORCE
            if result[2].find('refresh first') != -1:
                flags |= cmd_result.SUGGEST_REFRESH
            if result[2].find('(revert --all, qpush to recover)') != -1:
                flags |= cmd_result.SUGGEST_RECOVER
            return (flags, result[1], result[2])
    def _run_cmd_on_console(self, cmd, ignore_err_re=None):
        result = utils.run_cmd_in_console(cmd, ifce.log)
        return self._map_cmd_result(result, ignore_err_re=ignore_err_re)
    def get_enabled(self):
        return self.get_extension_enabled('mq')
    def get_parent(self, patch):
        parent = 'qparent'
        for applied_patch in self.get_applied_patches():
            if patch == applied_patch:
                return parent
            else:
                parent = applied_patch
        return None
    def get_patch_file_db(self, patch=None):
        if not self.get_enabled():
            return ScmFileDb([])
        if patch and not self.get_patch_is_applied(patch):
            pfn = self.get_patch_file_name(patch)
            result, file_list = putils.get_patch_files(pfn, status=True, decorated=True)
            if result:
                return ScmFileDb(file_list)
            else:
                return ScmFileDb([])
        top = self.get_top_patch()
        if not top:
            # either we're not in an mq playground or no patches are applied
            return ScmFileDb([])
        cmd = 'hg status -mardC'
        if patch:
            parent = self.get_parent(patch)
            cmd += ' --rev %s --rev %s' % (parent, patch)
        else:
            parent = self.get_parent(top)
            cmd += ' --rev %s' % parent
        res, sout, serr = utils.run_cmd(cmd)
        return ScmFileDb(sout.splitlines())
    def get_in_progress(self):
        if not self.get_enabled():
            return False
        return (self.get_top_patch() is not None) or \
            self._ws_update_mgr.is_in_progress()
    def get_applied_patches(self):
        if not self.get_enabled():
            return []
        res, op, err = utils.run_cmd('hg qapplied')
        if res != 0:
                return []
        return op.splitlines()
    def get_unapplied_patches(self):
        if not self.get_enabled():
            return []
        res, op, err = utils.run_cmd('hg qunapplied')
        if res != 0:
                return []
        return op.splitlines()
    def get_patch_is_applied(self, patch):
        return patch in self.get_applied_patches()
    def get_top_patch(self):
        res, sout, serr = utils.run_cmd('hg qtop')
        if res:
            return None
        else:
            return sout.strip()
    def get_base_patch(self):
        res, sout, serr = utils.run_cmd('hg qapplied')
        if res or not sout:
            return None
        else:
            return sout.splitlines()[0]
    def get_next_patch(self):
        res, sout, serr = utils.run_cmd('hg qnext')
        if res or not sout:
            return None
        else:
            return sout.strip()
    def get_diff_for_files(self, file_list=[], patch=None):
        if patch:
            parent = self.get_parent(patch)
            if not parent:
                # the patch is not applied
                pfn = self.get_patch_file_name(patch)
                result, diff = putils.get_patch_diff(pfn, file_list)
                if result:
                    return (cmd_result.OK, diff, '')
                else:
                    return (cmd_result.WARNING, '', diff)
        else:
            top = self.get_top_patch()
            if top:
                parent = self.get_parent(top)
            else:
                return (cmd_result.OK, '', '')
        cmd = 'hg diff --rev %s' % parent
        if patch:
            cmd += ' --rev %s' % patch
        if file_list:
            cmd += utils.file_list_to_string(file_list)
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            res = cmd_result.ERROR
        return (res, sout, serr)
    def do_refresh(self):
        result = self._run_cmd_on_console('hg qrefresh')
        if not result[0]:
            ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.REPO_MOD)
        return result
    def do_pop_to(self, patch=None, force=False):
        if patch is None:
            if force:
                cmd = 'hg qpop -f'
            else:
                cmd = 'hg qpop'
        elif patch is '':
            if force:
                cmd = 'hg qpop -f -a'
            else:
                cmd = 'hg qpop -a'
        else:
            if force:
                cmd = 'hg qpop -f %s' % patch
            else:
                cmd = 'hg qpop %s' % patch
        result = self._run_cmd_on_console(cmd)
        if not self.get_in_progress():
            ws_event.notify_events(ws_event.PMIC_CHANGE, False)
        events = ws_event.CHECKOUT|ws_event.REPO_MOD|ws_event.FILE_CHANGES
        ws_event.notify_events(events)
        return result
    def do_push_to(self, patch=None, force=False, merge=False):
        in_charge = self.get_in_progress()
        if merge:
            cmd = 'hg -y qpush -m'
        else:
            cmd = 'hg qpush'
        if patch is None:
            if force:
                result = self._run_cmd_on_console('%s -f' % cmd, ignore_err_re=self._qpush_re)
            else:
                result = self._run_cmd_on_console(cmd, ignore_err_re=self._qpush_re)
        elif patch is "":
            if force:
                result = self._run_cmd_on_console('%s -f -a' % cmd, ignore_err_re=self._qpush_re)
            else:
                result = self._run_cmd_on_console('%s -a' % cmd, ignore_err_re=self._qpush_re)
        else:
            if force:
                result = self._run_cmd_on_console('%s -f %s' % (cmd, patch), ignore_err_re=self._qpush_re)
            else:
                result = self._run_cmd_on_console('%s %s' % (cmd, patch), ignore_err_re=self._qpush_re)
        if not in_charge:
            ws_event.notify_events(ws_event.PMIC_CHANGE, True)
        events = ws_event.CHECKOUT|ws_event.REPO_MOD|ws_event.FILE_CHANGES
        ws_event.notify_events(events)
        if not result[0] and merge and len(self.get_unapplied_patches()) == 0:
            self._ws_update_mgr.set_state('merged')
        return result
    def get_patch_file_name(self, patch):
        return os.path.join(os.getcwd(), '.hg', 'patches', patch)
    def get_patch_description(self, patch):
        pfn = self.get_patch_file_name(patch)
        res, descr_lines = putils.get_patch_descr_lines(pfn)
        descr = '\n'.join(descr_lines) + '\n'
        if res:
            return (cmd_result.OK, descr, "")
        else:
            return (cmd_result.ERROR, descr, "Error reading description to \"%s\" patch file" % patch)
    def do_set_patch_description(self, patch, descr):
        pfn = self.get_patch_file_name(patch)
        ifce.log.start_cmd("set description for: %s" %patch)
        res = putils.set_patch_descr_lines(pfn, descr.splitlines())
        if res:
            ifce.log.append_stdout(descr)
            res = cmd_result.OK
            serr = ""
        else:
            serr = "Error writing description to \"%s\" patch file" % patch
            ifce.log.append_stderr(serr)
            res = cmd_result.ERROR
        ifce.log.end_cmd()
        return (res, "", serr)
    def get_description_is_finish_ready(self, patch):
        pfn = self.get_patch_file_name(patch)
        res, pf_descr_lines = putils.get_patch_descr_lines(pfn)
        pf_descr = '\n'.join(pf_descr_lines).strip()
        if not pf_descr:
            return False
        cmd = 'hg log --template "{desc}" --rev %s' % patch
        res, rep_descr, sout = utils.run_cmd(cmd)
        if pf_descr != rep_descr.strip():
            top = self.get_top_patch()
            if top == patch:
                utils.run_cmd('hg qrefresh')
            else:
                # let's hope the user doesn't mind having the top patch refreshed
                utils.run_cmd('hg qrefresh')
                utils.run_cmd('hg qgoto %s' % patch)
                utils.run_cmd('hg qrefresh')
                utils.run_cmd('hg qgoto %s' % top)
        return True
    def do_finish_patch(self, patch):
        result = self._run_cmd_on_console('hg qfinish %s' % patch)
        if not self.get_in_progress():
            ws_event.notify_events(ws_event.PMIC_CHANGE, False)
        events = ws_event.CHECKOUT|ws_event.REPO_MOD|ws_event.FILE_CHANGES
        ws_event.notify_events(events)
        return result
    def do_rename_patch(self, old_name, new_name):
        cmd = 'hg qrename %s %s' % (old_name, new_name)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_delete_patch(self, patch):
        result = self._run_cmd_on_console('hg qdelete %s' % patch)
        ws_event.notify_events(ws_event.UNAPPLIED_PATCH_MOD)
        return result
    def do_fold_patch(self, patch):
        result = self._run_cmd_on_console('hg qfold %s' % patch)
        ws_event.notify_events(ws_event.FILES_CHANGE)
        return result
    def do_import_patch(self, patch_file_name, as_patch_name=None, force=False):
        cmd = 'hg qimport'
        if as_patch_name:
            cmd += ' -n "%s"' % as_patch_name
        if force:
            cmd += ' -f'
        cmd += ' "%s"' % patch_file_name
        res, sout, serr = self._run_cmd_on_console(cmd, ignore_err_re=self._adding_re)
        if res and re.search("already exists", serr):
            res |= cmd_result.SUGGEST_FORCE_OR_RENAME
        ws_event.notify_events(ws_event.UNAPPLIED_PATCH_MOD)
        return (res, sout, serr)
    def do_new_patch(self, patch_name_raw, force=False):
        in_charge = self.get_in_progress()
        patch_name = re.sub('\s', '_', patch_name_raw)
        if force:
            cmd = 'hg qnew -f %s' % patch_name
        else:
            cmd = 'hg qnew %s' % patch_name
        res, sout, serr = self._run_cmd_on_console(cmd)
        if not in_charge:
            ws_event.notify_events(ws_event.PMIC_CHANGE, True)
        events = ws_event.CHECKOUT|ws_event.REPO_MOD
        ws_event.notify_events(events)
        if res & cmd_result.SUGGEST_REFRESH:
            res |= cmd_result.SUGGEST_FORCE
        return (res, sout, serr)
    def do_remove_files(self, file_list, force=False):
        applied_count = len(self.get_applied_patches())
        if not file_list or applied_count == 0:
            return (cmd_result.OK, '', '')
        elif applied_count == 1:
            parent = 'qparent'
        else:
            res, sout, serr = utils.run_cmd('hg qprev')
            parent = sout.strip()
        cmd = 'hg revert --rev %s' % parent
        if force:
            cmd += ' -f'
        cmd += utils.file_list_to_string(file_list)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.FILE_DEL)
        return result
    def do_save_queue_state_for_update(self):
        cmd = 'hg qsave -e -c'
        result = self._run_cmd_on_console(cmd)
        self._ws_update_mgr.start(result[2], 'qsaved')
        ws_event.notify_events(ws_event.CHECKOUT|ws_event.FILE_CHANGES|ws_event.REPO_MOD)
        return result
    def do_pull_from(self, rev=None, source=None):
        result = BaseInterface.do_pull_from(self, rev=rev, source=source)
        if cmd_result.is_less_than_error(result[0]):
            self._ws_update_mgr.set_state('pulled')
        return result
    def do_update_workspace(self, rev=None):
        cmd = 'hg update -C'
        if rev is not None:
            cmd += ' -r %s' %rev
        result = self._run_cmd_on_console(cmd)
        if not result[0]:
            ws_event.notify_events(ws_event.CHECKOUT)
            self._ws_update_mgr.set_state('updated')
        return result
    def do_clean_up_after_update(self):
        pcd = self._ws_update_mgr.get_patches_copy_dir()
        if pcd:
            top_patch = self.get_top_patch()
            if top_patch:
                utils.run_cmd('hg qpop -a')
            self._ws_update_mgr.finish()
            result = self._run_cmd_on_console('hg qpop -a -n %s' % pcd)
            if top_patch:
                utils.run_cmd('hg qgoto %s' % top_patch)
                ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.REPO_MOD)
            else:
                ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.REPO_MOD)
                ws_event.notify_events(ws_event.PMIC_CHANGE, False)
            return result
        else:
            return (cmd_result.INFO, 'Saved patch directory not found.', '')
    def get_ws_update_qsave_ready(self, unapplied_count=None, applied_count=None):
        if unapplied_count is None:
            unapplied_count = len(self.get_unapplied_patches())
        if applied_count is None:
            applied_count = len(self.get_applied_patches())
        return applied_count and not unapplied_count and not self._ws_update_mgr.is_in_progress()
    def get_ws_update_ready(self, applied_count=None):
        if applied_count is None:
            applied_count = len(self.get_applied_patches())
        if self._ws_update_mgr.tip_is_patches_saved_state():
            return False
        return not applied_count and self._ws_update_mgr.get_state_is_in(["pulled"])
    def get_ws_update_merge_ready(self, unapplied_count=None):
        if unapplied_count is None:
            unapplied_count = len(self.get_unapplied_patches())
        if self._ws_update_mgr.parent_is_patches_saved_state():
            return False
        return unapplied_count and self._ws_update_mgr.get_state_is_in(["updated"])
    def get_ws_update_clean_up_ready(self, applied_count=None):
        return self._ws_update_mgr.get_state_is_in(["merged"])
    def get_ws_update_pull_ready(self, applied_count=None):
        if applied_count is None:
            applied_count = len(self.get_applied_patches())
        return not applied_count and self._ws_update_mgr.get_state_is_in(["qsaved"])
    def get_ws_update_to_ready(self, applied_count=None):
        if applied_count is None:
            applied_count = len(self.get_applied_patches())
        return not applied_count and self._ws_update_mgr.get_state_is_in(["qsaved", "pulled"])
