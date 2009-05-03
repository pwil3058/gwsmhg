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

import os, os.path, tempfile, pango, re
from gwsmhg_pkg import text_edit, utils, cmd_result, console, putils

DEFAULT_NAME_EVARS = ["GIT_AUTHOR_NAME", "GECOS"]
DEFAULT_EMAIL_VARS = ["GIT_AUTHOR_EMAIL", "EMAIL_ADDRESS"]

class BaseInterface:
    def __init__(self, name, console_log):
        self._console_log = console_log
        self.name = name
        self._notification_cbs = {}
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
    def add_notification_cb(self, cmd_list, cb):
        for cmd in cmd_list:
            if self._notification_cbs.has_key(cmd):
                self._notification_cbs[cmd].append(cb)
            else:
                self._notification_cbs[cmd] = [cb]
    def _do_cmd_notification(self, cmd, data=None):
        if self._notification_cbs.has_key(cmd):
            for cb in self._notification_cbs[cmd]:
                if data is not None:
                    cb(data)
                else:
                    cb()
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
    def do_pull(self, rev=None, update=False, source=None):
        cmd = "hg pull"
        if update:
            cmd += " -u"
        if rev:
            cmd += " -r %s" % rev
        if source:
            cmd += " %s" % source
        return self._run_cmd_on_console(cmd)

class SCMInterface(BaseInterface):
    def __init__(self, console_log):
        BaseInterface.__init__(self, "hg", console_log)
        self.tracked_statuses = (None, "C") + self.modification_statuses
    def _run_cmd_on_console(self, cmd, stdout_expected=True):
        result = utils.run_cmd_in_console(cmd, self._console_log)
        return cmd_result.map_cmd_result(result, stdout_expected)
    def get_patches_applied(self):
        res = utils.run_cmd("hg qtop")
        return res[0] == 0
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
    def get_parents_data(self, rev=None):
        cmd = 'hg parents --template "{rev}:{date|age}:{tags}:{branches}:{author|person}:{desc|firstline}' + os.linesep + '"'
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
    def get_heads_data(self):
        cmd = 'hg heads --template "{rev}:{date|age}:{tags}:{branches}:{author|person}:{desc|firstline}' + os.linesep + '"'
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
            tag_list.append([dat.group(1), int(dat.group(2))])
        cmd = 'hg log --template "{branches}:{date|age}:{author|person}:{desc|firstline}" --rev '
        for tag in tag_list:
            res, sout, serr = utils.run_cmd(cmd + str(tag[1]))
            tag += sout.split(":", 3)
        return (res, tag_list, serr)
    def get_branches_data(self):
        res, sout, serr = utils.run_cmd("hg branches")
        if res:
            return (res, sout, serr)
        de = re.compile("^(\S+)\s*(\d+):")
        tag_list = []
        for line in sout.splitlines(False):
            dat = de.match(line)
            tag_list.append([dat.group(1), int(dat.group(2))])
        cmd = 'hg log --template "{tags}:{date|age}:{author|person}:{desc|firstline}" --rev '
        for tag in tag_list:
            res, sout, serr = utils.run_cmd(cmd + str(tag[1]))
            tag += sout.split(":", 3)
        return (res, tag_list, serr)
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
        return self._run_cmd_on_console(cmd)
    def do_pull(self, rev=None, update=False, source=None):
        cmd = "hg pull"
        if update:
            cmd += " -u"
        if rev:
            cmd += " -r %s" %rev
        if source:
            cmd += " %s" % source
        return self._run_cmd_on_console(cmd)

class _WsUpdateStateTagMgr:
    def __init__(self):
        self._saved_state_msg = "hg patches saved state"
        self._common_hdr = "gwsmhg.ws."
        self._main_tag = self._common_hdr + "update"
        self._state_tag_hdr = self._common_hdr + "state."
        self._patches_copy_tag_hdr = self._common_hdr + "copy."
        self._get_copy_re = re.compile("^copy\s*\S*\s*to\s*(\S*)\n$")
        self._common_tag_re = re.compile("^" + self._common_hdr + "(\S*)$")
        self._state_tag_re = re.compile("^" + self._state_tag_hdr + "(\S*)$")
        self._patches_copy_tag_re = re.compile("^" + self._patches_copy_tag_hdr + "(\S*)$")
    def initialize(self, serr, state):
        if self.tip_is_patches_saved_state():
            tag_list = [self._main_tag]
            match = self._get_copy_re.match(serr)
            if match:
                tag_list.append(self._patches_copy_tag_hdr + os.path.basename(match.group(1)))
            utils.run_cmd("hg tag --rev tip --local %s" % " ".join(tag_list))
        self.set_state_tag(state)
    def is_in_progress(self):
        res, sout, serr = utils.run_cmd('hg log --template "{desc|firstline}" --rev %s' % self._main_tag)
        return res == 0
    def tip_is_patches_saved_state(self):
        res, sout, serr = utils.run_cmd('hg log --template "{desc|firstline}" --rev tip')
        return sout == self._saved_state_msg
    def parent_is_patches_saved_state(self):
        res, sout, serr = utils.run_cmd('hg parent --template "{desc|firstline}"')
        return sout == self._saved_state_msg
    def _get_tag_list(self, regex):
        res, sout, serr = utils.run_cmd('hg log --template "{tags}\n" --rev %s' % self._main_tag)
        result = []
        for tag in sout.split():
            if regex.match(tag):
                result.append(tag)
        return result
    def set_state_tag(self, state):
        state_tags = self._get_tag_list(self._state_tag_re)
        utils.run_cmd('hg tag --local --remove %s' % " ".join(state_tags))
        utils.run_cmd('hg tag --local --rev %s %s%s' % (self._main_tag, self._state_tag_hdr, state))
    def get_state_is_in(self, state_list):
        state_tags = self._get_tag_list(self._state_tag_re)
        for state in state_list:
            if "".join([self._state_tag_hdr, state]) in state_tags:
                return True
        return False
    def get_patches_copy_dir(self):
        tags = self._get_tag_list(self._patches_copy_tag_re)
        return tags[0]
    def clear_tags(self):
        update_tags = self._get_tag_list(self._common_tag_re)
        if update_tags:
            utils.run_cmd('hg tag --local --remove %s' % " ".join(update_tags))

class PMInterface(BaseInterface):
    def __init__(self, console_log):
        BaseInterface.__init__(self, "MQ", console_log)
        self._ws_update_mgr = _WsUpdateStateTagMgr()
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
            cmd += " --rev %s" % patch
            parent = self.get_parent(patch)
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
            self._ws_update_mgr.set_state_tag("merged")
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
        print result, self._ws_update_mgr.tip_is_patches_saved_state()
        self._ws_update_mgr.initialize(result[2], "qsaved")
        self._do_cmd_notification("qsave-pfu")
        return result
    def do_pull(self, rev=None, source=None):
        result = BaseInterface.do_pull(self, rev=rev, source=source)
        if not result[0]:
            self._ws_update_mgr.set_state_tag("pulled")
            self._do_cmd_notification("pull")
        return result
    def do_update_workspace(self, rev=None):
        cmd = "hg update -C"
        if rev:
            cmd += " -r %s" %rev
        result = self._run_cmd_on_console(cmd)
        if not result[0]:
            self._do_cmd_notification("update")
            self._ws_update_mgr.set_state_tag("updated")
        return result
    def do_clean_up_after_update(self):
        pcd = self._ws_update_mgr.get_patches_copy_dir()
        if pcd:
            top_patch = self.get_top_patch()
            if top_patch:
                utils.run_cmd("hg qpop -a")
            self._ws_update_mgr.clear_tags()
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

