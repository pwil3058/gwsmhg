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
from gwsmhg_pkg import text_edit, utils, cmd_result, console

DEFAULT_NAME_EVARS = ["GIT_AUTHOR_NAME", "GECOS"]
DEFAULT_EMAIL_VARS = ["GIT_AUTHOR_EMAIL", "EMAIL_ADDRESS"]

class SCMInterface(console.ConsoleLogUser):
    def __init__(self, console_log=None):
        console.ConsoleLogUser.__init__(self, console_log)
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
    def get_patches_applied(self):
        return False
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
    def _map_result(self, result, stdout_is_data=False):
        outres, sout, serr = cmd_result.map_cmd_result(result, stdout_is_data)
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
            return self._map_result(utils.run_cmd(cmd), stdout_is_data=True)
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
            return self._map_result(utils.run_cmd(cmd), stdout_is_data=True)
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
            return self._map_result(utils.run_cmd(cmd), stdout_is_data=True)
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
            return self._map_result(utils.run_cmd(cmd), stdout_is_data=True)
        else:
            return self._run_cmd_on_console(cmd, stdout_is_data=True)
    def do_exec_tool_cmd(self, cmd):
        return self._run_cmd_on_console("hg " + cmd, stdout_is_data=True)

