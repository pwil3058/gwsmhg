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

import os, gtk, gtksourceview, pango
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

class ChangeSummaryBuffer(gtksourceview.SourceBuffer):
    def __init__(self, table=None, scm_ifce=None):
        if not table:
            table = gtksourceview.SourceTagTable()
        gtksourceview.SourceBuffer.__init__(self, table=table)
        self._scm_ifce = scm_ifce
        self._save_file_name = self._scm_ifce.get_default_commit_save_file()
    def save_summary(self, file_name=None):
        if not file_name:
            file_name = self._save_file_name
        try:
            save_file = open(file_name, 'w')
            save_file.write(self.get_text(self.get_start_iter(), self.get_end_iter()))
            save_file.close()
            self._save_file_name = file_name
            self.set_modified(False)
        except:
            gutils.inform_user("Save failed!")
    def save_summary_as(self):
        fn = gutils.ask_file_name("Enter file name", existing=False, suggestion=self._save_file_name)
        if fn and os.path.exists(fn) and not os.path.samefile(fn, self._save_file_name):
            if not os.path.samefile(fn, self._scm_ifce.get_default_commit_save_file()):
                if not gutils.ask_question(os.linesep.join([fn, "\nFile exists. Overwrite?"])):
                    return
        self.save_summary(fn)
    def load_summary(self, file_name=None):
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
    def load_summary_from(self):
        fn = gutils.ask_file_name("Enter file name", existing=True)
        self.load_summary(fn)
    def insert_summary_from(self):
        file_name = gutils.ask_file_name("Enter file name", existing=True)
        try:
            save_file = open(file_name, 'r')
            self.insert_at_cursor(save_file.read())
            save_file.close()
            self.set_modified(True)
        except:
            gutils.inform_user("Insert at cursor from file failed!")
    def insert_sign_off(self):
        self.insert_at_cursor("Signed-off-by: %s\n" % self._scm_ifce.get_author_name_and_email())
    def insert_ack(self):
        self.insert_at_cursor("Acked-by: %s\n" % self._scm_ifce.get_author_name_and_email())
    def insert_author(self):
        self.insert_at_cursor("Author: %s\n" % self._scm_ifce.get_author_name_and_email())

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
    <toolitem action="change_summary_ack"/>
    <toolitem action="change_summary_sign_off"/>
    <toolitem action="change_summary_author"/>
  </toolbar>
</ui>
'''

class ChangeSummaryView(gtksourceview.SourceView):
    def __init__(self, buffer=None, table=None, scm_ifce=None):
        if not buffer:
            buffer = ChangeSummaryBuffer(table, scm_ifce)
        gtksourceview.SourceView.__init__(self, buffer)
        self._save_file_name = None
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
        self._action_group = gtk.ActionGroup("change_summary")
        self._ui_manager = gtk.UIManager()
        self._ui_manager.insert_action_group(self._action_group, -1)
        self._action_group.add_actions(
            [
                ("menu_summary", None, "_Summary"),
                ("change_summary_save", gtk.STOCK_SAVE, "_Save", "",
                 "Save commit summary", self._save_summary_acb),
                ("change_summary_save_as", gtk.STOCK_SAVE_AS, "S_ave as", "",
                 "Save commit summary to a file", self._save_summary_as_acb),
                ("change_summary_load", gtk.STOCK_REVERT_TO_SAVED, "_Load", "",
                 "Load summary from saved file", self._load_summary_acb),
                ("change_summary_load_from", gtk.STOCK_REVERT_TO_SAVED, "Load _from", "",
                 "Load summary from a file", self._load_summary_from_acb),
                ("change_summary_insert_from", gtk.STOCK_PASTE, "_Insert from", "",
                 "Insert contents of a file at cursor position", self._insert_summary_from_acb),
                ("change_summary_ack", None, "_Ack", None,
                 "Insert Acked-by tag at cursor position", self._insert_ack_acb),
                ("change_summary_sign_off", None, "_Sign Off", None,
                 "Insert Signed-off-by tag at cursor position", self._insert_sign_off_acb),
                ("change_summary_author", None, "A_uthor", None,
                 "Insert Author tag at cursor position", self._insert_author_acb),
            ])
        self.change_summary_merge_id = self._ui_manager.add_ui_from_string(CHANGE_SUMMARY_UI_DESCR)
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
    def _save_summary_acb(self, action):
        self.get_buffer().save_summary()
    def _save_summary_as_acb(self, action):
        self.get_buffer().save_summary_as()
    def _load_summary_acb(self, action):
        self.get_buffer().load_summary()
    def _load_summary_from_acb(self, action):
        self.get_buffer().load_summary_from()
    def _insert_summary_from_acb(self, action):
        self.get_buffer().insert_summary_from()
    def _insert_sign_off_acb(self, action):
        self.get_buffer().insert_sign_off()
    def _insert_ack_acb(self, action):
        self.get_buffer().insert_ack()
    def _insert_author_acb(self, action):
        self.get_buffer().insert_author()
    def get_msg(self):
        buffer = self.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter())

