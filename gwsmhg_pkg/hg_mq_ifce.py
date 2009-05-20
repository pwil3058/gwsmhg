### Copyright (C) 2007 Peter Williams <pwil3058@bigpond.net.au>

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

import os, os.path, tempfile, pango, re, tempfile
from gwsmhg_pkg import text_edit, utils, cmd_result, console, putils

DEFAULT_NAME_EVARS = ["GIT_AUTHOR_NAME", "GECOS"]
DEFAULT_EMAIL_VARS = ["GIT_AUTHOR_EMAIL", "EMAIL_ADDRESS"]

class BaseInterface(utils.action_notifier):
    def __init__(self, name, console_log):
        utils.action_notifier.__init__(self)
        self._console_log = console_log
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
    def get_author_name_and_email(self):
        res, uiusername, serr = utils.run_cmd("hg showconfig ui.username")
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
    def _map_result(self, result, stdout_expected=False):
        outres, sout, serr = cmd_result.map_cmd_result(result, stdout_expected)
        if outres != cmd_result.OK:
            for force_suggested in ["use -f to force", "not overwriting - file exists"]:
                if serr.find(force_suggested) != -1 or sout.find(force_suggested) != -1:
                    outres += cmd_result.SUGGEST_FORCE
        return (outres, sout, serr)
    def do_add_files(self, file_list, dry_run=False):
        cmd = "hg add"
        if dry_run:
            cmd += " -n --verbose"
        if file_list:
            cmd = " ".join([cmd] + file_list)
        if dry_run:
            return self._map_result(utils.run_cmd(cmd), stdout_expected=True)
        else:
            result = self._run_cmd_on_console(cmd)
            self._do_cmd_notification("add")
            return result
    def do_copy_files(self, file_list, target, force=False, dry_run=False):
        cmd = "hg copy "
        if dry_run:
            cmd += "-n --verbose "
        if force:
            cmd += "-f "
        cmd = " ".join([cmd] + file_list + [target])
        if dry_run:
            return self._map_result(utils.run_cmd(cmd), stdout_expected=True)
        else:
            result = self._run_cmd_on_console(cmd)
            self._do_cmd_notification("copy")
            return result
    def do_move_files(self, file_list, target, force=False, dry_run=False):
        cmd = "hg rename "
        if dry_run:
            cmd += "-n --verbose "
        if force:
            cmd += "-f "
        cmd = " ".join([cmd] + file_list + [target])
        if dry_run:
            return self._map_result(utils.run_cmd(cmd), stdout_expected=True)
        else:
            result = self._run_cmd_on_console(cmd)
            self._do_cmd_notification("rename")
            return result
    def do_revert_files(self, file_list, dry_run=False):
        cmd = "hg revert "
        if dry_run:
            cmd += "-n --verbose "
        if file_list:
            cmd += " ".join(file_list)
        else:
            cmd += "--all"
        if dry_run:
            return self._map_result(utils.run_cmd(cmd), stdout_expected=True)
        else:
            result = self._run_cmd_on_console(cmd, stdout_expected=True)
            self._do_cmd_notification("revert")
            return result
    def do_delete_files(self, file_list):
        if self._console_log:
            self._console_log.start_cmd("Deleting: %s" % " ".join(file_list))
        serr = ""
        for filename in file_list:
            try:
                os.remove(filename)
                if self._console_log:
                    self._console_log.append_stdout(("Deleted: %s" + os.linesep) % filename)
            except os.error, value:
                errmsg = ("%s: %s" + os.linesep) % (value[1], filename)
                serr += errmsg
                if self._console_log:
                    self._console_log.append_stderr(errmsg)
        if self._console_log:
            self._console_log.end_cmd()
        self._do_cmd_notification("delete")
        if serr:
            return (cmd_result.ERROR, "", serr)
        return (cmd_result.OK, "", "")
    def do_pull_from(self, rev=None, update=False, source=None):
        cmd = "hg pull"
        if update:
            cmd += " -u"
        if rev:
            cmd += " -r %s" % rev
        if source:
            cmd += " %s" % source
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result[0]):
            self._do_cmd_notification("pull")
        return result

class SCMInterface(BaseInterface):
    def __init__(self, console_log):
        BaseInterface.__init__(self, "hg", console_log)
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
        self.cs_summary_template = os.linesep.join(self.cs_summary_template_lines)
        self.cs_table_template = '{rev}:{date|age}:{tags}:{branches}:{author|person}:{desc|firstline}' + os.linesep
    def _map_cmd_result(self, result, stdout_expected=True, ignore_err_re=None):
        if not result[0]:
            return cmd_result.map_cmd_result(result, stdout_expected=stdout_expected, ignore_err_re=ignore_err_re)
        else:
            flags = cmd_result.ERROR
            if result[2].find('use -f to force') is not -1:
                flags |= cmd_result.SUGGEST_FORCE
            if result[2].find('already exists') is not -1:
                flags |= cmd_result.SUGGEST_RENAME
            return (flags, result[1], result[2])
    def _run_cmd_on_console(self, cmd, stdout_expected=True):
        result = utils.run_cmd_in_console(cmd, self._console_log)
        return self._map_cmd_result(result, stdout_expected)
    def get_default_commit_save_file(self):
        return os.path.join(".hg", "gwsmhg.saved.commit")
    def _get_first_in_envar(self, envar_list):
        for envar in envar_list:
            try:
                value = os.environ[envar]
                if value is not "":
                    return value
            except KeyError:
                continue
        return ""
    def get_root(self, dir=None):
        if dir:
            old_dir = os.getcwd()
            os.chdir(dir)
        res, root, serr = utils.run_cmd("hg root")
        if dir:
            os.chdir(old_dir)
        if res != 0:
            return None
        return root.strip()
    def is_repository(self, dir=None):
        return self.get_root(dir) != None
    def _get_qbase(self):
        res, rev, serr = utils.run_cmd('hg log --template "{rev}" -r qbase')
        if not res:
            return rev
        return None
    def get_parents(self, rev=None):
        cmd = os.linesep.join(['hg parents --template "{rev}', '"'])
        if not rev:
            qbase = self._get_qbase()
            if qbase:
                rev = qbase
        if rev:
            cmd += " -r %s" % rev
        res, sout, serr = utils.run_cmd(cmd)
        if res or not sout:
            revs = [sout]
        else:
            revs = []
            for line in sout.splitlines(False):
                revs.append(line)
        return (res, revs, serr)
    def _get_qbase_parents(self):
        res, parents, serr = self.get_parents("qbase")
        if res:
            # probably should pop up a problem report
            return []
        else:
            return parents
    def get_file_status_lists(self, fspath_list=[], *revs):
        cmd = "hg status -marduiC"
        if not revs:
            revs = self._get_qbase_parents()
        if revs:
            for rev in revs:
                cmd += " --rev %s" % rev
        if fspath_list:
            cmd += " %s" % " ".join(fspath_list)
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
                if (index + 1) < numlines and lines[index + 1][0] == " ":
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
        lines = sout.splitlines(False)
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
        summary['DESCR'] = os.linesep.join(lines[self._css_line_index('{desc}'):])
        return (res, summary, serr)
    def get_change_set_summary(self, rev):
        res, sout, serr = utils.run_cmd('hg log --template "%s" --rev %s' % (self.cs_summary_template, rev))
        if res:
            return (res, sout, serr)
        return self._process_change_set_summary(res, sout, serr)
    def get_change_set_files(self, rev):
        res, parents, serr = self.get_parents(rev)
        template = os.linesep.join(['{files}', '{file_adds}', '{file_dels}', ''])
        res, sout, serr = utils.run_cmd('hg log --template "%s" --rev %s' % (template, rev))
        if res:
            return (res, sout, serr)
        lines = sout.splitlines(False)
        file_names = lines[0].split()
        added_files = lines[1].split()
        deleted_files = lines[2].split()
        files = []
        for name in file_names:
            if name in added_files:
                extra_info = None
                for parent in parents:
                    cmd = "hg status -aC --rev %s --rev %s %s" % (parent, rev, name)
                    res, sout, serr = utils.run_cmd(cmd)
                    lines = sout.splitlines(False)
                    if len(lines) > 1 and lines[1][0] == " ":
                        extra_info = lines[1].strip()
                        break
                files.append((name, "A", extra_info))
            elif name in deleted_files:
                files.append((name, "R", None))
            else:
                files.append((name, "M", None))
        return (cmd_result.OK, files, "")
    def get_parents_data(self, rev=None):
        cmd = 'hg parents --template "%s"' % self.cs_table_template
        if not rev:
            qbase = self._get_qbase()
            if qbase:
                rev = qbase
        if rev:
            cmd += " --rev %s" % str(rev)
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(":", 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_path_table_data(self):
        path_re = re.compile("^(\S*)\s+=\s+(\S*)\s*$")
        res, sout, serr = utils.run_cmd("hg paths")
        paths = []
        for line in sout.splitlines(False):
            match = path_re.match(line)
            if match:
                paths.append([match.group(1), match.group(2)])
        return (res, paths, serr)
    def get_outgoing_table_data(self, path=None):
        cmd = 'hg -q outgoing --template "%s"' % self.cs_table_template
        if path:
            cmd += " %s" % path
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(":", 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_incoming_table_data(self, path=None):
        cmd = 'hg -q incoming --template "%s"' % self.cs_table_template
        if path:
            cmd += " %s" % path
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(":", 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_incoming_change_set_summary(self, rev, path=None):
        cmd = 'hg -q incoming --template "%s" -nl 1 --rev %s' % (self.cs_summary_template, rev)
        if path:
            cmd += ' %s' % path
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        return self._process_change_set_summary(res, sout, serr)
    def get_incoming_change_set_files(self, rev, path=None):
        template = os.linesep.join(['{files}', '{file_adds}', '{file_dels}', ''])
        cmd = 'hg -q incoming --template "%s" -nl 1 --rev %s' % (template, rev)
        if path:
            cmd += ' %s' % path
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        lines = sout.splitlines(False)
        file_names = lines[0].split()
        added_files = lines[1].split()
        deleted_files = lines[2].split()
        files = []
        if not file_names:
            res, parents, serr = self.get_incoming_parents(rev, path)
            if res or len(parents) < 2:
                return (cmd_result.OK, files, "")
            # 'incoming --template "{files}"' is still broken so try lsdiff
            res, diff, serr = self.get_incoming_diff(rev, path)
            tf, tfn = tempfile.mkstemp()
            os.write(tf, diff)
            os.close(tf)
            ok, file_list = putils.get_patch_files(tfn)
            os.remove(tfn)
            if ok:
                return (cmd_result.OK, file_list, "")
            else:
                return (cmd_result.ERROR, "", file_list)
        for name in file_names:
            if name in added_files:
                files.append((name, "A", None))
            elif name in deleted_files:
                files.append((name, "R", None))
            else:
                files.append((name, "M", None))
        return (cmd_result.OK, files, "")
    def get_incoming_parents(self, rev, path=None):
        cmd = 'hg -q incoming --template "{parents}" -nl 1 --rev %s' % rev
        if path:
            cmd += ' %s' % path
        res, psout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, psout, serr)
        if psout:
            parents = []
            for item in psout.split():
                parents.append(item.split(":"))
        else:
            parents = [str(int(rev) + 1)]
        return (res, parents, serr)
    def get_incoming_parents_table_data(self, rev, path=None):
        res, parents, serr = self.get_incoming_parents(rev, path)
        if res != 0:
            return (res, parents, serr)
        plist = []
        base_cmd = 'hg -q incoming --template "%s" -nl 1' % self.cs_table_template
        for parent in parents:
            if path:
                cmd = base_cmd + " --rev %s %s" % (parent[0], path)
            else:
                cmd = base_cmd + " --rev %s" % parent[0]
            res, sout, serr = utils.run_cmd(cmd)
            if res == 1:
                # the parent is local
                res, sublist, serr = self.get_history_data(rev=parent[1])
                plist += sublist
                continue
            if res != 0:
                return (res, sout, serr)
            pdata = sout.strip().split(":", 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_incoming_diff(self, rev, path=None):
        cmd = 'hg incoming --patch -nl 1 --rev %s' % rev
        if path:
            cmd += ' %s' % path
        res, sout, serr = utils.run_cmd(cmd)
        if res:
            return (res, sout, serr)
        lines = sout.splitlines(False)
        diffstat_si, patch_data = putils.trisect_patch_lines(lines)
        if not patch_data:
            return (res, "", err)
        else:
            patch = os.linesep.join(lines[patch_data[0]:])
            return (res, patch, serr)
    def get_heads_data(self):
        cmd = 'hg heads --template "%s"' % self.cs_table_template
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(":", 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_history_data(self, rev=None):
        cmd = 'hg log --template "%s"' % self.cs_table_template
        if rev:
            cmd += " --rev %s" % rev
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            return (res, sout, serr)
        plist = []
        for line in sout.splitlines():
            pdata = line.split(":", 5)
            pdata[0] = int(pdata[0])
            plist.append(pdata)
        return (res, plist, serr)
    def get_tags_data(self):
        res, sout, serr = utils.run_cmd("hg tags")
        if res:
            return (res, sout, serr)
        de = re.compile("^(\S+)\s*(\d+):")
        tag_list = []
        for line in sout.splitlines(False):
            dat = de.match(line)
            if dat:
                tag_list.append([dat.group(1), int(dat.group(2))])
        cmd = 'hg log --template "{branches}:{date|age}:{author|person}:{desc|firstline}" --rev '
        for tag in tag_list:
            res, sout, serr = utils.run_cmd(cmd + str(tag[1]))
            tag += sout.split(":", 3)
        return (res, tag_list, serr)
    def get_tags_list_for_table(self):
        res, sout, serr = utils.run_cmd("hg tags")
        if res:
            return (res, sout, serr)
        de = re.compile("^(\S+)\s*\d+:")
        tag_list = []
        for line in sout.splitlines(False):
            dat = de.match(line)
            if dat:
                tag_list.append([dat.group(1)])
        return (res, tag_list, serr)
    def get_branches_data(self):
        res, sout, serr = utils.run_cmd("hg branches")
        if res:
            return (res, sout, serr)
        de = re.compile("^(\S+)\s*(\d+):")
        branch_list = []
        for line in sout.splitlines(False):
            dat = de.match(line)
            branch_list.append([dat.group(1), int(dat.group(2))])
        cmd = 'hg log --template "{tags}:{date|age}:{author|person}:{desc|firstline}" --rev '
        for branch in branch_list:
            res, sout, serr = utils.run_cmd(cmd + str(branch[1]))
            branch += sout.split(":", 3)
        return (res, branch_list, serr)
    def get_branches_list_for_table(self):
        res, sout, serr = utils.run_cmd("hg branches")
        if res:
            return (res, sout, serr)
        de = re.compile("^(\S+)\s*\d+:")
        tag_list = []
        for line in sout.splitlines(False):
            dat = de.match(line)
            tag_list.append([dat.group(1)])
        return (res, tag_list, serr)
    def do_init(self, dir=None):
        if dir:
            cmd = "hg init %s" % dir
        else:
            cmd = "hg init"
        result = self._run_cmd_on_console(cmd)
        self._do_cmd_notification("init")
        return result
    def do_commit_change(self, msg, file_list=[]):
        cmd = "hg -v commit"
        if msg:
            # to avoid any possible problems with interaction of characters in the
            # message with the shell we'll stick the message in a temporary file
            msg_fd, msg_file_name = tempfile.mkstemp()
            os.write(msg_fd, msg)
            os.close(msg_fd)
            cmd += " --logfile %s" % msg_file_name
        if file_list:
            cmd += " %s" % " ".join(file_list)
        res, sout, serr = self._run_cmd_on_console(cmd)
        if msg:
            os.remove(msg_file_name)
        self._do_cmd_notification("commit", sout.splitlines(False)[:-1])
        return (res, sout, serr)
    def do_remove_files(self, file_list, force=False):
        if force:
            result = self._run_cmd_on_console("hg remove -f " + " ".join(file_list))
        else:
            result = self._run_cmd_on_console("hg remove " + " ".join(file_list))
        self._do_cmd_notification("remove")
        return result
    def get_diff_for_files(self, file_list, fromrev, torev=None):
        # because of the likelihood of a multiple parents we'll never use the
        # zero rev option so fromrev is compulsory
        cmd = "hg diff --rev %s " % fromrev
        if torev:
            cmd += "--rev %s " % torev
        if file_list:
            cmd += " ".join(file_list)
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            res = cmd_result.ERROR
        return (res, sout, serr)
    def do_update_workspace(self, rev=None, clean=False):
        cmd = "hg update"
        if clean:
            cmd += " -C"
        if rev:
            cmd += " -r %s" %rev
        result = self._run_cmd_on_console(cmd)
        self._do_cmd_notification("update")
        return result
    def do_merge_workspace(self, rev=None, force=False):
        cmd = "hg merge"
        if force:
            cmd += " -f"
        if rev:
            cmd += " -r %s" %rev
        result = self._run_cmd_on_console(cmd)
        self._do_cmd_notification("merge")
        return result
    def do_push_to(self, rev=None, force=False, path=None):
        cmd = "hg push"
        if force:
            cmd += " -f"
        if rev:
            cmd += " -r %s" %rev
        if path:
            cmd += " %s" % path
        return self._run_cmd_on_console(cmd)
    def do_verify_repo(self):
        return self._run_cmd_on_console("hg verify")
    def do_set_tag(self, tag, rev=None, local=False, force=False, msg=None):
        if not tag:
            return (cmd_result.OK, "", "")
        cmd = "hg tag"
        if force:
            cmd += " -f"
        if local:
            cmd += " -l"
        if rev:
            cmd += " -r %s" % rev
        if msg:
            cmd += ' -m "%s"' % msg.replace('"', '\\"')
        cmd += " %s" % tag
        result = self._run_cmd_on_console(cmd)
        if cmd_result.is_less_than_error(result[0]):
            self._do_cmd_notification("tag")
        return result        
    def do_set_branch(self, branch, force=False):
        cmd = "hg tag"
        if force:
            cmd += " -f"
        cmd += " %s" % branch
        result = self._run_cmd_on_console(cmd)
        self._do_cmd_notification("branch")
        return result        

class _WsUpdateStateMgr:
    # We save this data in a file so that it survives closing/opening the GUI
    def __init__(self):
        self._saved_state_msg = "hg patches saved state"
        self._state_file = ".hg/gwsmhg.pm.wsu.state"
        self._copy_file = ".hg/gwsmhg.pm.wsu.patches.copy"
        self._get_copy_re = re.compile("^copy\s*\S*\s*to\s*(\S*)\n$")
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
        res, sout, serr = utils.run_cmd('hg log --template "{desc|firstline}" --rev tip')
        return sout == self._saved_state_msg
    def parent_is_patches_saved_state(self):
        res, sout, serr = utils.run_cmd('hg parent --template "{desc|firstline}"')
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

class PMInterface(BaseInterface):
    def __init__(self, console_log):
        BaseInterface.__init__(self, "MQ", console_log)
        self._ws_update_mgr = _WsUpdateStateMgr()
        self._adding_re = re.compile("^adding\s.*$")
        self._qpush_re = re.compile("^(merging|applying)\s.*$", re.M)
        self.file_state_changing_cmds = ["qfold", "qsave", "qpop", "qpush", "qfinish", "qsave-pfu", "qrestore", "qnew"]
        self.tag_changing_cmds = self.file_state_changing_cmds + ["qrename", "qdelete", "qimport", "update", "pull"]
        self.file_state_changing_cmds += ["add", "copy", "remove", "rename", "revert", "delete"]
    def _map_cmd_result(self, result, stdout_expected=True, ignore_err_re=None):
        if not result[0]:
            return cmd_result.map_cmd_result(result, stdout_expected=stdout_expected, ignore_err_re=ignore_err_re)
        else:
            flags = cmd_result.ERROR
            if result[2].find('use -f to force') is not -1:
                flags |= cmd_result.SUGGEST_FORCE
            if result[2].find('refresh first') is not -1:
                flags |= cmd_result.SUGGEST_REFRESH
            if result[2].find('(revert --all, qpush to recover)') is not -1:
                flags |= cmd_result.SUGGEST_RECOVER
            return (flags, result[1], result[2])
    def _run_cmd_on_console(self, cmd, stdout_expected=True, ignore_err_re=None):
        result = utils.run_cmd_in_console(cmd, self._console_log)
        return self._map_cmd_result(result, stdout_expected, ignore_err_re=ignore_err_re)
    def get_parent(self, patch):
        parent = "qparent"
        for applied_patch in self.get_applied_patches():
            if patch == applied_patch:
                return parent
            else:
                parent = applied_patch
        return None
    def get_file_status_list(self, patch=None):
        if patch and not self.get_patch_is_applied(patch):
            pfn = self.get_patch_file_name(patch)
            result, file_list = putils.get_patch_files(pfn, status=True)
            if result:
                return (cmd_result.OK, file_list, "")
            else:
                return (cmd_result.WARNING, "", file_list)
        top = self.get_top_patch()
        if not top:
            # either we're not in an mq playground or no patches are applied
            return (cmd_result.OK, [], "")
        cmd = "hg status -mardC"
        if patch:
            parent = self.get_parent(patch)
            cmd += " --rev %s --rev %s" % (parent, patch)
        else:
            parent = self.get_parent(top)
            cmd += " --rev %s" % parent
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
            if (index + 1) < numlines and lines[index + 1][0] == " ":
                index += 1
                extra_info = lines[index][2:]
            else:
                extra_info = None
            file_list.append((name, status, extra_info))
            index += 1
        return (res, file_list, serr)
    def get_in_progress(self):
        return self.get_top_patch() or self._ws_update_mgr.is_in_progress()
    def get_applied_patches(self):
        res, op, err = utils.run_cmd("hg qapplied")
        if res != 0:
                return []
        return op.splitlines(False)
    def get_unapplied_patches(self):
        res, op, err = utils.run_cmd("hg qunapplied")
        if res != 0:
                return []
        return op.splitlines(False)
    def get_patch_is_applied(self, patch):
        return patch in self.get_applied_patches()
    def get_top_patch(self):
        res, sout, serr = utils.run_cmd("hg qtop")
        if res:
            return None
        else:
            return sout.strip()
    def get_base_patch(self):
        res, sout, serr = utils.run_cmd("hg qapplied")
        if res or not sout:
            return None
        else:
            return sout.splitlines(False)[0]
    def get_next_patch(self):
        res, sout, serr = utils.run_cmd("hg qnext")
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
                    return (cmd_result.OK, diff, "")
                else:
                    return (cmd_result.WARNING, "", diff)
        else:
            top = self.get_top_patch()
            if top:
                parent = self.get_parent(top)
            else:
                return (cmd_result.OK, "", "")
        cmd = "hg diff --rev %s " % parent
        if patch:
            cmd += "--rev %s " % patch
        if file_list:
            cmd += " ".join(file_list)
        res, sout, serr = utils.run_cmd(cmd)
        if res != 0:
            res = cmd_result.ERROR
        return (res, sout, serr)
    def do_refresh(self):
        result = self._run_cmd_on_console("hg qrefresh")
        if not result[0]:
            self._do_cmd_notification("qrefresh")
        return result
    def do_pop_to(self, patch=None, force=False):
        if patch is None:
            if force:
                result = self._run_cmd_on_console("hg qpop -f")
            else:
                result = self._run_cmd_on_console("hg qpop")
        elif patch is "":
            if force:
                result = self._run_cmd_on_console("hg qpop -f -a")
            else:
                result = self._run_cmd_on_console("hg qpop -a")
        else:
            if force:
                result = self._run_cmd_on_console("hg qgoto -f %s" % patch)
            else:
                result = self._run_cmd_on_console("hg qgoto %s" % patch)
        self._do_cmd_notification("qpop")
        return result
    def do_push_to(self, patch=None, force=False, merge=False):
        if merge:
            mflag = "-m"
        else:
            mflag = ""
        if patch is None:
            if force:
                result = self._run_cmd_on_console("hg qpush %s -f" % mflag, ignore_err_re=self._qpush_re)
            else:
                result = self._run_cmd_on_console("hg qpush %s" % mflag, ignore_err_re=self._qpush_re)
        elif patch is "":
            if force:
                result = self._run_cmd_on_console("hg qpush %s -f -a" % mflag, ignore_err_re=self._qpush_re)
            else:
                result = self._run_cmd_on_console("hg qpush %s -a" % mflag, ignore_err_re=self._qpush_re)
        else:
            if force:
                result = self._run_cmd_on_console("hg qgoto %s -f %s" % (mflag, patch), ignore_err_re=self._qpush_re)
            else:
                result = self._run_cmd_on_console("hg qgoto %s %s" % (mflag, patch), ignore_err_re=self._qpush_re)
        self._do_cmd_notification("qpush")
        if not result[0] and merge and len(self.get_unapplied_patches()) == 0:
            self._ws_update_mgr.set_state("merged")
        return result
    def get_patch_file_name(self, patch):
        return os.path.join(os.getcwd(), ".hg", "patches", patch)
    def get_patch_description(self, patch):
        pfn = self.get_patch_file_name(patch)
        res, descr_lines = putils.get_patch_descr_lines(pfn)
        descr = os.linesep.join(descr_lines) + os.linesep
        if res:
            return (cmd_result.OK, descr, "")
        else:
            return (cmd_result.ERROR, descr, "Error reading description to \"%s\" patch file" % patch)
    def do_set_patch_description(self, patch, descr):
        pfn = self.get_patch_file_name(patch)
        self._console_log.start_cmd("set description for: %s" %patch)
        res = putils.set_patch_descr_lines(pfn, descr.splitlines(False))
        if res:
            self._console_log.append_stdout(descr)
            res = cmd_result.OK
            serr = ""
        else:
            serr = "Error writing description to \"%s\" patch file" % patch
            self._console_log.append_stderr(serr)
            res = cmd_result.ERROR
        self._console_log.end_cmd()
        return (res, "", serr)
    def get_description_is_finish_ready(self, patch):
        pfn = self.get_patch_file_name(patch)
        res, pf_descr_lines = putils.get_patch_descr_lines(pfn)
        pf_descr = os.linesep.join(pf_descr_lines).strip()
        if not pf_descr:
            return False
        res, rep_descr, sout = utils.run_cmd('hg log --template "{desc}" --rev %s' % patch)
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
        result = self._run_cmd_on_console("hg qfinish %s" % patch)
        self._do_cmd_notification("qfinish")
        return result
    def do_rename_patch(self, old_name, new_name):
        result = self._run_cmd_on_console("hg qrename %s %s" % (old_name, new_name))
        self._do_cmd_notification("qrename")
        return result
    def do_delete_patch(self, patch):
        result = self._run_cmd_on_console("hg qdelete %s" % patch)
        self._do_cmd_notification("qdelete")
        return result
    def do_fold_patch(self, patch):
        result = self._run_cmd_on_console("hg qfold %s" % patch)
        self._do_cmd_notification("qfold")
        return result
    def do_import_patch(self, patch_file_name, as_patch_name=None, force=False):
        cmd = "hg qimport "
        if as_patch_name:
            cmd += "-n %s " % as_patch_name
        if force:
            cmd += "-f "
        res, sout, serr = self._run_cmd_on_console(cmd + patch_file_name, ignore_err_re=self._adding_re)
        if res and re.search("already exists", serr):
            res |= cmd_result.SUGGEST_FORCE_OR_RENAME
        self._do_cmd_notification("qimport")
        return (res, sout, serr)
    def do_new_patch(self, patch_name_raw, force=False):
        patch_name = re.sub('\s', '_', patch_name_raw)
        if force:
            res, sout, serr = self._run_cmd_on_console("hg qnew -f %s" % patch_name)
        else:
            res, sout, serr = self._run_cmd_on_console("hg qnew %s" % patch_name)
        self._do_cmd_notification("qnew")
        if res & cmd_result.SUGGEST_REFRESH:
            res |= cmd_result.SUGGEST_FORCE
        return (res, sout, serr)
    def do_remove_files(self, file_list, force=False):
        applied_count = len(self.get_applied_patches())
        if not file_list or applied_count == 0:
            return (cmd_result.OK, "", "")
        elif applied_count == 1:
            parent = "qparent"
        else:
            res, sout, serr = utils.run_cmd("hg qprev")
            parent = sout.strip()
        cmd = "hg revert --rev %s " % parent
        if force:
            cmd += "-f "
        result = self._run_cmd_on_console(" ".join([cmd] + file_list)) 
        self._do_cmd_notification("remove")
        return result
    def do_save_queue_state_for_update(self):
        result = self._run_cmd_on_console("hg qsave -e -c")
        self._ws_update_mgr.start(result[2], "qsaved")
        self._do_cmd_notification("qsave-pfu")
        return result
    def do_pull_from(self, rev=None, source=None):
        result = BaseInterface.do_pull_from(self, rev=rev, source=source)
        if cmd_result.is_less_than_error(result[0]):
            self._ws_update_mgr.set_state("pulled")
        return result
    def do_update_workspace(self, rev=None):
        cmd = "hg update -C"
        if rev:
            cmd += " -r %s" %rev
        result = self._run_cmd_on_console(cmd)
        if not result[0]:
            self._do_cmd_notification("update")
            self._ws_update_mgr.set_state("updated")
        return result
    def do_clean_up_after_update(self):
        pcd = self._ws_update_mgr.get_patches_copy_dir()
        if pcd:
            top_patch = self.get_top_patch()
            if top_patch:
                utils.run_cmd("hg qpop -a")
            self._ws_update_mgr.finish()
            result = self._run_cmd_on_console("hg qpop -a -n %s" % pcd)
            if top_patch:
                utils.run_cmd("hg qgoto %s" % top_patch)
                self._do_cmd_notification("qpush")
            else:
                self._do_cmd_notification("qpop")
            return result
        else:
            return (cmd_result.INFO, "Saved patch directory not found.", "")
    def get_ws_update_qsave_ready(self, unapplied_count=None):
        if unapplied_count is None:
            unapplied_count = len(self.get_unappplied_patches())
        return not unapplied_count and not self._ws_update_mgr.is_in_progress()
    def get_ws_update_ready(self, applied_count=None):
        if applied_count is None:
            applied_count = len(self.get_appplied_patches())
        if self._ws_update_mgr.tip_is_patches_saved_state():
            return False
        return not applied_count and self._ws_update_mgr.get_state_is_in(["pulled"])
    def get_ws_update_merge_ready(self, unapplied_count=None):
        if unapplied_count is None:
            unapplied_count = len(self.get_unappplied_patches())
        if self._ws_update_mgr.parent_is_patches_saved_state():
            return False
        return unapplied_count and self._ws_update_mgr.get_state_is_in(["updated"])
    def get_ws_update_clean_up_ready(self, applied_count=None):
        return self._ws_update_mgr.get_state_is_in(["merged"])
    def get_ws_update_pull_ready(self, applied_count=None):
        if applied_count is None:
            applied_count = len(self.get_appplied_patches())
        return not applied_count and self._ws_update_mgr.get_state_is_in(["qsaved"])
    def get_ws_update_to_ready(self, applied_count=None):
        if applied_count is None:
            applied_count = len(self.get_appplied_patches())
        return not applied_count and self._ws_update_mgr.get_state_is_in(["qsaved", "pulled"])

class CombinedInterface:
    def __init__(self, busy_indicator, tooltips=None):
        self.log = console.ConsoleLog(busy_indicator=busy_indicator, tooltips=tooltips)
        self.SCM = SCMInterface(self.log)
        self.PM = PMInterface(self.log)

