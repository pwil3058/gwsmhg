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

class SCMInterface:
    def __init__(self, console_log=None):
        self._console_log = console_log
        self.name = "hg"
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
        self.tracked_statuses = (None, "C") + self.modification_statuses
        self._name_envars = DEFAULT_NAME_EVARS
        self._email_envars = DEFAULT_EMAIL_VARS
        self._commit_notification_cbs = []
    def _run_cmd_on_console(self, cmd, stdout_expected=True):
        result = utils.run_cmd_in_console(cmd, self._console_log)
        return cmd_result.map_cmd_result(result, stdout_expected)
    def get_patches_applied(self):
        res = utils.run_cmd("hg qtop")
        return res[0] == 0
    def get_default_commit_save_file(self):
        return os.path.join(".hg", "gwsmhg.saved.commit")
    def get_status_row_data(self):
        return (self.status_deco_map, self.extra_info_sep, self.modified_dir_status, self.default_nonexistant_status)
    def _get_first_in_envar(self, envar_list):
        for envar in envar_list:
            try:
                value = os.environ[envar]
                if value is not "":
                    return value
            except KeyError:
                continue
        return ""
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
    def _map_result(self, result, stdout_expected=False):
        outres, sout, serr = cmd_result.map_cmd_result(result, stdout_expected)
        if outres != cmd_result.OK:
            for force_suggested in ["use -f to force", "not overwriting - file exists"]:
                if serr.find(force_suggested) != -1 or sout.find(force_suggested) != -1:
                    outres += cmd_result.SUGGEST_FORCE
        return (outres, sout, serr)
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
    def add_files(self, file_list, dry_run=False):
        cmd = "hg add"
        if dry_run:
            cmd += " -n --verbose"
        if file_list:
            cmd = " ".join([cmd] + file_list)
        if dry_run:
            return self._map_result(utils.run_cmd(cmd), stdout_expected=True)
        else:
            return self._run_cmd_on_console(cmd)
    def add_commit_notification_cb(self, notification_cb):
        self._commit_notification_cbs.append(notification_cb)
    def del_commit_notification_cb(self, notification_cb):
        try:
            del self._commit_notification_cbs[self._commit_notification_cbs.index(notification_cb)]
        except:
            pass
    def commit_change(self, msg, file_list=[]):
        cmd = "hg commit"
        if msg:
            # to avoid any possible problems with interaction of characters in the
            # message with the shell we'll stick the message in a temporary file
            msg_fd, msg_file_name = tempfile.mkstemp()
            os.write(msg_fd, msg)
            os.close(msg_fd)
            cmd += " --logfile %s" % msg_file_name
        if file_list:
            cmd += " %s" % " ".join(file_list)
        result = self._run_cmd_on_console(cmd)
        if msg:
            os.remove(msg_file_name)
        for notification_cb in self._commit_notification_cbs:
            notification_cb(file_list)
        return result
    def remove_files(self, file_list, force=False):
        if force:
            return self._run_cmd_on_console("hg remove -f " + " ".join(file_list))
        else:
            return self._run_cmd_on_console("hg remove " + " ".join(file_list))
    def copy_files(self, file_list, target, force=False, dry_run=False):
        cmd = "hg copy "
        if dry_run:
            cmd += "-n --verbose "
        if force:
            cmd += "-f "
        cmd = " ".join([cmd] + file_list + [target])
        if dry_run:
            return self._map_result(utils.run_cmd(cmd), stdout_expected=True)
        else:
            return self._run_cmd_on_console(cmd)
    def move_files(self, file_list, target, force=False, dry_run=False):
        cmd = "hg rename "
        if dry_run:
            cmd += "-n --verbose "
        if force:
            cmd += "-f "
        cmd = " ".join([cmd] + file_list + [target])
        if dry_run:
            return self._map_result(utils.run_cmd(cmd), stdout_expected=True)
        else:
            return self._run_cmd_on_console(cmd)
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
    def revert_files(self, file_list, dry_run=False):
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
            return self._run_cmd_on_console(cmd, stdout_expected=True)
    def do_exec_tool_cmd(self, cmd):
        return self._run_cmd_on_console("hg " + cmd, stdout_expected=True)
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

class PMInterface:
    def __init__(self, console_log=None):
        self._console_log = console_log
        self.name = "MQ"
        self.status_deco_map = {
            None: (pango.STYLE_NORMAL, "black"),
            "M": (pango.STYLE_NORMAL, "blue"),
            "A": (pango.STYLE_NORMAL, "darkgreen"),
            "R": (pango.STYLE_NORMAL, "red"),
            "!": (pango.STYLE_ITALIC, "pink"),
        }
        self.extra_info_sep = " <- "
        self.modified_dir_status = "M"
        self.default_nonexistant_status = "!"
        self.modification_statuses = ("M", "A", "R", "!")
        self._name_envars = DEFAULT_NAME_EVARS
        self._email_envars = DEFAULT_EMAIL_VARS
        self._qrefresh_notification_cbs = []
        self._qpush_notification_cbs = []
        self._qpop_notification_cbs = []
        self._qfinish_notification_cbs = []
    def _map_cmd_result(self, result, stdout_expected=True):
        if not result[0]:
            return cmd_result.map_cmd_result(result, stdout_expected=stdout_expected)
        else:
            flags = cmd_result.ERROR
            if result[2].find('use -f to force') is not -1:
                flags |= cmd_result.SUGGEST_FORCE
            if result[2].find('refresh first') is not -1:
                flags |= cmd_result.SUGGEST_REFRESH
            if result[2].find('(revert --all, qpush to recover)') is not -1:
                flags |= cmd_result.SUGGEST_RECOVER
            return (flags, result[1], result[2])
    def _run_cmd_on_console(self, cmd, stdout_expected=True):
        result = utils.run_cmd_in_console(cmd, self._console_log)
        return self._map_cmd_result(result, stdout_expected)
    def get_status_row_data(self):
        return (self.status_deco_map, self.extra_info_sep, self.modified_dir_status, self.default_nonexistant_status)
    def add_qrefresh_notification_cb(self, notification_cb):
        self._qrefresh_notification_cbs.append(notification_cb)
    def del_qrefresh_notification_cb(self, notification_cb):
        try:
            del self._qrefresh_notification_cbs[self._qrefresh_notification_cbs.index(notification_cb)]
        except:
            pass
    def add_qpop_notification_cb(self, notification_cb):
        self._qpop_notification_cbs.append(notification_cb)
    def del_qpop_notification_cb(self, notification_cb):
        try:
            del self._qpop_notification_cbs[self._qpop_notification_cbs.index(notification_cb)]
        except:
            pass
    def add_qpush_notification_cb(self, notification_cb):
        self._qpush_notification_cbs.append(notification_cb)
    def del_qpush_notification_cb(self, notification_cb):
        try:
            del self._qpush_notification_cbs[self._qpush_notification_cbs.index(notification_cb)]
        except:
            pass
    def add_qfinish_notification_cb(self, notification_cb):
        self._qfinish_notification_cbs.append(notification_cb)
    def del_qfinish_notification_cb(self, notification_cb):
        try:
            del self._qfinish_notification_cbs[self._qfinish_notification_cbs.index(notification_cb)]
        except:
            pass
    def get_parents(self, patch):
        cmd = os.linesep.join(['hg parents --template "{rev}', '" -r %s' % patch])
        res, sout, serr = utils.run_cmd(cmd)
        return sout.splitlines(False)
    def get_file_status_list(self, patch=None):
        if patch and not self.get_patch_is_applied(patch):
            pfn = self.get_patch_file_name(patch)
            result, file_list = putils.get_patch_files(pfn, status=True)
            if result:
                return (cmd_result.OK, file_list, "")
            else:
                return (cmd_result.WARNING, "", file_list)
        res, top, serr = utils.run_cmd("hg qtop")
        if res:
            # either we're not in an mq playground or no patches are applied
            return (cmd_result.OK, [], "")
        cmd = "hg status -mardC"
        if patch:
            cmd += " --rev %s" % patch
            parents = self.get_parents(patch)
        else:
            parents = self.get_parents("qtip")
        cmd += " --rev %s" % parents[0] # use the newest parent
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
        res, op, err = utils.run_cmd("hg qapplied %s" % patch)
        return op.strip() == patch
    def top_patch(self):
        res, sout, serr = utils.run_cmd("hg qtop")
        if res:
            return None
        else:
            return sout.strip()
    def base_patch(self):
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
    def do_refresh(self):
        result = self._run_cmd_on_console("hg qrefresh")
        if not result[0]:
            for call_back in self._qrefresh_notification_cbs:
                call_back()
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
        for call_back in self._qpop_notification_cbs:
            call_back()
        return result
    def do_push_to(self, patch=None, force=False, merge=False):
        if merge:
            mflag = "-m"
        else:
            mflag = ""
        if patch is None:
            if force:
                result = self._run_cmd_on_console("hg qpush %s -f" % mflag)
            else:
                result = self._run_cmd_on_console("hg qpush %s" % mflag)
        elif patch is "":
            if force:
                result = self._run_cmd_on_console("hg qpush %s -f -a" % mflag)
            else:
                result = self._run_cmd_on_console("hg qpush %s -a" % mflag)
        else:
            if force:
                result = self._run_cmd_on_console("hg qgoto %s -f %s" % (mflag, patch))
            else:
                result = self._run_cmd_on_console("hg qgoto %s %s" % (mflag, patch))
        for call_back in self._qpush_notification_cbs:
            call_back()
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
        for call_back in self._qfinish_notification_cbs:
            call_back()
        return result
    def do_save_queue_state(self):
        return self._run_cmd_on_console("hg qsave")
    def do_save_queue_state_for_update(self):
        result = self._run_cmd_on_console("hg qsave -e -c")
        for call_back in self._qpop_notification_cbs:
            call_back()
        return result
    def do_rename_patch(self, old_name, new_name):
        return self._run_cmd_on_console("hg qrename %s %s" % (old_name, new_name))
    def do_delete_patch(self, patch):
        return self._run_cmd_on_console("hg qdelete %s" % patch)
    def do_fold_patch(self, patch):
        return self._run_cmd_on_console("hg qfold %s" % patch)
    def do_import_patch(self, patch_file_name, as_patch_name=None, force=False):
        cmd = "hg qimport "
        if as_patch_name:
            cmd += "-n %s " % as_patch_name
        if force:
            cmd += "-f "
        return self._run_cmd_on_console(cmd + patch_file_name)
    def do_clean_up_after_update(self):
        pde = re.compile("^patches\.(\d+)$")
        biggest = None
        for item in os.listdir(".hg"):
            if os.path.isdir(os.sep.join([".hg", item])):
                match = pde.match(item)
                if match:
                    num = int(match.group(1))
                    if not biggest or num > biggest:
                        biggest = num
        if biggest:
            return self._run_cmd_on_console("hg qpop -a -n patches.%d" % biggest)
        else:
            return (cmd_result.INFO, "Saved patch directory not found.", "")
    def do_new_patch(self, patch_name_raw, force=False):
        patch_name = re.sub('\s', '_', patch_name_raw)
        if force:
            res, sout, serr = self._run_cmd_on_console("hg qnew -f %s" % patch_name)
        else:
            res, sout, serr = self._run_cmd_on_console("hg qnew %s" % patch_name)
        for call_back in self._qpush_notification_cbs:
            call_back()
        if res & cmd_result.SUGGEST_REFRESH:
            res |= cmd_result.SUGGEST_FORCE
        return (res, sout, serr)

class CombinedInterface:
    def __init__(self, tooltips=None):
        self.log = console.ConsoleLog(tooltips=tooltips)
        self.SCM = SCMInterface(self.log)
        self.PM = PMInterface(self.log)

