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

class DiffTextBuffer(gtksourceview.SourceBuffer):
    def __init__(self, table=None):
        if not table:
            table = gtksourceview.SourceTagTable()
        gtksourceview.SourceBuffer.__init__(self, table)
        self.index_tag = self.create_tag("INDEX", weight=pango.WEIGHT_BOLD, foreground="#0000AA", family="monospace")
        self.sep_tag = self.create_tag("SEP", weight=pango.WEIGHT_BOLD, foreground="#0000AA", family="monospace")
        self.minus_tag = self.create_tag("MINUS", foreground="#AA0000", family="monospace")
        self.lab_tag = self.create_tag("LAB", foreground="#AA0000", family="monospace")
        self.plus_tag = self.create_tag("PLUS", foreground="#006600", family="monospace")
        self.star_tag = self.create_tag("STAR", foreground="#006600", family="monospace")
        self.rab_tag = self.create_tag("RAB", foreground="#006600", family="monospace")
        self.change_tag = self.create_tag("CHANGED", foreground="#AA6600", family="monospace")
        self.stats_tag = self.create_tag("STATS", foreground="#AA00AA", family="monospace")
        self.func_tag = self.create_tag("FUNC", foreground="#00AAAA", family="monospace")
        self.unchanged_tag = self.create_tag("UNCHANGED", foreground="black", family="monospace")
    def _append_tagged_text(self, text, tag):
        self.insert_with_tags(self.get_end_iter(), text, tag)
    def _append_patch_line(self, line):
        fc = line[0]
        if fc == " ":
            self._append_tagged_text(line, self.unchanged_tag)
        elif fc == "+":
            self._append_tagged_text(line, self.plus_tag)
        elif fc == "-":
            self._append_tagged_text(line, self.minus_tag)
        elif fc == "!":
            self._append_tagged_text(line, self.change_tag)
        elif fc == "@":
            i = line.find("@@", 2)
            if i == -1:
                self._append_tagged_text(line, self.stats_tag)
            else:
                self._append_tagged_text(line[:i+2], self.stats_tag)
                self._append_tagged_text(line[i+2:], self.func_tag)
                pass
        elif fc == "=":
            self._append_tagged_text(line, self.sep_tag)
        elif fc == "*":
            self._append_tagged_text(line, self.star_tag)
        elif fc == "<":
            self._append_tagged_text(line, self.lab_tag)
        elif fc == ">":
            self._append_tagged_text(line, self.rab_tag)
        else:
            self._append_tagged_text(line, self.index_tag)
    def set_contents(self, text):
        self.begin_not_undoable_action()
        self.set_text("")
        for line in text.splitlines():
            self._append_patch_line(line + os.linesep)
        self.end_not_undoable_action()
    def save_to_file(self, filename):
        try:
            file = open(filename, 'w')
        except IOError, (errno, strerror):
            return (False, strerror)
        text = self.get_text(self.get_start_iter(), self.get_end_iter())
        file.write(text)
        file.close()
        return (True, None)

DIFF_TEXT_UI_DESCR = \
'''
<ui>
  <toolbar name="diff_text_toolbar">
    <toolitem action="diff_save"/>
    <toolitem action="diff_save_as"/>
    <toolitem action="diff_refresh"/>
  </toolbar>
</ui>
'''

class DiffTextView(gtksourceview.SourceView, cmd_result.ProblemReporter):
    def __init__(self, buffer=None, scm_ifce=None, file_list=[]):
        cmd_result.ProblemReporter.__init__(self)
        # allow scm_ifce to be either an instance or a generator
        try:
            self._scm_ifce = scm_ifce()
        except:
            self._scm_ifce = scm_ifce
        self._file_list = file_list
        if not buffer:
            buffer = DiffTextBuffer()
        self._gtk_window = None
        gtksourceview.SourceView.__init__(self, buffer)
        fdesc = pango.FontDescription("mono, 10")
        self.modify_font(fdesc)
        self.set_margin(81)
        self.set_show_margin(True)
        context = self.get_pango_context()
        metrics = context.get_metrics(fdesc)
        width = pango.PIXELS(metrics.get_approximate_char_width() * 85)
        x, y = self.buffer_to_window_coords(gtk.TEXT_WINDOW_TEXT, width, width / 2)
        self.set_size_request(width, width / 2)
        self.set_cursor_visible(False)
        self.set_editable(False)
        self._action_group = gtk.ActionGroup("diff_text")
        self._ui_manager = gtk.UIManager()
        self._ui_manager.insert_action_group(self._action_group, -1)
        self._action_group.add_actions(
            [
                ("diff_save", gtk.STOCK_SAVE, "_Save", None,
                 "Save the diff to previously nominated file", self._save_acb),
                ("diff_save_as", gtk.STOCK_SAVE_AS, "Save _as", None,
                 "Save the diff to a nominated file", self._save_as_acb),
                ("diff_refresh", gtk.STOCK_REFRESH, "_Refresh", None,
                 "Refresh contents of the diff", self._refresh_acb),
            ])
        self.diff_text_merge_id = self._ui_manager.add_ui_from_string(DIFF_TEXT_UI_DESCR)
        self._save_file = None
        self.check_set_save_sensitive()
        self.set_contents()
    def _get_gtk_window(self):
        if not self._gtk_window:
            temp = self.get_parent()
            while temp:
                self._gtk_window = temp
                temp = temp.get_parent()
        return self._gtk_window
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
    def check_save_sensitive(self):
        return self._save_file is not None and os.path.exists(self._save_file)
    def check_set_save_sensitive(self):
        set_sensitive = self.check_save_sensitive()
        self._action_group.get_action("diff_save").set_sensitive(set_sensitive)
    def set_contents(self):
        res, diff_text, serr = self._scm_ifce.diff_files(self._file_list)
        self._report_any_problems((res, diff_text, serr))
        self.get_buffer().set_contents(diff_text)
    def _refresh_acb(self, action):
        self.set_contents()
    def _save_to_file(self):
        ok, msg = self.get_buffer().save_to_file(self._save_file)
        if not ok:
            self._report_any_problems((cmd_result.ERROR, "", msg))
        self.check_set_save_sensitive()
    def _save_acb(self, action):
        self._save_to_file()
    def _save_as_acb(self, action):
        dialog = gtk.FileChooserDialog("Save as ...", self._get_gtk_window(),
                                       gtk.FILE_CHOOSER_ACTION_SAVE,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        if self._save_file:
            dialog.set_current_folder(os.path.abspath(os.path.dirname(self._save_file)))
            dialog.et_current_name(os.path.abspath(os.path.basename(self._save_file)))
        else:
            dialog.set_current_folder(os.getcwd())
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self._save_file = dialog.get_filename()
            dialog.destroy()
            self._save_to_file()
        else:
            dialog.destroy()

class DiffTextDialog(gtk.Dialog):
    def __init__(self, parent, scm_ifce, file_list=[], modal=False):
        if modal or (parent and parent.get_modal()):
            flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
        else:
            flags = gtk.DIALOG_DESTROY_WITH_PARENT
        gtk.Dialog.__init__(self, "diff: %s" % os.getcwd(), parent, flags, ())
        self.diff_view = DiffTextView(scm_ifce=scm_ifce, file_list=file_list)
        self.vbox.pack_start(gutils.wrap_in_scrolled_window(self.diff_view))
        for action_name in ["diff_save", "diff_save_as", "diff_refresh"]:
            action = self.diff_view.get_action(action_name)
            button = gtk.Button(stock=action.get_property("stock-id"))
            action.connect_proxy(button)
            self.action_area.pack_start(button)
        self.add_buttons(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.connect("response", self._close_cb)
        self.show_all()
    def _close_cb(self, dialog, response_id):
        self.destroy()
