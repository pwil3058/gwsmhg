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

import os, gtk, gtksourceview, pango, gobject
from gwsmhg_pkg import utils, cmd_result, gutils

EDITORS_THAT_NEED_A_TERMINAL = ["vi", "joe"]
DEFAULT_EDITOR = "gedit"
DEFAULT_TERMINAL = "gnome-terminal"

def _edit_files_extern(filelist, editor_env_vars):
    edstr = DEFAULT_EDITOR
    for e in editor_env_vars:
        try:
            ed = os.environ[e]
            if ed is not "":
                edstr = ed
                break
        except KeyError:
            pass
    edlist = edstr.split()
    editor = edlist[0]
    options = edlist[1:]
    if not editor in EDITORS_THAT_NEED_A_TERMINAL:
        return apply(os.spawnlp, tuple([os.P_NOWAIT, editor, editor] + options + filelist))
    try:
        term  = os.environ['COLORTERM']
    except KeyError:
        try:
            term = os.environ['TERM']
        except KeyError:
            term = DEFAULT_TERMINAL
    return apply(os.spawnlp, tuple([os.P_NOWAIT, term, term, "-e", " ".join(edlist + filelist)]))

def edit_files_extern(filelist):
    return _edit_files_extern(filelist, ['VISUAL', 'EDITOR'])

def peruse_files_extern(filelist):
    return _edit_files_extern(filelist, ['PERUSER', 'VISUAL', 'EDITOR'])

import time

class SummaryBuffer(gtksourceview.SourceBuffer):
    def __init__(self, table=None, ifce=None):
        if not table:
            table = gtksourceview.SourceTagTable()
        gtksourceview.SourceBuffer.__init__(self, table=table)
        self._ifce = ifce
        self._action_group = gtk.ActionGroup("summary")
        self._action_group.add_actions(
            [
                ("summary_ack", None, "_Ack", None,
                 "Insert Acked-by tag at cursor position", self._insert_ack_acb),
                ("summary_sign_off", None, "_Sign Off", None,
                 "Insert Signed-off-by tag at cursor position", self._insert_sign_off_acb),
                ("summary_author", None, "A_uthor", None,
                 "Insert Author tag at cursor position", self._insert_author_acb),
            ])
    def _insert_sign_off_acb(self, action=None):
        self.insert_at_cursor("Signed-off-by: %s\n" % self._ifce.SCM.get_author_name_and_email())
    def _insert_ack_acb(self, action=None):
        self.insert_at_cursor("Acked-by: %s\n" % self._ifce.SCM.get_author_name_and_email())
    def _insert_author_acb(self, action=None):
        self.insert_at_cursor("Author: %s\n" % self._ifce.SCM.get_author_name_and_email())

class SummaryView(gtksourceview.SourceView):
    def __init__(self, buffer=None, table=None, ifce=None):
        if not buffer:
            buffer = SummaryBuffer(table, ifce)
        gtksourceview.SourceView.__init__(self, buffer)
        fdesc = pango.FontDescription("mono, 10")
        self.modify_font(fdesc)
        self.set_margin(72)
        self.set_show_margin(True)
        context = self.get_pango_context()
        metrics = context.get_metrics(fdesc)
        width = pango.PIXELS(metrics.get_approximate_char_width() * 81)
        x, y = self.buffer_to_window_coords(gtk.TEXT_WINDOW_TEXT, width, width / 3)
        self.set_size_request(x, y)
        self.set_cursor_visible(True)
        self.set_editable(True)
        self._ui_manager = gtk.UIManager()
        self._ui_manager.insert_action_group(buffer._action_group, -1)
    def get_action(self, action_name):
        for action_group in self._ui_manager.get_action_groups():
            action = action_group.get_action(action_name)
            if action:
                return action
        return None
    def get_ui_manager(self):
        return self._ui_manager
    def get_ui_widget(self, path):
        return self._ui_manager.get_widget(path)
    def get_accel_group(self):
        return self._ui_manager.get_accel_group()
    def get_msg(self):
        buffer = self.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())

class ChangeSummaryBuffer(SummaryBuffer):
    def __init__(self, table=None, ifce=None, auto_save=True):
        if not table:
            table = gtksourceview.SourceTagTable()
        SummaryBuffer.__init__(self, table=table, ifce=ifce)
        self._save_interval = 1000 # milliseconds
        self._save_file_name = self._ifce.SCM.get_default_commit_save_file()
        if not os.path.exists(self._save_file_name):
            self.save_summary(content="")
        self._action_group.add_actions(
            [
                ("menu_summary", None, "_Summary"),
                ("change_summary_save", gtk.STOCK_SAVE, "_Save", "",
                 "Save commit summary", self._save_summary_acb),
                ("change_summary_save_as", gtk.STOCK_SAVE_AS, "S_ave as", "",
                 "Save commit summary to a file", self.save_summary_as),
                ("change_summary_load", gtk.STOCK_REVERT_TO_SAVED, "_Revert", "",
                 "Load summary from saved file", self._load_summary_acb),
                ("change_summary_load_from", gtk.STOCK_REVERT_TO_SAVED, "_Load from", "",
                 "Load summary from a file", self.load_summary_from),
                ("change_summary_insert_from", gtk.STOCK_PASTE, "_Insert from", "",
                 "Insert contents of a file at cursor position", self.insert_summary_from),
            ])
        self.save_toggle_action = gtk.ToggleAction(
                "summary_toggle_auto_save", "Auto Sa_ve",
                "Automatically/periodically save summary to file", gtk.STOCK_SAVE
            )
        self.save_toggle_action.connect("toggled", self._toggle_auto_save_acb)
        self.save_toggle_action.set_active(auto_save)
        self._action_group.add_action(self.save_toggle_action)
        # Load the saved content before (possibly) turning auto save on or
        # contents of saved file could be wiped out before it's loaded
        self.load_summary(already_checked=True)
        self._toggle_auto_save_acb()
    def save_summary(self, file_name=None, content=None):
        if not file_name:
            file_name = self._save_file_name
        try:
            save_file = open(file_name, 'w')
            if content is None:
                save_file.write(self.get_text(self.get_start_iter(), self.get_end_iter()))
            else:
                save_file.write(content)
            save_file.close()
            self._save_file_name = file_name
            self.set_modified(False)
        except:
            gutils.inform_user("Save failed!")
    def _save_summary_acb(self, action=None):
        self.save_summary()
    def save_summary_as(self, action=None):
        fn = gutils.ask_file_name("Enter file name", existing=False, suggestion=self._save_file_name)
        if fn and os.path.exists(fn) and not os.path.samefile(fn, self._save_file_name):
            if not os.path.samefile(fn, self._ifce.SCM.get_default_commit_save_file()):
                if not gutils.ask_ok_cancel(os.linesep.join([fn, "\nFile exists. Overwrite?"])):
                    return
        self.save_summary(file_name=fn)
    def _ok_to_overwrite_summary(self):
        if self.get_char_count():
            return gutils.ask_ok_cancel("Buffer contents will be destroyed. Continue?")
        return True
    def load_summary(self, file_name=None, already_checked=False):
        if not already_checked and not self._ok_to_overwrite_summary():
            return
        if not file_name:
            file_name = self._save_file_name
        try:
            save_file = open(file_name, 'r')
            self.set_text(save_file.read())
            save_file.close()
            self._save_file_name = file_name
            self.set_modified(False)
        except:
            gutils.inform_user("Load from file failed!")
    def _load_summary_acb(self, action=None):
        self.load_summary()
    def load_summary_from(self, action=None):
        if not self._ok_to_overwrite_summary():
            return
        fn = gutils.ask_file_name("Enter file name", existing=True)
        self.load_summary(file_name=fn, already_checked=True)
    def insert_summary_from(self, action=None):
        file_name = gutils.ask_file_name("Enter file name", existing=True)
        try:
            save_file = open(file_name, 'r')
            self.insert_at_cursor(save_file.read())
            save_file.close()
            self.set_modified(True)
        except:
            gutils.inform_user("Insert at cursor from file failed!")
    def get_auto_save(self):
        return self.save_toggle_action.get_active()
    def set_auto_save(self, active=True):
        self.save_toggle_action.set_active(active)
    def get_auto_save_interval(self):
        return self._save_interval
    def set_auto_save_inerval(self, interval):
        self._save_interval = interval
    def do_auto_save(self):
        if self.get_modified():
            self.save_summary()
        return self.get_auto_save()
    def _toggle_auto_save_acb(self, action=None):
        if self.get_auto_save():
            gobject.timeout_add(self._save_interval, self.do_auto_save)
    def finish_up(self, clear_save=False):
        if self.get_auto_save():
            self.set_auto_save(False)
            self.do_auto_save()
        if clear_save:
            self.save_summary(file_name=self._ifce.SCM.get_default_commit_save_file(), content="")

CHANGE_SUMMARY_UI_DESCR = \
'''
<ui>
  <menubar name="change_summary_menubar">
    <menu name="change_summary_menu" action="menu_summary">
      <menuitem action="change_summary_save"/>
      <menuitem action="change_summary_save_as"/>
      <menuitem action="change_summary_load"/>
      <menuitem action="change_summary_load_from"/>
      <menuitem action="change_summary_insert_from"/>
    </menu>
  </menubar>
  <toolbar name="change_summary_toolbar">
    <toolitem action="summary_ack"/>
    <toolitem action="summary_sign_off"/>
    <toolitem action="summary_author"/>
    <toolitem action="summary_toggle_auto_save"/>
  </toolbar>
</ui>
'''

class ChangeSummaryView(SummaryView):
    def __init__(self, buffer=None, auto_save=True, table=None, ifce=None):
        if not buffer:
            buffer = ChangeSummaryBuffer(table, ifce, auto_save)
        SummaryView.__init__(self, buffer, table, ifce)
        self.change_summary_merge_id = self._ui_manager.add_ui_from_string(CHANGE_SUMMARY_UI_DESCR)

class NewPatchSummaryBuffer(SummaryBuffer):
    def __init__(self, table=None, ifce=None):
        if not table:
            table = gtksourceview.SourceTagTable()
        SummaryBuffer.__init__(self, table=table, ifce=ifce)
        self._ifce = ifce
        self._action_group.add_actions(
            [
                ("menu_summary", None, "_Description"),
                ("patch_summary_insert_from", gtk.STOCK_PASTE, "_Insert from", "",
                 "Insert contents of a file at cursor position", self._insert_summary_from_acb),
            ])
    def _insert_summary_from_acb(self, action=None):
        file_name = gutils.ask_file_name("Enter file name", existing=True)
        try:
            save_file = open(file_name, 'r')
            self.insert_at_cursor(save_file.read())
            save_file.close()
            self.set_modified(True)
        except:
            gutils.inform_user("Insert at cursor from file failed!")

class PatchSummaryBuffer(NewPatchSummaryBuffer):
    def __init__(self, patch, table=None, ifce=None):
        self.patch = patch
        if not table:
            table = gtksourceview.SourceTagTable()
        NewPatchSummaryBuffer.__init__(self, table=table, ifce=ifce)
        self._ifce = ifce
        self._action_group.add_actions(
            [
                ("patch_summary_save", gtk.STOCK_SAVE, "_Save", "",
                 "Save commit summary", self._save_summary_acb),
                ("patch_summary_load", gtk.STOCK_REVERT_TO_SAVED, "_Reload", "",
                 "Load summary from saved file", self._load_summary_acb),
            ])
    def _save_summary_acb(self, action=None):
        text = self.get_text(self.get_start_iter(), self.get_end_iter())
        res, sout, serr = self._ifce.PM.do_set_patch_description(self.patch, text)
        if res:
            gutils.inform_user(os.linesep.join([sout, serr]))
        else:
            self.set_modified(False)
    def _ok_to_overwrite_summary(self):
        if self.get_char_count() and self.get_modified():
            return gutils.ask_ok_cancel("Buffer contents will be destroyed. Continue?")
        return True
    def load_summary(self):
        res, text, serr = self._ifce.PM.get_patch_description(self.patch)
        if res:
            gutils.inform_user(os.linesep.join([text, serr]))
        else:
            self.set_text(text)
            self.set_modified(False)
    def _load_summary_acb(self, action=None):
        if self._ok_to_overwrite_summary():
            self.load_summary()

NEW_PATCH_SUMMARY_UI_DESCR = \
'''
<ui>
  <menubar name="patch_summary_menubar">
    <menu name="patch_summary_menu" action="menu_summary">
      <separator/>
      <menuitem action="patch_summary_insert_from"/>
    </menu>
  </menubar>
  <toolbar name="patch_summary_toolbar">
    <toolitem action="summary_ack"/>
    <toolitem action="summary_sign_off"/>
    <toolitem action="summary_author"/>
  </toolbar>
</ui>
'''

class NewPatchSummaryView(SummaryView):
    def __init__(self, ifce, buffer=None, table=None):
        if not buffer:
            buffer = NewPatchSummaryBuffer(table, ifce)
        SummaryView.__init__(self, buffer, table, ifce)
        self.patch_summary_merge_id = self._ui_manager.add_ui_from_string(NEW_PATCH_SUMMARY_UI_DESCR)

PATCH_SUMMARY_UI_DESCR = \
'''
<ui>
  <menubar name="patch_summary_menubar">
    <menu name="patch_summary_menu" action="menu_summary">
      <menuitem action="patch_summary_load"/>
      <separator/>
    </menu>
  </menubar>
  <toolbar name="patch_summary_toolbar">
  </toolbar>
</ui>
'''

class PatchSummaryView(NewPatchSummaryView):
    def __init__(self, patch, ifce, table=None):
        buffer = PatchSummaryBuffer(patch, table, ifce)
        NewPatchSummaryView.__init__(self, ifce, buffer, table)
        self.patch_summary_merge_id = self._ui_manager.add_ui_from_string(PATCH_SUMMARY_UI_DESCR)
        action = buffer._action_group.get_action("patch_summary_save")
        self.save_button = gutils.ActionButton(action, use_underline=False)
    def load_summary(self):
        self.get_buffer().load_summary()

