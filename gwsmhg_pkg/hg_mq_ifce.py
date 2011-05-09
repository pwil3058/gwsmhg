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

import os, os.path, tempfile, pango, re, time, collections
from gwsmhg_pkg import ifce, utils, cmd_result, putils, ws_event, const, fsdb

newlines_not_allowed_in_cmd = os.name == 'nt' or os.name == 'dos'

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

class ScmDir(fsdb.GenDir):
    def __init__(self):
        fsdb.GenDir.__init__(self)
    def _new_dir(self):
        return ScmDir()
    def _update_own_status(self):
        if FSTATUS_UNRESOLVED in self.status_set:
            self.status = FSTATUS_UNRESOLVED
        elif self.status_set & FSTATUS_MODIFIED_SET:
            self.status = FSTATUS_MODIFIED
        elif self.status_set == set([FSTATUS_IGNORED]):
            self.status = FSTATUS_IGNORED
        elif self.status_set in [set([FSTATUS_NOT_TRACKED]), set([FSTATUS_NOT_TRACKED, FSTATUS_IGNORED])]:
            self.status = FSTATUS_NOT_TRACKED
        elif self.status_set in [set([FSTATUS_CLEAN]), set([FSTATUS_CLEAN, FSTATUS_IGNORED])]:
            self.status = FSTATUS_CLEAN
    def _is_hidden_dir(self, dkey):
        status = self.subdirs[dkey].status
        if status not in [FSTATUS_UNRESOLVED, FSTATUS_MODIFIED]:
            return dkey[0] == '.' or status == FSTATUS_IGNORED
        return False
    def _is_hidden_file(self, fdata):
        if fdata.status not in FSTATUS_MODIFIED_SET:
            return fdata.name[0] == '.' or fdata.status == FSTATUS_IGNORED
        return False

class ScmFileDb(fsdb.GenFileDb):
    def __init__(self, file_list, unresolved_file_list=list()):
        fsdb.GenFileDb.__init__(self, ScmDir)
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

Deco = collections.namedtuple('Deco', ['style', 'foreground'])

_hg_version_re = re.compile('[^(]*\(version ([0-9][0-9.]*)\).*')

def _get_hg_version():
    result = utils.run_cmd('hg version')
    match = _hg_version_re.match(result.stdout)
    if match:
        parts = match.group(1).split('.')
        return tuple(int(part) for part in parts)
    else:
        return None

def _is_hg_version_ge(version):
    hg_version = _get_hg_version()
    for index in range(len(version)):
        try:
            if hg_version[index] < version[index]:
                return False
            elif hg_version[index] > version[index]:
                return True
        except IndexError:
            return False
    return True

def _changes_exist():
    result = utils.run_cmd('hg status -m')
    return result.stdout != ''

class BaseInterface:
    def __init__(self, name):
        self.name = name
        self.status_deco_map = {
            None: Deco(pango.STYLE_NORMAL, "black"),
            FSTATUS_CLEAN: Deco(pango.STYLE_NORMAL, "black"),
            FSTATUS_MODIFIED: Deco(pango.STYLE_NORMAL, "blue"),
            FSTATUS_ADDED: Deco(pango.STYLE_NORMAL, "darkgreen"),
            FSTATUS_REMOVED: Deco(pango.STYLE_NORMAL, "red"),
            FSTATUS_UNRESOLVED: Deco(pango.STYLE_NORMAL, "magenta"),
            FSTATUS_MISSING: Deco(pango.STYLE_ITALIC, "pink"),
            FSTATUS_NOT_TRACKED: Deco(pango.STYLE_ITALIC, "cyan"),
            FSTATUS_IGNORED: Deco(pango.STYLE_ITALIC, "grey"),
        }
        self.extra_info_sep = " <- "
        self._name_envars = DEFAULT_NAME_EVARS
        self._email_envars = DEFAULT_EMAIL_VARS
    def _map_cmd_result(self, result, ignore_err_re=None):
        assert False, "Must be defined in child"
    def _run_cmd_on_console(self, cmd, input_text=None, ignore_err_re=None):
        result = utils.run_cmd_in_console(cmd, ifce.log, input_text)
        return self._map_cmd_result(result, ignore_err_re=ignore_err_re)
    def _inotify_warning(self, serr):
        return serr.strip() in ['(found dead inotify server socket; removing it)',
            '(inotify: received response from incompatible server version 1)']
    def get_extensions(self):
        result = utils.run_cmd("hg showconfig extensions")
        extens = []
        for line in result.stdout.splitlines():
            preeq, posteq = line.split('=')
            extens.append(preeq.split('.')[-1])
        return extens
    def get_extension_enabled(self, exten):
        return exten in self.get_extensions()
    def get_author_name_and_email(self):
        cmd = 'hg showconfig ui.username'
        result = utils.run_cmd(cmd)
        if result.eflags == 0 and result.stdout:
            return result.stdout.strip()
        name = utils.get_first_in_envar(self._name_envars)
        if not name:
            name = "UNKNOWN"
        email = utils.get_first_in_envar(self._email_envars)
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
        return cmd_result.Result(outres, sout, serr)
    def _file_list_to_I_string(self, file_list):
        mod_file_list = []
        for file_name in file_list:
            if file_name.count(' ') == 0:
                mod_file_list.append('-I %s' % file_name)
            else:
                mod_file_list.append('-I "%s"' % file_name)
        return ' '.join(mod_file_list)
    def _create_temp_file_for_msg(self, msg):
        msg_fd, msg_file_name = tempfile.mkstemp()
        os.write(msg_fd, msg)
        os.close(msg_fd)
        return msg_file_name
    def do_add_files(self, file_list, dry_run=False):
        cmd = 'hg add'
        if dry_run:
            cmd += ' -n --verbose'
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
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
        cmd += ' %s' % utils.file_list_to_string(file_list + [target])
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
        cmd += ' %s' % utils.file_list_to_string(file_list + [target])
        if dry_run:
            return self._map_result(utils.run_cmd(cmd))
        else:
            result = self._run_cmd_on_console(cmd)
            ws_event.notify_events(ws_event.FILE_DEL|ws_event.FILE_ADD)
            return result
    def do_revert_files(self, file_list=None, dry_run=False):
        cmd = 'hg revert'
        if dry_run:
            cmd += ' -n --verbose'
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
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
            ifce.log.start_cmd('Deleting: %s' % utils.file_list_to_string(file_list))
        serr = ""
        for filename in file_list:
            try:
                os.remove(filename)
                if ifce.log:
                    ifce.log.append_stdout(('Deleted: %s\n') % filename)
            except os.error as value:
                errmsg = ('%s: "%s"\n') % (value[1], filename)
                serr += errmsg
                if ifce.log:
                    ifce.log.append_stderr(errmsg)
        if ifce.log:
            ifce.log.end_cmd()
        ws_event.notify_events(ws_event.FILE_DEL)
        if serr:
            return cmd_result.Result(cmd_result.ERROR, "", serr)
        return cmd_result.Result(cmd_result.OK, "", "")
    def do_pull_from(self, rev=None, update=False, source=None):
        cmd = 'hg pull'
        if update:
            cmd += ' -u'
        if rev is not None:
            cmd += ' -r %s' % rev
        if source:
            cmd += ' "%s"' % source
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result.eflags):
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
        self.cs_table_template = '{rev}:{node}:{date|age}:{tags}:{branches}:{author|person}:{desc|firstline}\\n'
    def _map_cmd_result(self, result, ignore_err_re=None):
        if not result.eflags:
            if self._inotify_warning(result.stderr):
                return result
            return cmd_result.map_cmd_result(result, ignore_err_re=ignore_err_re)
        else:
            flags = cmd_result.ERROR
            if result.stderr.find('use -f to force') != -1:
                flags |= cmd_result.SUGGEST_FORCE
            if result.stderr.find('already exists') != -1:
                flags |= cmd_result.SUGGEST_RENAME
            if result.stderr.find('use \'hg merge\' or \'hg update -C\'') != -1:
                flags |= cmd_result.SUGGEST_MERGE_OR_DISCARD
            elif result.stderr.find('use \'hg update -C\'') != -1:
                flags |= cmd_result.SUGGEST_DISCARD
            return cmd_result.Result(flags, result.stdout, result.stderr)
    def get_default_commit_save_file(self):
        return os.path.join('.hg', 'gwsmhg.saved.commit')
    def get_root(self):
        cmd = 'hg root'
        result = utils.run_cmd(cmd)
        return result.stdout.strip() if result.eflags == 0 and result.stdout else None
    def _get_qbase(self):
        cmd = 'hg log --template "{rev}" -r qbase'
        result = utils.run_cmd(cmd)
        return result.stdout if result.eflags == 0 and result.stdout else None
    def _get_qparent(self):
        cmd = 'hg log --template "{rev}" -r qparent'
        result = utils.run_cmd(cmd)
        return result.stdout if result.eflags == 0 and result.stdout else None
    def get_parents(self, rev=None):
        cmd = 'hg parents --template "{rev}\\n"'
        if rev is None:
            qbase = self._get_qbase()
            if qbase:
                rev = qbase
        if rev is not None:
            cmd += ' -r %s' % rev
        result = utils.run_cmd(cmd)
        if result.eflags:
            raise cmd_result.Failure(result)
        return result.stdout.splitlines()
    def _unresolved_file_list(self,  fspath_list=None):
        cmd = 'hg resolve --list'
        if fspath_list:
            cmd += ' %s' % utils.file_list_to_string(fspath_list)
        result = utils.run_cmd(cmd)
        if result.eflags != 0:
            return []
        return [line[2:] for line in result.stdout.splitlines() if line[0] == FSTATUS_UNRESOLVED]
    def get_ws_file_db(self):
        cmd = 'hg status -AC'
        qprev = self._get_qparent()
        if qprev is not None:
            cmd += ' --rev %s' % qprev
        result = utils.run_cmd(cmd)
        scm_file_db = ScmFileDb(result.stdout.splitlines(), self._unresolved_file_list())
        scm_file_db.decorate_dirs()
        return scm_file_db
    def get_commit_file_db(self, fspath_list=None):
        cmd = 'hg status -mardC'
        if fspath_list:
            cmd += ' %s' % utils.file_list_to_string(fspath_list)
        result = utils.run_cmd(cmd)
        scm_file_db = ScmFileDb(result.stdout.splitlines(), self._unresolved_file_list())
        return scm_file_db
    def _css_line_index(self, tempfrag):
        return self.cs_summary_template_lines.index(tempfrag)
    def _process_change_set_summary(self, lines):
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
        return summary
    def get_change_set_summary(self, rev):
        cmd = 'hg log --template "%s" --rev %s' % (self.cs_summary_template, rev)
        result = utils.run_cmd(cmd)
        if result.eflags:
            raise cmd_result.Failure(result)
        return self._process_change_set_summary(result.stdout.splitlines())
    def get_change_set_files_db(self, rev):
        parents = self.get_parents(rev)
        template = '{files}\\n{file_adds}\\n{file_dels}\\n'
        cmd = 'hg log --template "%s" --rev %s' % (template, rev)
        cs_file_db = ScmFileDb([])
        result = utils.run_cmd(cmd)
        if result.eflags:
            return cs_file_db
        lines = result.stdout.splitlines()
        file_names = utils.string_to_file_list(lines[0])
        added_files = utils.string_to_file_list(lines[1])
        deleted_files = utils.string_to_file_list(lines[2])
        for name in file_names:
            if name in added_files:
                extra_info = None
                for parent in parents:
                    cmd = 'hg status -aC --rev %s --rev %s "%s"' % (parent, rev, name)
                    result = utils.run_cmd(cmd)
                    lines = result.stdout.splitlines()
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
        result = utils.run_cmd(cmd)
        if result.eflags != 0:
            return []
        plist = []
        for line in result.stdout.splitlines():
            pdata = line.split(':', 6)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return plist
    def get_path_table_data(self):
        path_re = re.compile('^(\S*)\s+=\s+(\S*.*)\s*$')
        cmd = 'hg paths'
        result = utils.run_cmd(cmd)
        paths = []
        for line in result.stdout.splitlines():
            match = path_re.match(line)
            if match:
                paths.append([match.group(1), match.group(2)])
        return paths
    def get_outgoing_table_data(self, path=None):
        cmd = 'hg -q outgoing --template "%s"' % self.cs_table_template
        if path:
            cmd += ' "%s"' % path
        result = utils.run_cmd(cmd)
        if result.eflags not in [0, 1]:
            raise cmd_result.Failure(result)
        plist = []
        for line in result.stdout.splitlines():
            pdata = line.split(':', 6)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return plist
    def get_outgoing_rev(self, revarg):
        cmd = 'hg -q outgoing -n -l 1 --template "{rev}" --rev %s' % revarg
        return utils.run_cmd(cmd).stdout
    def get_incoming_table_data(self, path=None):
        cmd = 'hg -q incoming --template "%s"' % self.cs_table_template
        if path:
            cmd += ' "%s"' % path
        result = utils.run_cmd(cmd)
        if result.eflags not in [0, 1]:
            raise cmd_result.Failure(result)
        plist = []
        for line in result.stdout.splitlines():
            pdata = line.split(":", 6)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return plist
    def get_incoming_rev(self, revarg):
        cmd = 'hg -q incoming -n -l 1 --template "{rev}" --rev %s' % revarg
        return utils.run_cmd(cmd).stdout
    def get_is_incoming(self, rev, path=None):
        cmd = 'hg incoming -qnl1 --template "{rev}" --rev %s' % str(rev)
        if path:
            cmd += ' "%s"' % path
        return utils.run_cmd(cmd).stdout == str(rev)
    def get_incoming_change_set_summary(self, rev, path=None):
        cmd = 'hg -q incoming --template "%s" -nl 1 --rev %s' % (self.cs_summary_template, rev)
        if path:
            cmd += ' "%s"' % path
        result = utils.run_cmd(cmd)
        if result.eflags:
            raise cmd_result.Failure(result)
        return self._process_change_set_summary(result.stdout.splitlines())
    def get_incoming_change_set_files_db(self, rev, path=None):
        template = '{files}\\n{file_adds}\\n{file_dels}\\n'
        cmd = 'hg -q incoming --template "%s" -nl 1 --rev %s' % (template, rev)
        if path:
            cmd += ' "%s"' % path
        cs_file_db = ScmFileDb([])
        result = utils.run_cmd(cmd)
        if result.eflags:
            return cs_file_db
        lines = result.stdout.splitlines()
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
        result = utils.run_cmd(cmd)
        if result.eflags != 0:
            raise cmd_result.Failure(result)
        parents = []
        if result.stdout:
            return [item.split(':')[0] for item in result.stdout.split()]
        else:
            irev = int(rev)
            if irev > 0:
                return [str(irev - 1)]
        return []
    def get_incoming_parents_table_data(self, rev, path=None):
        parents = self.get_incoming_parents(rev, path)
        plist = []
        base_cmd = 'hg -q incoming --template "%s" -nl 1' % self.cs_table_template
        for parent in parents:
            if not self.get_is_incoming(parent, path):
                # the parent is local
                plist += self.get_history_data(rev=parent)
                continue
            if path:
                cmd = base_cmd + ' --rev %s "%s"' % (parent, path)
            else:
                cmd = base_cmd + ' --rev %s' % parent
            result = utils.run_cmd(cmd)
            if result.eflags != 0:
                raise cmd_result.Failure(result)
            pdata = result.stdout.strip().split(':', 6)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return plist
    def get_incoming_diff(self, rev, path=None):
        cmd = 'hg incoming --patch -nl 1 --rev %s' % rev
        if path:
            cmd += ' "%s"' % path
        result = utils.run_cmd(cmd)
        if result.eflags:
            raise cmd_result.Failure(result)
        is_ok, diff = putils.get_patch_diff_fm_text(result.stdout)
        if is_ok:
            return diff
        else:
            return ''
    def get_heads_data(self):
        if not self.get_root():
            return []
        cmd = 'hg heads --template "%s"' % self.cs_table_template
        result = utils.run_cmd(cmd)
        if result.eflags != 0:
            raise cmd_result.Failure(result)
        plist = []
        for line in result.stdout.splitlines():
            pdata = line.split(':', 6)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return plist
    def get_history_data(self, rev=None, maxitems=None):
        if not self.get_root():
            return []
        cmd = 'hg log --template "%s"' % self.cs_table_template
        if maxitems:
            if rev is not None:
                rev2 = max(int(rev) - maxitems + 1, 0)
                cmd += ' --rev %d:%d' % (int(rev), rev2)
            else:
                cmd += ' -l %d' % maxitems
        elif rev is not None:
            cmd += ' --rev %s' % rev
        result = utils.run_cmd(cmd)
        if result.eflags != 0:
            raise cmd_result.Failure(result)
        plist = []
        for line in result.stdout.splitlines():
            pdata = line.split(':', 6)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return plist
    def get_rev(self, revarg):
        cmd = 'hg log --template "{rev}" --rev %s' % revarg
        return utils.run_cmd(cmd).stdout
    def get_tags_data(self):
        if not self.get_root():
            return []
        cmd = 'hg -v tags'
        result = utils.run_cmd(cmd)
        if result.eflags:
            raise cmd_result.Failure(result)
        dre = re.compile('^(\S+)\s*(\d+):(\S+)\s*(\S*)')
        tag_list = []
        template = '{rev}:{branches}:{date|age}:{author|person}:{desc|firstline}\\n'
        cmd = 'hg log --template "%s"' % template
        lastrev = None
        for line in result.stdout.splitlines():
            dat = dre.match(line)
            if dat:
                rev = dat.group(2)
                if rev != lastrev:
                    cmd += ' -r %s' % rev
                    lastrev = rev
                tag_list.append([dat.group(1), dat.group(4), int(dat.group(2))])
        result = utils.run_cmd(cmd)
        index = 0
        ntags = len(tag_list)
        for line in result.stdout.splitlines():
            fields = line.split(':', 4)
            rev = int(fields[0])
            addon = fields[1:]
            while index < ntags and tag_list[index][2] == rev:
                tag_list[index].extend(addon)
                index += 1
        return tag_list
    def get_tags_list_for_table(self):
        cmd = 'hg tags'
        result = utils.run_cmd(cmd)
        if result.eflags:
            raise cmd_result.Failure(result)
        dre = re.compile('^(\S+)\s*\d+:')
        tag_list = []
        for line in result.stdout.splitlines():
            dat = dre.match(line)
            if dat:
                tag_list.append([dat.group(1)])
        return tag_list
    def get_branches_data(self):
        if not self.get_root():
            return []
        cmd = 'hg branches'
        result = utils.run_cmd(cmd)
        if result.eflags:
            raise cmd_result.Failure(result)
        dre = re.compile('^(\S+)\s*(\d+):')
        branch_list = []
        for line in result.stdout.splitlines():
            dat = dre.match(line)
            branch_list.append([dat.group(1), int(dat.group(2))])
        cmd = 'hg log --template "{tags}:{date|age}:{author|person}:{desc|firstline}" --rev '
        for branch in branch_list:
            result = utils.run_cmd(cmd + str(branch[1]))
            branch += result.stdout.split(':', 3)
        return branch_list
    def get_branches_list_for_table(self):
        cmd = 'hg branches'
        result = utils.run_cmd(cmd)
        if result.eflags:
            raise cmd_result.Failure(result)
        dre = re.compile('^(\S+)\s*\d+:')
        tag_list = []
        for line in result.stdout.splitlines():
            dat = dre.match(line)
            tag_list.append([dat.group(1)])
        return tag_list
    def do_init(self, dir_name=None):
        if dir_name:
            cmd = "hg init %s" % dir_name
        else:
            cmd = "hg init"
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD|ws_event.CHECKOUT)
        return result
    def do_commit_change(self, msg, file_list=None):
        cmd = 'hg -v commit'
        msg_file_name = None
        if msg:
            if newlines_not_allowed_in_cmd:
                msg_file_name = self._create_temp_file_for_msg(msg)
                cmd += ' --logfile "%s"' % msg_file_name
            else:
                cmd += ' -m "%s"' % msg.replace('"', '\\"')
        if file_list:
            cmd += ' %s' % self._file_list_to_I_string(file_list)
        result = self._run_cmd_on_console(cmd)
        if msg_file_name is not None:
            os.remove(msg_file_name)
        ws_event.notify_events(ws_event.REPO_MOD|ws_event.CHECKOUT)
        return result
    def do_remove_files(self, file_list, force=False):
        if force:
            cmd = 'hg remove -f'
        else:
            cmd = 'hg remove'
        result = self._run_cmd_on_console(cmd + ' %s' % utils.file_list_to_string(file_list))
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
            assert not self.get_parents()
        if torev:
            cmd += ' --rev %s' % torev
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
        result = utils.run_cmd(cmd)
        if result.eflags != 0:
            raise cmd_result.Failure(result)
        return result.stdout
    def launch_extdiff_for_ws(self, file_list=None):
        cmd = 'hg extdiff'
        rev = self._get_qparent()
        if rev:
            cmd += ' --rev %s' % rev
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
        return utils.run_cmd_in_bgnd(cmd)
    def launch_extdiff_for_changeset(self, rev, file_list=None):
        cmd = 'hg extdiff --change %s' % rev
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
        return utils.run_cmd_in_bgnd(cmd)
    def do_update_workspace(self, rev=None, discard=False):
        cmd = 'hg update'
        if discard:
            cmd += ' -C'
        if rev is not None:
            cmd += ' -r %s' % rev
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.CHECKOUT)
        return result
    def do_merge_workspace(self, rev=None, force=False):
        cmd = 'hg merge'
        if force:
            cmd += ' -f'
        if rev is not None:
            cmd += ' -r %s' % rev
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.CHECKOUT)
        return result
    def do_resolve_workspace(self, file_list=None):
        cmd = 'hg resolve'
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
        else:
            cmd += ' --all'
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.FILE_CHANGES)
        return result
    def do_mark_files_resolved(self, file_list):
        cmd = 'hg resolve --mark %s' % utils.file_list_to_string(file_list)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.FILE_CHANGES)
        return result
    def do_mark_files_unresolved(self, file_list):
        cmd = 'hg resolve --unmark %s' % utils.file_list_to_string(file_list)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.FILE_CHANGES)
        return result
    def do_push_to(self, rev=None, force=False, path=None):
        cmd = cmd = 'hg push'
        if force:
            cmd += ' -f'
        if rev is not None:
            cmd += ' -r %s' % rev
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
            return cmd_result.Result(cmd_result.OK, "", "")
        cmd = 'hg tag'
        if force:
            cmd += ' -f'
        if local:
            cmd += ' -l'
        if rev is not None:
            cmd += ' -r %s' % rev
        if msg:
            if newlines_not_allowed_in_cmd:
                # no alternatives to -m available so just replace the new lines
                lines = msg.splitlines()
                if len(lines) > 1:
                    msg = ' '.join(lines)
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        cmd += ' %s' % tag
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result.eflags):
            ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_remove_tag(self, tag, local=False, msg=None):
        cmd = 'hg tag --remove'
        if local:
            cmd += ' -l'
        if msg:
            if newlines_not_allowed_in_cmd:
                # no alternatives to -m available so just replace the new lines
                lines = msg.splitlines()
                if len(lines) > 1:
                    msg = ' '.join(lines)
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        cmd += ' %s' % tag
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result.eflags):
            ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_move_tag(self, tag, rev, msg=None):
        cmd = 'hg tag -f -r %s' % rev
        if msg:
            if newlines_not_allowed_in_cmd:
                # no alternatives to -m available so just replace the new lines
                lines = msg.splitlines()
                if len(lines) > 1:
                    msg = ' '.join(lines)
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        cmd += " %s" % tag
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result.eflags):
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
        msg_file_name = None
        if msg:
            if newlines_not_allowed_in_cmd:
                msg_file_name = self._create_temp_file_for_msg(msg)
                cmd += ' --logfile "%s"' % msg_file_name
            else:
                cmd += ' -m "%s"' % msg.replace('"', '\\"')
        if merge:
            cmd += ' --merge'
        if parent:
            cmd += ' --parent %s' % parent
        if rev is not None:
            cmd += ' %s' % rev
        result = self._run_cmd_on_console(cmd)
        if msg_file_name is not None:
            os.remove(msg_file_name)
        if merge:
            ws_event.notify_events(ws_event.REPO_MOD|ws_event.FILE_CHANGES)
        else:
            ws_event.notify_events(ws_event.REPO_MOD)
        return result

class _WsUpdateStateMgr:
    # We save this data in a file so that it survives closing/opening the GUI
    def __init__(self):
        self._saved_state_msg = 'hg patches saved state'
        self._state_file = '.hg/gwsmhg.pm.wsu.state'
        self._copy_file = '.hg/gwsmhg.pm.wsu.patches.copy'
        self._get_copy_re = re.compile('^copy\s*\S*\s*to\s*(\S*)\n$')
    def _write_to_named_file(self, fname, text):
        fobj = open(fname, 'w')
        fobj.write(text)
        fobj.close()
    def _read_from_named_file(self, fname):
        fobj = open(fname, 'r')
        text = fobj.read()
        fobj.close()
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
        return utils.run_cmd(cmd).stdout == self._saved_state_msg
    def parent_is_patches_saved_state(self):
        cmd = 'hg parent --template "{desc|firstline}"'
        return utils.run_cmd(cmd).stdout == self._saved_state_msg
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

_qguard_re = re.compile("^\s*([+-].*)\s*$")

def _extract_name_and_guards(string):
    name, gstring = string.split(':', 1)
    match = _qguard_re.match(gstring)
    if match:
        return name, match.group(1).split()
    else:
        return name, []

PatchData = collections.namedtuple('PatchData', ['name', 'state', 'guards'])

class PMInterface(BaseInterface):
    def __init__(self):
        BaseInterface.__init__(self, "MQ")
        self._ws_update_mgr = _WsUpdateStateMgr()
        self.not_enabled_response = cmd_result.Result(cmd_result.ERROR, ENABLE_MQ_MSG, "")
        self._is_enabled = False
        self._enabled_checked_at = None
        self.update_is_enabled()
        self._adding_re = re.compile("^adding\s.*$")
        self._qpush_re = re.compile("^(merging|applying)\s.*$", re.M)
        self._qguard_re = re.compile("^[^:]*:\s*([+-].*)\s*$")
    def _map_cmd_result(self, result, ignore_err_re=None):
        if not result.eflags:
            if self._inotify_warning(result.stdout):
                return result
            return cmd_result.map_cmd_result(result, ignore_err_re=ignore_err_re)
        else:
            flags = cmd_result.ERROR
            if result.stderr.find('use -f to force') != -1:
                flags |= cmd_result.SUGGEST_FORCE
            if result.stderr.find('refresh first') != -1:
                flags |= cmd_result.SUGGEST_REFRESH
            if result.stderr.find('(revert --all, qpush to recover)') != -1:
                flags |= cmd_result.SUGGEST_RECOVER
            if result.stdout.find('errors during apply, please fix and refresh') != -1:
                flags = cmd_result.WARNING
            return cmd_result.Result(flags, result.stdout, result.stderr)
    def update_is_enabled(self):
        self._is_enabled = self.get_extension_enabled('mq')
        self._enabled_checked_at = time.time()
    def get_enabled(self):
        if (time.time() - self._enabled_checked_at) > 20.0:
            self.update_is_enabled()
        return self._is_enabled
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
        return ScmFileDb(utils.run_cmd(cmd).stdout.splitlines())
    def get_in_progress(self):
        if not self.get_enabled():
            return False
        return (self.get_top_patch() is not None) or \
            self._ws_update_mgr.is_in_progress()
    def get_all_patches_data(self):
        output = []
        if not self.get_enabled():
            return output
        patch_plus_guard_list = utils.run_cmd('hg qguard -l').stdout.splitlines()
        applied_patches = self.get_applied_patches()
        if len(applied_patches) > 0:
            top_patch = applied_patches[-1]
            for ppg in patch_plus_guard_list:
                name, guards = _extract_name_and_guards(ppg)
                if name in applied_patches:
                    if name == top_patch:
                        state = const.TOP_PATCH
                    else:
                        state = const.APPLIED
                else:
                    state = const.NOT_APPLIED
                output.append(PatchData(name, state, guards))
        else:
            for ppg in patch_plus_guard_list:
                name, guards = _extract_name_and_guards(ppg)
                output.append(PatchData(name, const.NOT_APPLIED, guards))
        return output
    def get_applied_patches(self):
        if not self.get_enabled():
            return []
        result = utils.run_cmd('hg qapplied')
        return result.stdout.splitlines() if result.eflags == 0 else []
    def get_unapplied_patches(self):
        if not self.get_enabled():
            return []
        result = utils.run_cmd('hg qunapplied')
        return result.stdout.splitlines() if result.eflags == 0 else []
    def get_all_patches(self):
        if not self.get_enabled():
            return []
        result = utils.run_cmd('hg qseries')
        return result.stdout.splitlines() if result.eflags == 0 else []
    def get_patch_is_applied(self, patch):
        return patch in self.get_applied_patches()
    def get_patch_guards(self, patch):
        if not self.get_enabled():
            return []
        result = utils.run_cmd('hg qguard ' + patch)
        if result.eflags != 0:
            return []
        match = self._qguard_re.match(result.stdout.strip())
        return match.group(1).split() if match else []
    def get_selected_guards(self):
        result = utils.run_cmd('hg qselect')
        if result.eflags != 0 or result.stdout.strip() == "no active guards":
            return []
        return result.stdout.split()
    def get_top_patch(self):
        result = utils.run_cmd('hg qtop')
        return result.stdout.strip() if result.eflags == 0 else None
    def get_base_patch(self):
        result = utils.run_cmd('hg qapplied')
        return result.stdout.splitlines()[0] if result.stdout and result.eflags == 0 else None
    def get_next_patch(self):
        result = utils.run_cmd('hg qnext')
        return result.stdout.strip() if result.stdout and result.eflags == 0 else None
    def get_diff_for_files(self, file_list=None, patch=None):
        if patch:
            parent = self.get_parent(patch)
            if not parent:
                # the patch is not applied
                pfn = self.get_patch_file_name(patch)
                result, diff = putils.get_patch_diff(pfn, file_list)
                if result:
                    return diff
                else:
                    raise cmd_result.Failure(cmd_result.Result(cmd_result.WARNING, '', diff))
        else:
            top = self.get_top_patch()
            if top:
                parent = self.get_parent(top)
            else:
                return ''
        cmd = 'hg diff --rev %s' % parent
        if patch:
            cmd += ' --rev %s' % patch
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
        result = utils.run_cmd(cmd)
        if result.eflags != 0:
            raise cmd_result.Failure(result)
        return result.stdout
    def launch_extdiff_for_ws(self, file_list=None):
        cmd = 'hg extdiff --rev %s' % self.get_parent(self.get_top_patch())
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
        return utils.run_cmd_in_bgnd(cmd)
    def launch_extdiff_for_patch(self, patch, file_list=None):
        cmd = 'hg extdiff --change %s' % patch
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
        return utils.run_cmd_in_bgnd(cmd)
    def do_select_guards(self, guards):
        if not guards:
            guards = "--none"
        result = self._run_cmd_on_console('hg qselect %s' % guards)
        ws_event.notify_events(ws_event.PATCH_MODIFY)
        return result
    def do_set_patch_guards(self, patch_name, guards):
        cmd = 'hg qguard '
        if not guards:
            cmd += "--none %s" % patch_name
        else:
            cmd += "-- %s %s" % (patch_name, guards)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.PATCH_MODIFY)
        return result
    def do_recover_interrupted_refresh(self):
        self._run_cmd_on_console('hg revert --all')
        self._run_cmd_on_console('hg qpush')
        ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.PATCH_PUSH)
    def do_refresh(self, notify=True):
        result = self._run_cmd_on_console('hg qrefresh')
        if notify and not cmd_result.is_error(result.eflags):
            ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.PATCH_REFRESH)
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
        if cmd_result.is_less_than_error(result.eflags):
            events = ws_event.CHECKOUT|ws_event.PATCH_POP|ws_event.FILE_CHANGES
            if not self.get_in_progress():
                events |= ws_event.PMIC_CHANGE
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
        if cmd_result.is_less_than_error(result.eflags):
            events = ws_event.CHECKOUT|ws_event.PATCH_PUSH|ws_event.FILE_CHANGES
            if not in_charge:
                events |= ws_event.PMIC_CHANGE
            ws_event.notify_events(events)
            if merge and len(self.get_unapplied_patches()) == 0:
                self._ws_update_mgr.set_state('merged')
        return result
    def get_patch_file_name(self, patch):
        return os.path.join(os.getcwd(), '.hg', 'patches', patch)
    def get_patch_description(self, patch):
        if patch:
            cmd = 'hg qheader %s' % patch
        else:
            cmd = 'hg qheader'
        result = utils.run_cmd(cmd)
        if result.eflags:
            raise cmd_result.Failure(result)
        return result.stdout
    def do_set_patch_description(self, patch, descr):
        pfn = self.get_patch_file_name(patch)
        ifce.log.start_cmd("set description for: %s" %patch)
        if putils.set_patch_descr_lines(pfn, descr.splitlines()):
            ifce.log.append_stdout(descr)
            serr = ''
        else:
            serr = 'Error writing description to "%s" patch file' % patch
            ifce.log.append_stderr(serr)
        ifce.log.end_cmd()
        return cmd_result.Result(cmd_result.ERROR if serr else cmd_result.OK, '', serr)
    def get_description_is_finish_ready(self, patch):
        try:
            pf_descr = self.get_patch_description(patch)
            if not pf_descr:
                return False
        except cmd_result.Failure:
            return False
        cmd = 'hg log --template "{desc}" --rev %s' % patch
        result = utils.run_cmd(cmd)
        if pf_descr != result.stdout.strip():
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
        events = ws_event.CHECKOUT|ws_event.REPO_MOD|ws_event.FILE_CHANGES|ws_event.PATCH_DELETE|ws_event.PATCH_POP
        if not self.get_in_progress():
                    events |= ws_event.PMIC_CHANGE
        ws_event.notify_events(events)
        return result
    def do_rename_patch(self, old_name, new_name):
        cmd = 'hg qrename %s %s' % (old_name, new_name)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.PATCH_CREATE|ws_event.PATCH_DELETE)
        return result
    def do_delete_patch(self, patch):
        result = self._run_cmd_on_console('hg qdelete %s' % patch)
        ws_event.notify_events(ws_event.PATCH_DELETE)
        return result
    def do_fold_patch(self, patch):
        result = self._run_cmd_on_console('hg qfold %s' % patch)
        ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.PATCH_DELETED)
        return result
    def do_import_patch(self, patch_file_name, as_patch_name=None, force=False):
        cmd = 'hg qimport'
        if as_patch_name:
            cmd += ' -n "%s"' % as_patch_name
        if force:
            cmd += ' -f'
        cmd += ' "%s"' % patch_file_name
        result = self._run_cmd_on_console(cmd, ignore_err_re=self._adding_re)
        ws_event.notify_events(ws_event.PATCH_CREATE)
        if result.eflags and re.search("already exists", result.stderr):
            return result.Result(result.eflags | cmd_result.SUGGEST_FORCE_OR_RENAME, result.stdout, result.stderr)
        return result
    def do_new_patch(self, patch_name_raw, force=False):
        in_charge = self.get_in_progress()
        patch_name = re.sub('\s', '_', patch_name_raw)
        if _is_hg_version_ge((1,5)):
            if _changes_exist() and not force:
                return cmd_result.Result(cmd_result.ERROR_SUGGEST_FORCE_OR_REFRESH, '', 'Uncommited/unrefreshed changes exist!!!')
            else:
                cmd = 'hg qnew %s' % patch_name
        else:
            if force:
                cmd = 'hg qnew -f %s' % patch_name
            else:
                cmd = 'hg qnew %s' % patch_name
        result = self._run_cmd_on_console(cmd)
        events = ws_event.CHECKOUT|ws_event.PATCH_CREATE|ws_event.PATCH_PUSH
        if not in_charge:
            events |= ws_event.PMIC_CHANGE
        ws_event.notify_events(events)
        if result.eflags & cmd_result.SUGGEST_REFRESH:
            return result.Result(result.eflags | cmd_result.SUGGEST_FORCE, result.stdout, result.stderr)
        return result
    def do_remove_files(self, file_list, force=False):
        applied_count = len(self.get_applied_patches())
        if not file_list or applied_count == 0:
            return cmd_result.Result(cmd_result.OK, '', '')
        elif applied_count == 1:
            parent = 'qparent'
        else:
            result = utils.run_cmd('hg qprev')
            parent = result.stdout.strip()
        cmd = 'hg revert --rev %s' % parent
        if force:
            cmd += ' -f'
        cmd += ' %s' % utils.file_list_to_string(file_list)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.FILE_DEL)
        return result
    def do_save_queue_state_for_update(self):
        cmd = 'hg qsave -e -c'
        result = self._run_cmd_on_console(cmd)
        self._ws_update_mgr.start(result.stderr, 'qsaved')
        ws_event.notify_events(ws_event.CHECKOUT|ws_event.FILE_CHANGES|ws_event.REPO_MOD|ws_event.PATCH_CHANGES)
        return result
    def do_pull_from(self, rev=None, update=False, source=None):
        result = BaseInterface.do_pull_from(self, rev=rev, update=update, source=source)
        if cmd_result.is_less_than_error(result.eflags):
            self._ws_update_mgr.set_state('pulled')
        return result
    def do_update_workspace(self, rev=None):
        cmd = 'hg update -C'
        if rev is not None:
            cmd += ' -r %s' % rev
        result = self._run_cmd_on_console(cmd)
        if not result.eflags:
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
                ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.REPO_MOD|ws_event.PATCH_CHANGES)
            else:
                ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.REPO_MOD|ws_event.PATCH_CHANGES|ws_event.PMIC_CHANGE)
            return result
        else:
            return cmd_result.Result(cmd_result.WARNING, 'Saved patch directory not found.', '')
    def get_ws_update_qsave_ready(self, unapplied_count, applied_count):
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
