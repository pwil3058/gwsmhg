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

def _hg_cmd_str(cmd, rootdir, gflags=''):
    if rootdir:
        return 'hg -R "%s" %s %s' % (rootdir, gflags, cmd)
    else:
        return 'hg %s %s' % (gflags, cmd)

class BaseInterface:
    def __init__(self, name):
        self.name = name
        self.status_deco_map = {
            None: (pango.STYLE_NORMAL, "black"),
            "M": (pango.STYLE_NORMAL, "blue"),
            "A": (pango.STYLE_NORMAL, "darkgreen"),
            "R": (pango.STYLE_NORMAL, "red"),
            "C": (pango.STYLE_NORMAL, "black"),
            "!": (pango.STYLE_ITALIC, "pink"),
            "?": (pango.STYLE_ITALIC, "cyan"),
            "I": (pango.STYLE_ITALIC, "grey"),
        }
        self.extra_info_sep = " <- "
        self.modified_dir_status = "M"
        self.default_nonexistant_status = "!"
        self.ignored_statuses = ("I",)
        self.modification_statuses = ("M", "A", "R", "!")
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
    def get_author_name_and_email(self, rootdir=None):
        cmd = _hg_cmd_str('showconfig ui.username', rootdir)
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
        return (self.status_deco_map, self.extra_info_sep, self.modified_dir_status, self.default_nonexistant_status)
    def _map_result(self, result, ignore_err_re=None):
        outres, sout, serr = cmd_result.map_cmd_result(result, ignore_err_re)
        if outres != cmd_result.OK:
            for force_suggested in ["use -f to force", "not overwriting - file exists"]:
                if serr.find(force_suggested) != -1 or sout.find(force_suggested) != -1:
                    outres += cmd_result.SUGGEST_FORCE
        return (outres, sout, serr)
    def _file_list_to_I_string(self, file_list):
        return ' -I "%s"' % '" -I "'.join(file_list)
    def do_add_files(self, file_list, dry_run=False, rootdir=None):
        cmd = _hg_cmd_str('add', rootdir)
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
    def do_copy_files(self, file_list, target, force=False, dry_run=False, rootdir=None):
        cmd = _hg_cmd_str('copy', rootdir)
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
    def do_move_files(self, file_list, target, force=False, dry_run=False, rootdir=None):
        cmd = _hg_cmd_str('rename', rootdir)
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
    def do_revert_files(self, file_list=[], dry_run=False, rootdir=None):
        cmd = _hg_cmd_str('revert', rootdir)
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
    def do_pull_from(self, rev=None, update=False, source=None, rootdir=None):
        cmd = _hg_cmd_str('pull', rootdir)
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
        self.tracked_statuses = (None, "C") + self.modification_statuses
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
            if self._inotify_warning(result[1]):
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
    def get_default_commit_save_file(self, rootdir=None):
        if rootdir:
            return os.path.join(os.path.abspath(rootdir), '.hg', 'gwsmhg.saved.commit')
        else:
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
    def get_root(self, rootdir=None):
        cmd = _hg_cmd_str('root', rootdir)
        res, root, serr = utils.run_cmd(cmd)
        if res != 0:
            return None
        return root.strip()
    def _get_qbase(self, rootdir=None):
        cmd = _hg_cmd_str('log --template "{rev}" -r qbase', rootdir)
        res, rev, serr = utils.run_cmd(cmd)
        if not res:
            return rev
        return None
    def get_parents(self, rev=None, rootdir=None):
        cmd = _hg_cmd_str('parents --template "{rev}\\n"', rootdir)
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
    def _get_qbase_parents(self, rootdir=None):
        res, parents, serr = self.get_parents('qbase', rootdir=rootdir)
        if res:
            # probably should pop up a problem report
            return []
        else:
            return parents
    def get_file_status_lists(self, fspath_list=[], revs=[], rootdir=None):
        cmd = _hg_cmd_str('status -marduiC', rootdir)
        if not revs:
            revs = self._get_qbase_parents(rootdir=rootdir)
        if revs:
            for rev in revs:
                cmd += ' --rev %s' % rev
        if fspath_list:
            cmd += utils.file_list_to_string(fspath_list)
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, [], sout + serr)
        modified = []
        ignored = []
        others = []
        lines = sout.splitlines()
        numlines = len(lines)
        index = 0
        while index < numlines:
            status = lines[index][0]
            name = lines[index][2:]
            if status in self.modification_statuses:
                if (index + 1) < numlines and lines[index + 1][0] == ' ':
                    index += 1
                    extra_info = lines[index][2:]
                else:
                    extra_info = None
                modified.append((name, status, extra_info))
            elif status in self.ignored_statuses:
                ignored.append((name, status, None))
            else:
                others.append((name, status, None))
            index += 1
        return (res, (ignored, others, modified), serr)
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
    def get_change_set_summary(self, rev, rootdir=None):
        cstr = 'log --template "%s" --rev %s' % (self.cs_summary_template, rev)
        cmd = _hg_cmd_str(cstr, rootdir)
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        return self._process_change_set_summary(res, sout, serr)
    def get_change_set_files(self, rev, rootdir=None):
        res, parents, serr = self.get_parents(rev, rootdir=rootdir)
        template = '{files}\\n{file_adds}\\n{file_dels}\\n'
        cstr = 'log --template "%s" --rev %s' % (template, rev)
        cmd = _hg_cmd_str(cstr, rootdir)
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        lines = sout.splitlines()
        file_names = utils.string_to_file_list(lines[0])
        added_files = utils.string_to_file_list(lines[1])
        deleted_files = utils.string_to_file_list(lines[2])
        files = []
        for name in file_names:
            if name in added_files:
                extra_info = None
                for parent in parents:
                    cstr = 'status -aC --rev %s --rev %s "%s"' % (parent, rev, name)
                    cmd = _hg_cmd_str(cstr, rootdir)
                    res, sout, serr = utils.run_cmd(cmd)
                    lines = sout.splitlines()
                    if len(lines) > 1 and lines[1][0] == ' ':
                        extra_info = lines[1].strip()
                        break
                files.append((name, 'A', extra_info))
            elif name in deleted_files:
                files.append((name, 'R', None))
            else:
                files.append((name, 'M', None))
        return (cmd_result.OK, files, '')
    def get_parents_data(self, rev=None, rootdir=None):
        cmd = _hg_cmd_str('parents --template "%s"' % self.cs_table_template, rootdir)
        if rev is None:
            qbase = self._get_qbase(rootdir=rootdir)
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
    def get_path_table_data(self, rootdir=None):
        path_re = re.compile('^(\S*)\s+=\s+(\S*)\s*$')
        cmd = _hg_cmd_str('paths', rootdir)
        res, sout, serr = utils.run_cmd(cmd)
        paths = []
        for line in sout.splitlines():
            match = path_re.match(line)
            if match:
                paths.append([match.group(1), match.group(2)])
        return (res, paths, serr)
    def get_outgoing_table_data(self, path=None, rootdir=None):
        cstr = 'outgoing --template "%s"' % self.cs_table_template
        cmd = _hg_cmd_str(cstr, rootdir, '-q')
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
    def get_outgoing_rev(self, revarg, rootdir=None):
        cmd = _hg_cmd_str('outgoing -n -l 1 --template "{rev}" --rev %s' % revarg, rootdir, ' -q')
        return utils.run_cmd(cmd)
    def get_incoming_table_data(self, path=None, rootdir=None):
        cstr = 'incoming --template "%s"' % self.cs_table_template
        cmd = _hg_cmd_str(cstr, rootdir, '-q')
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
    def get_incoming_rev(self, revarg, rootdir=None):
        cmd = _hg_cmd_str('incoming -n -l 1 --template "{rev}" --rev %s' % revarg, rootdir, ' -q')
        return utils.run_cmd(cmd)
    def get_is_incoming(self, rev, path=None, rootdir=None):
        cstr = 'incoming -qnl1 --template "{rev}" --rev %s' % str(rev)
        cmd = _hg_cmd_str(cstr, rootdir)
        if path:
            cmd += ' "%s"' % path
        res, sout, serr = utils.run_cmd(cmd)
        return sout == str(rev)
    def get_incoming_change_set_summary(self, rev, path=None, rootdir=None):
        cstr = 'incoming --template "%s" -nl 1 --rev %s' % (self.cs_summary_template, rev)
        cmd = _hg_cmd_str(cstr, rootdir, '-q')
        if path:
            cmd += ' "%s"' % path
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        return self._process_change_set_summary(res, sout, serr)
    def get_incoming_change_set_files(self, rev, path=None, rootdir=None):
        template = '{files}\\n{file_adds}\\n{file_dels}\\n'
        cstr = 'incoming --template "%s" -nl 1 --rev %s' % (template, rev)
        cmd = _hg_cmd_str(cstr, rootdir, '-q')
        if path:
            cmd += ' "%s"' % path
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        lines = sout.splitlines()
        file_names = utils.string_to_file_list(lines[0])
        added_files = utils.string_to_file_list(lines[1])
        deleted_files = utils.string_to_file_list(lines[2])
        files = []
        for name in file_names:
            if name in added_files:
                files.append((name, 'A', None))
            elif name in deleted_files:
                files.append((name, 'R', None))
            else:
                files.append((name, 'M', None))
        return (cmd_result.OK, files, "")
    def get_incoming_parents(self, rev, path=None, rootdir=None):
        cstr = 'incoming --template "{parents}" -nl 1 --rev %s' % rev
        cmd = _hg_cmd_str(cstr, rootdir, '-q')
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
    def get_incoming_parents_table_data(self, rev, path=None, rootdir=None):
        res, parents, serr = self.get_incoming_parents(rev, path, rootdir=rootdir)
        if res != 0:
            return (res, parents, serr)
        plist = []
        cstr = 'incoming --template "%s" -nl 1' % self.cs_table_template
        base_cmd = _hg_cmd_str(cstr, rootdir, '-q')
        for parent in parents:
            if not self.get_is_incoming(parent, path, rootdir=rootdir):
                # the parent is local
                res, sublist, serr = self.get_history_data(rev=parent, rootdir=rootdir)
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
    def get_incoming_diff(self, rev, path=None, rootdir=None):
        cstr = 'incoming --patch -nl 1 --rev %s' % rev
        cmd = _hg_cmd_str(cstr, rootdir)
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
    def get_heads_data(self, rootdir=None):
        if not self.get_root(rootdir=rootdir): return (cmd_result.OK, [], '')
        cstr = 'heads --template "%s"' % self.cs_table_template
        cmd = _hg_cmd_str(cstr, rootdir)
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(':', 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_history_data(self, rev=None, maxitems=None, rootdir=None):
        if not self.get_root(rootdir=rootdir): return (cmd_result.OK, [], '')
        cstr = 'log --template "%s"' % self.cs_table_template
        cmd = _hg_cmd_str(cstr, rootdir)
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
    def get_rev(self, revarg, rootdir=None):
        cmd = _hg_cmd_str('log --template "{rev}" --rev %s' % revarg, rootdir)
        return utils.run_cmd(cmd)
    def get_tags_data(self, rootdir=None):
        if not self.get_root(rootdir=rootdir): return (cmd_result.OK, [], '')
        cmd = _hg_cmd_str('tags', rootdir, '-v')
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        de = re.compile('^(\S+)\s*(\d+):(\S+)\s*(\S*)')
        tag_list = []
        template = '{rev}:{branches}:{date|age}:{author|person}:{desc|firstline}\\n'
        cmd = _hg_cmd_str('log --template "%s"' % template, rootdir)
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
    def get_tags_list_for_table(self, rootdir=None):
        cmd = _hg_cmd_str('tags', rootdir)
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
    def get_branches_data(self, rootdir=None):
        if not self.get_root(rootdir=rootdir): return (cmd_result.OK, [], '')
        cmd = _hg_cmd_str('branches', rootdir)
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        de = re.compile('^(\S+)\s*(\d+):')
        branch_list = []
        for line in sout.splitlines():
            dat = de.match(line)
            branch_list.append([dat.group(1), int(dat.group(2))])
        cstr = 'log --template "{tags}:{date|age}:{author|person}:{desc|firstline}" --rev '
        cmd = _hg_cmd_str(cstr, rootdir)
        for branch in branch_list:
            res, sout, serr = utils.run_cmd(cmd + str(branch[1]))
            branch += sout.split(':', 3)
        return (res, branch_list, serr)
    def get_branches_list_for_table(self, rootdir=None):
        cmd = _hg_cmd_str('branches', rootdir)
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
    def do_commit_change(self, msg, file_list=[], rootdir=None):
        cmd = _hg_cmd_str('commit', rootdir, '-v')
        if msg:
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        if file_list:
            cmd += self._file_list_to_I_string(file_list)
        res, sout, serr = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD|ws_event.CHECKOUT, file_list)
        return (res, sout, serr)
    def do_remove_files(self, file_list, force=False, rootdir=None):
        if force:
            cmd = _hg_cmd_str('remove -f', rootdir)
        else:
            cmd = _hg_cmd_str('remove', rootdir)
        result = self._run_cmd_on_console(cmd + utils.file_list_to_string(file_list))
        ws_event.notify_events(ws_event.FILE_DEL)
        return result
    def get_diff_for_files(self, file_list, fromrev, torev=None, rootdir=None):
        # because of the likelihood of a multiple parents we'll never use the
        # zero rev option so fromrev is compulsory (except when there are no
        # revisions yet e.g. in a brand new repository)
        cmd = _hg_cmd_str('diff', rootdir)
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
    def do_update_workspace(self, rev=None, discard=False, rootdir=None):
        cmd = _hg_cmd_str('update', rootdir)
        if discard:
            cmd += ' -C'
        if rev is not None:
            cmd += ' -r %s' %rev
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.CHECKOUT)
        return result
    def do_merge_workspace(self, rev=None, force=False, rootdir=None):
        cmd = _hg_cmd_str('merge', rootdir)
        if force:
            cmd += ' -f'
        if rev is not None:
            cmd += ' -r %s' %rev
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.CHECKOUT)
        return result
    def do_push_to(self, rev=None, force=False, path=None, rootdir=None):
        cmd = cmd = _hg_cmd_str('push', rootdir)
        if force:
            cmd += ' -f'
        if rev is not None:
            cmd += ' -r %s' %rev
        if path:
            cmd += ' "%s"' % path
        return self._run_cmd_on_console(cmd)
    def do_verify_repo(self, rootdir=None):
        return self._run_cmd_on_console(_hg_cmd_str('verify', rootdir))
    def do_rollback_repo(self, rootdir=None):
        result = self._run_cmd_on_console(_hg_cmd_str('rollback', rootdir))
        ws_event.notify_events(ws_event.REPO_MOD|ws_event.CHECKOUT)
        return result
    def do_set_tag(self, tag, rev=None, local=False, force=False, msg=None, rootdir=None):
        if not tag:
            return (cmd_result.OK, "", "")
        cmd = _hg_cmd_str('tag', rootdir)
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
    def do_remove_tag(self, tag, local=False, msg=None, rootdir=None):
        cmd = _hg_cmd_str('tag --remove', rootdir)
        if local:
            cmd += ' -l'
        if msg:
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        cmd += ' %s' % tag
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result[0]):
            ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_move_tag(self, tag, rev, msg=None, rootdir=None):
        cmd = _hg_cmd_str('tag -f -r %s' % rev, rootdir)
        if msg:
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        cmd += " %s" % tag
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result[0]):
            ws_event.notify_events(ws_event.REPO_MOD)
        return result        
    def do_set_branch(self, branch, force=False, rootdir=None):
        cmd = _hg_cmd_str('branch', rootdir)
        if force:
            cmd += ' -f'
        cmd += ' %s' % branch
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_clone_as(self, path, target=None, rootdir=None):
        cmd = _hg_cmd_str('clone "%s"' % path, rootdir)
        if target:
            cmd += ' "%s"' % target
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_backout(self, rev, msg, merge=False, parent=None, rootdir=None):
        cmd = _hg_cmd_str('backout', rootdir)
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
    def get_pbranch_table_data(self, rootdir=None):
        if not self.get_root(rootdir=rootdir): return (cmd_result.OK, [], '')
        cmd = _hg_cmd_str('pgraph --title --with-name', rootdir)
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        de = re.compile('^([^]]*)\[(\S+)\]\s*(.*)')
        branch_list = []
        for line in sout.splitlines():
            dat = de.match(line)
            if dat:
                branch_list.append([dat.group(2), dat.group(3), dat.group(1).find('@') >= 0])
        cmd = _hg_cmd_str('pstatus %s', rootdir)
        for branch in branch_list:
            res, sout, serr = utils.run_cmd(cmd % branch[0])
            branch.append(sout.strip() == '')
        return (res, branch_list, serr)
    def get_pbranch_description(self, pbranch, rootdir=None):
        if pbranch:
            cmd = _hg_cmd_str('pmessage %s' % pbranch, rootdir)
        else:
            cmd = _hg_cmd_str('pmessage', rootdir)
        res, sout, serr = utils.run_cmd(cmd)
        descr_lines = sout.splitlines()[1:]
        return (res, '\n'.join(descr_lines), serr)
    def get_pdiff_for_files(self, file_list=[], pbranch=None, rootdir=None):
        cmd = _hg_cmd_str('pdiff', rootdir)
        if pbranch:
            cmd += ' %s' % pbranch
        if file_list:
            cmd += ' %s' % utils.file_list_to_string(file_list)
        return utils.run_cmd(cmd)
    def get_pstatus(self, pbranch=None, rootdir=None):
        cmd = _hg_cmd_str('pstatus', rootdir)
        if pbranch:
            cmd += ' %s' % pbranch
        return utils.run_cmd(cmd)
    def get_pgraph(self, rootdir=None):
        cmd = _hg_cmd_str('pgraph --title --with-name', rootdir)
        return utils.run_cmd(cmd)
    def do_set_pbranch_description(self, pbranch, descr, rootdir=None):
        cstr = 'peditmessage -t "%s"' % descr.replace('"', '\\"')
        cmd = _hg_cmd_str(cstr, rootdir)
        if pbranch:
            cmd += ' %s' % pbranch
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_new_pbranch(self, name, msg, preserve=False, rootdir=None):
        cmd = _hg_cmd_str('pnew', rootdir)
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
    def do_pmerge(self, pbranches=[], rootdir=None):
        cmd = _hg_cmd_str('pmerge', rootdir)
        if pbranches:
            cmd += ' %s' % ' '.join(pbranches)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD|ws_event.CHECKOUT|ws_event.FILE_CHANGES)
        return result
    def do_pbackout(self, files=[], rootdir=None):
        cmd = _hg_cmd_str('pbackout', rootdir)
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
    def start(self, serr, state, rootdir=None):
        match = self._get_copy_re.match(serr)
        if rootdir:
            copy_file = os.path.join(rootdir, self._copy_file)
        else:
            copy_file = self._copy_file
        if match:
            self._write_to_named_file(copy_file, os.path.basename(match.group(1)))
        self.set_state(state)
    def is_in_progress(self, rootdir=None):
        if rootdir:
            state_file = os.path.join(rootdir, self._state_file)
        else:
            state_file = self._state_file
        return os.path.exists(state_file)
    def tip_is_patches_saved_state(self, rootdir=None):
        cstr = 'log --template "{desc|firstline}" --rev tip'
        cmd = _hg_cmd_str(cstr, rootdir)
        res, sout, serr = utils.run_cmd(cmd)
        return sout == self._saved_state_msg
    def parent_is_patches_saved_state(self, rootdir=None):
        cstr = 'parent --template "{desc|firstline}"'
        cmd = _hg_cmd_str(cstr, rootdir)
        res, sout, serr = utils.run_cmd(cmd)
        return sout == self._saved_state_msg
    def set_state(self, state, rootdir=None):
        if rootdir:
            state_file = os.path.join(rootdir, self._state_file)
        else:
            state_file = self._state_file
        self._write_to_named_file(state_file, state)
    def get_state_is_in(self, state_list, rootdir=None):
        if rootdir:
            state_file = os.path.join(rootdir, self._state_file)
        else:
            state_file = self._state_file
        if not os.path.exists(state_file):
            return False
        state = self._read_from_named_file(state_file)
        return state in state_list
    def get_patches_copy_dir(self, rootdir=None):
        if rootdir:
            copy_file = os.path.join(rootdir, self._copy_file)
        else:
            copy_file = self._copy_file
        return self._read_from_named_file(copy_file)
    def finish(self, rootdir=None):
        if rootdir:
            copy_file = os.path.join(rootdir, self._copy_file)
            state_file = os.path.join(rootdir, self._state_file)
        else:
            copy_file = self._copy_file
            state_file = self._state_file
        for path in copy_file, state_file:
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
    def get_parent(self, patch, rootdir=None):
        parent = 'qparent'
        for applied_patch in self.get_applied_patches(rootdir=rootdir):
            if patch == applied_patch:
                return parent
            else:
                parent = applied_patch
        return None
    def get_file_status_list(self, patch=None, rootdir=None):
        if not self.get_enabled():
            return (cmd_result.OK, [], "")
        if patch and not self.get_patch_is_applied(patch, rootdir=rootdir):
            pfn = self.get_patch_file_name(patch, rootdir=rootdir)
            result, file_list = putils.get_patch_files(pfn, status=True)
            if result:
                return (cmd_result.OK, file_list, "")
            else:
                return (cmd_result.WARNING, "", file_list)
        top = self.get_top_patch(rootdir=rootdir)
        if not top:
            # either we're not in an mq playground or no patches are applied
            return (cmd_result.OK, [], "")
        cmd = _hg_cmd_str('status -mardC', rootdir)
        if patch:
            parent = self.get_parent(patch)
            cmd += ' --rev %s --rev %s' % (parent, patch)
        else:
            parent = self.get_parent(top, rootdir=rootdir)
            cmd += ' --rev %s' % parent
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, [], sout + serr)
        file_list = []
        lines = sout.splitlines()
        numlines = len(lines)
        index = 0
        while index < numlines:
            status = lines[index][0]
            name = lines[index][2:]
            if (index + 1) < numlines and lines[index + 1][0] == ' ':
                index += 1
                extra_info = lines[index][2:]
            else:
                extra_info = None
            file_list.append((name, status, extra_info))
            index += 1
        return (res, file_list, serr)
    def get_in_progress(self, rootdir=None):
        if not self.get_enabled():
            return False
        return (self.get_top_patch(rootdir=rootdir) is not None) or \
            self._ws_update_mgr.is_in_progress(rootdir=rootdir)
    def get_applied_patches(self, rootdir=None):
        if not self.get_enabled():
            return []
        res, op, err = utils.run_cmd(_hg_cmd_str('qapplied', rootdir))
        if res != 0:
                return []
        return op.splitlines()
    def get_unapplied_patches(self, rootdir=None):
        if not self.get_enabled():
            return []
        res, op, err = utils.run_cmd(_hg_cmd_str('qunapplied', rootdir))
        if res != 0:
                return []
        return op.splitlines()
    def get_patch_is_applied(self, patch, rootdir=None):
        return patch in self.get_applied_patches(rootdir=rootdir)
    def get_top_patch(self, rootdir=None):
        res, sout, serr = utils.run_cmd(_hg_cmd_str('qtop', rootdir))
        if res:
            return None
        else:
            return sout.strip()
    def get_base_patch(self, rootdir=None):
        res, sout, serr = utils.run_cmd(_hg_cmd_str('qapplied', rootdir))
        if res or not sout:
            return None
        else:
            return sout.splitlines()[0]
    def get_next_patch(self, rootdir=None):
        res, sout, serr = utils.run_cmd(_hg_cmd_str('qnext', rootdir))
        if res or not sout:
            return None
        else:
            return sout.strip()
    def get_diff_for_files(self, file_list=[], patch=None, rootdir=None):
        if patch:
            parent = self.get_parent(patch)
            if not parent:
                # the patch is not applied
                pfn = self.get_patch_file_name(patch, rootdir=rootdir)
                result, diff = putils.get_patch_diff(pfn, file_list)
                if result:
                    return (cmd_result.OK, diff, '')
                else:
                    return (cmd_result.WARNING, '', diff)
        else:
            top = self.get_top_patch(rootdir=rootdir)
            if top:
                parent = self.get_parent(top, rootdir=rootdir)
            else:
                return (cmd_result.OK, '', '')
        cmd = _hg_cmd_str('diff --rev %s' % parent, rootdir)
        if patch:
            cmd += ' --rev %s' % patch
        if file_list:
            cmd += utils.file_list_to_string(file_list)
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            res = cmd_result.ERROR
        return (res, sout, serr)
    def do_refresh(self, rootdir=None):
        result = self._run_cmd_on_console(_hg_cmd_str('qrefresh', rootdir))
        if not result[0]:
            ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.REPO_MOD)
        return result
    def do_pop_to(self, patch=None, force=False, rootdir=None):
        if patch is None:
            if force:
                cmd = _hg_cmd_str('qpop -f', rootdir)
            else:
                cmd = _hg_cmd_str('qpop', rootdir)
        elif patch is '':
            if force:
                cmd = _hg_cmd_str('qpop -f -a', rootdir)
            else:
                cmd = _hg_cmd_str('qpop -a', rootdir)
        else:
            if force:
                cmd = _hg_cmd_str('qpop -f %s' % patch, rootdir)
            else:
                cmd = _hg_cmd_str('qpop %s' % patch, rootdir)
        result = self._run_cmd_on_console(cmd)
        if not self.get_in_progress():
            ws_event.notify_events(ws_event.PMIC_CHANGE, False)
        events = ws_event.CHECKOUT|ws_event.REPO_MOD|ws_event.FILE_CHANGES
        ws_event.notify_events(events)
        return result
    def do_push_to(self, patch=None, force=False, merge=False, rootdir=None):
        in_charge = self.get_in_progress(rootdir=rootdir)
        if merge:
            cmd = _hg_cmd_str('-y qpush -m', rootdir)
        else:
            cmd = _hg_cmd_str('qpush', rootdir)
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
            self._ws_update_mgr.set_state('merged', rootdir=rootdir)
        return result
    def get_patch_file_name(self, patch, rootdir=None):
        if rootdir:
            return os.path.join(os.path.abspath(rootdir), '.hg', 'patches', patch)
        else:
            return os.path.join(os.getcwd(), '.hg', 'patches', patch)
    def get_patch_description(self, patch, rootdir=None):
        pfn = self.get_patch_file_name(patch, rootdir=rootdir)
        res, descr_lines = putils.get_patch_descr_lines(pfn)
        descr = '\n'.join(descr_lines) + '\n'
        if res:
            return (cmd_result.OK, descr, "")
        else:
            return (cmd_result.ERROR, descr, "Error reading description to \"%s\" patch file" % patch)
    def do_set_patch_description(self, patch, descr, rootdir=None):
        pfn = self.get_patch_file_name(patch, rootdir=rootdir)
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
    def get_description_is_finish_ready(self, patch, rootdir=None):
        pfn = self.get_patch_file_name(patch, rootdir=rootdir)
        res, pf_descr_lines = putils.get_patch_descr_lines(pfn)
        pf_descr = '\n'.join(pf_descr_lines).strip()
        if not pf_descr:
            return False
        cmd = _hg_cmd_str('log --template "{desc}" --rev %s' % patch, rootdir)
        res, rep_descr, sout = utils.run_cmd(cmd)
        if pf_descr != rep_descr.strip():
            top = self.get_top_patch()
            if top == patch:
                utils.run_cmd(_hg_cmd_str('qrefresh', rootdir))
            else:
                # let's hope the user doesn't mind having the top patch refreshed
                utils.run_cmd(_hg_cmd_str('qrefresh', rootdir))
                utils.run_cmd(_hg_cmd_str('qgoto %s' % patch, rootdir))
                utils.run_cmd(_hg_cmd_str('qrefresh', rootdir))
                utils.run_cmd(_hg_cmd_str('qgoto %s' % top, rootdir))
        return True
    def do_finish_patch(self, patch, rootdir=None):
        result = self._run_cmd_on_console(_hg_cmd_str('qfinish %s' % patch, rootdir))
        if not self.get_in_progress(rootdir=rootdir):
            ws_event.notify_events(ws_event.PMIC_CHANGE, False)
        events = ws_event.CHECKOUT|ws_event.REPO_MOD|ws_event.FILE_CHANGES
        ws_event.notify_events(events)
        return result
    def do_rename_patch(self, old_name, new_name, rootdir=None):
        cmd = _hg_cmd_str('qrename %s %s' % (old_name, new_name), rootdir)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.REPO_MOD)
        return result
    def do_delete_patch(self, patch, rootdir=None):
        result = self._run_cmd_on_console(_hg_cmd_str('qdelete %s' % patch, rootdir))
        ws_event.notify_events(ws_event.UNAPPLIED_PATCH_MOD)
        return result
    def do_fold_patch(self, patch, rootdir=None):
        result = self._run_cmd_on_console(_hg_cmd_str('qfold %s' % patch, rootdir))
        ws_event.notify_events(ws_event.FILES_CHANGE)
        return result
    def do_import_patch(self, patch_file_name, as_patch_name=None, force=False, rootdir=None):
        cmd = _hg_cmd_str('qimport', rootdir)
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
    def do_new_patch(self, patch_name_raw, force=False, rootdir=None):
        in_charge = self.get_in_progress(rootdir=rootdir)
        patch_name = re.sub('\s', '_', patch_name_raw)
        if force:
            cmd = _hg_cmd_str('qnew -f %s' % patch_name, rootdir)
        else:
            cmd = _hg_cmd_str('qnew %s' % patch_name, rootdir)
        res, sout, serr = self._run_cmd_on_console(cmd)
        if not in_charge:
            ws_event.notify_events(ws_event.PMIC_CHANGE, True)
        events = ws_event.CHECKOUT|ws_event.REPO_MOD
        ws_event.notify_events(events)
        if res & cmd_result.SUGGEST_REFRESH:
            res |= cmd_result.SUGGEST_FORCE
        return (res, sout, serr)
    def do_remove_files(self, file_list, force=False, rootdir=None):
        applied_count = len(self.get_applied_patches(rootdir=rootdir))
        if not file_list or applied_count == 0:
            return (cmd_result.OK, '', '')
        elif applied_count == 1:
            parent = 'qparent'
        else:
            res, sout, serr = utils.run_cmd(_hg_cmd_str('qprev', rootdir))
            parent = sout.strip()
        cmd = _hg_cmd_str('revert --rev %s' % parent, rootdir)
        if force:
            cmd += ' -f'
        cmd += utils.file_list_to_string(file_list)
        result = self._run_cmd_on_console(cmd)
        ws_event.notify_events(ws_event.FILE_DEL)
        return result
    def do_save_queue_state_for_update(self, rootdir=None):
        cmd = _hg_cmd_str('qsave -e -c', rootdir)
        result = self._run_cmd_on_console(cmd)
        self._ws_update_mgr.start(result[2], 'qsaved', rootdir=rootdir)
        ws_event.notify_events(ws_event.CHECKOUT|ws_event.FILE_CHANGES|ws_event.REPO_MOD)
        return result
    def do_pull_from(self, rev=None, source=None, rootdir=None):
        result = BaseInterface.do_pull_from(self, rev=rev, source=source, rootdir=rootdir)
        if cmd_result.is_less_than_error(result[0]):
            self._ws_update_mgr.set_state('pulled', rootdir=rootdir)
        return result
    def do_update_workspace(self, rev=None, rootdir=None):
        cmd = _hg_cmd_str('update -C', rootdir)
        if rev is not None:
            cmd += ' -r %s' %rev
        result = self._run_cmd_on_console(cmd)
        if not result[0]:
            ws_event.notify_events(ws_event.CHECKOUT)
            self._ws_update_mgr.set_state('updated')
        return result
    def do_clean_up_after_update(self, rootdir=None):
        pcd = self._ws_update_mgr.get_patches_copy_dir(rootdir=rootdir)
        if pcd:
            top_patch = self.get_top_patch(rootdir=rootdir)
            if top_patch:
                utils.run_cmd(_hg_cmd_str('qpop -a', rootdir))
            self._ws_update_mgr.finish()
            result = self._run_cmd_on_console(_hg_cmd_str('qpop -a -n %s' % pcd, rootdir))
            if top_patch:
                utils.run_cmd(_hg_cmd_str('qgoto %s' % top_patch, rootdir))
                ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.REPO_MOD)
            else:
                ws_event.notify_events(ws_event.FILE_CHANGES|ws_event.REPO_MOD)
                ws_event.notify_events(ws_event.PMIC_CHANGE, False)
            return result
        else:
            return (cmd_result.INFO, 'Saved patch directory not found.', '')
    def get_ws_update_qsave_ready(self, unapplied_count=None, applied_count=None, rootdir=None):
        if unapplied_count is None:
            unapplied_count = len(self.get_unapplied_patches())
        if applied_count is None:
            applied_count = len(self.get_applied_patches())
        return applied_count and not unapplied_count and not self._ws_update_mgr.is_in_progress()
    def get_ws_update_ready(self, applied_count=None, rootdir=None):
        if applied_count is None:
            applied_count = len(self.get_applied_patches(rootdir=rootdir))
        if self._ws_update_mgr.tip_is_patches_saved_state(rootdir=rootdir):
            return False
        return not applied_count and self._ws_update_mgr.get_state_is_in(["pulled"])
    def get_ws_update_merge_ready(self, unapplied_count=None, rootdir=None):
        if unapplied_count is None:
            unapplied_count = len(self.get_unapplied_patches(rootdir=rootdir))
        if self._ws_update_mgr.parent_is_patches_saved_state(rootdir=rootdir):
            return False
        return unapplied_count and self._ws_update_mgr.get_state_is_in(["updated"], rootdir=rootdir)
    def get_ws_update_clean_up_ready(self, applied_count=None, rootdir=None):
        return self._ws_update_mgr.get_state_is_in(["merged"], rootdir=rootdir)
    def get_ws_update_pull_ready(self, applied_count=None, rootdir=None):
        if applied_count is None:
            applied_count = len(self.get_applied_patches(rootdir=rootdir))
        return not applied_count and self._ws_update_mgr.get_state_is_in(["qsaved"], rootdir=rootdir)
    def get_ws_update_to_ready(self, applied_count=None, rootdir=None):
        if applied_count is None:
            applied_count = len(self.get_applied_patches(rootdir=rootdir))
        return not applied_count and self._ws_update_mgr.get_state_is_in(["qsaved", "pulled"], rootdir=rootdir)
