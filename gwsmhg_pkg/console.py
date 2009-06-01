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

import os, gtk, gtksourceview, pango
from gwsmhg_pkg import utils, cmd_result, gutils, utils
import time

class DummyConsoleLog:
    def start_cmd(self, cmd):
        print "%s: %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), cmd.rstrip())
    def append_stdout(self, msg):
        print msg
    def append_stderr(self, msg):
        print msg
    def end_cmd(self):
        if sout or serr:
            print (sout + serr).rstrip()
        print "%",
    def append_entry(self, msg):
        print msg.rstrip()
        print "%",

class ConsoleLogBuffer(gtksourceview.SourceBuffer):
    def __init__(self, view=None, table=None):
        self._view = view
        if not table:
            table = gtksourceview.SourceTagTable()
        gtksourceview.SourceBuffer.__init__(self, table=table)
        self.bold_tag = self.create_tag("BOLD", weight=pango.WEIGHT_BOLD, foreground="black", family="monospace")
        self.cmd_tag = self.create_tag("CMD", foreground="black", family="monospace")
        self.stdout_tag = self.create_tag("STDOUT", foreground="black", family="monospace")
        self.stderr_tag = self.create_tag("STDERR", foreground="#AA0000", family="monospace")
        self._eobuf = self.create_mark("eobuf", self.get_end_iter(), False)
        self.begin_not_undoable_action()
        self.set_text("")
        self._append_tagged_text("% ", self.bold_tag)
    def clear(self):
        self.end_not_undoable_action()
        self.set_text("")
        self._append_tagged_text("% ", self.bold_tag)
        self.begin_not_undoable_action()
    def _append_tagged_text(self, text, tag):
        iter = self.get_end_iter()
        assert iter is not None, "ConsoleLogBuffer"
        self.insert_with_tags(iter, text, tag)
        self._view and self._view.scroll_to_mark(self._eobuf, 0.001)
    def start_cmd(self, cmd):
        self._append_tagged_text("%s: " % time.strftime("%Y-%m-%d %H:%M:%S"), self.bold_tag)
        self._append_tagged_text(cmd + os.linesep, self.cmd_tag)
    def append_stdout(self, msg):
        self._append_tagged_text(msg, self.stdout_tag)
    def append_stderr(self, msg):
        self._append_tagged_text(msg, self.stderr_tag)
    def end_cmd(self):
        self._append_tagged_text("% ", self.bold_tag)
    def append_entry(self, msg):
        self._append_tagged_text("%s: " % time.strftime("%Y-%m-%d %H:%M:%S"), self.bold_tag)
        self._append_tagged_text(msg, self.cmd_tag)
        self._append_tagged_text(os.linesep + "% ", self.bold_tag)

class ConsoleLogView(gtksourceview.SourceView):
    def __init__(self, buffer, table=None):
        gtksourceview.SourceView.__init__(self, buffer)
        buffer._view = self
        fdesc = pango.FontDescription("mono, 10")
        self.modify_font(fdesc)
        self.set_margin(80)
        self.set_show_margin(True)
        context = self.get_pango_context()
        metrics = context.get_metrics(fdesc)
        width = pango.PIXELS(metrics.get_approximate_char_width() * 81)
        x, y = self.buffer_to_window_coords(gtk.TEXT_WINDOW_TEXT, width, width / 6)
        self.set_size_request(x, y)
        self.set_cursor_visible(False)
        self.set_editable(False)

CONSOLE_LOG_UI_DESCR = \
'''
<ui>
  <menubar name="console_log_menubar">
    <menu name="Console" action="menu_console">
        <menuitem action="console_log_clear"/>
    </menu>
  </menubar>
</ui>
'''

class ConsoleLog(gtk.VBox, cmd_result.ProblemReporter, utils.action_notifier,
                 gutils.BusyIndicatorUser, gutils.TooltipsUser):
    def __init__(self, busy_indicator, table=None, tooltips=None):
        gtk.VBox.__init__(self)
        cmd_result.ProblemReporter.__init__(self)
        gutils.BusyIndicatorUser.__init__(self, busy_indicator)
        gutils.TooltipsUser.__init__(self, tooltips)
        utils.action_notifier.__init__(self)
        self._buffer = ConsoleLogBuffer()
        self._view = ConsoleLogView(buffer=self._buffer)
        self._action_group = gtk.ActionGroup("console_log")
        self._ui_manager = gtk.UIManager()
        self._ui_manager.insert_action_group(self._action_group, -1)
        self._action_group.add_actions(
            [
                ("console_log_clear", gtk.STOCK_CLEAR, "_Clear", None,
                 "Clear the console log", self._clear_acb),
                ("menu_console", None, "_Console"),
            ])
        self.change_summary_merge_id = self._ui_manager.add_ui_from_string(CONSOLE_LOG_UI_DESCR)
        self._menubar = self._ui_manager.get_widget("/console_log_menubar")
        hbox = gtk.HBox()
        hbox.pack_start(self._menubar, expand=False)
        hbox.pack_start(gtk.Label("Run: "), expand=False)
        cmd_entry = gutils.EntryWithHistory()
        cmd_entry.connect("activate", self._cmd_entry_cb)
        hbox.pack_start(cmd_entry, expand=True, fill=True)
        self.pack_start(hbox, expand=False)
        self.pack_start(gutils.wrap_in_scrolled_window(self._view), expand=True, fill=True)
        self.show_all()
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
    def _clear_acb(self, action):
        self._buffer.clear()
    def start_cmd(self, cmd):
        self._buffer.start_cmd(cmd)
        while gtk.events_pending(): gtk.main_iteration()
    def append_stdout(self, msg):
        self._buffer.append_stdout(msg)
        while gtk.events_pending(): gtk.main_iteration()
    def append_stderr(self, msg):
        self._buffer.append_stderr(msg)
        while gtk.events_pending(): gtk.main_iteration()
    def end_cmd(self):
        self._buffer.end_cmd()
        while gtk.events_pending(): gtk.main_iteration()
    def append_entry(self, msg):
        self._buffer.append_entry(msg)
        while gtk.events_pending(): gtk.main_iteration()
    def _cmd_entry_cb(self, entry):
        self._show_busy()
        text = entry.get_text_and_clear_to_history()
        if text:
            result = utils.run_cmd_in_console(text, self)
        else:
            result = (cmd_result.OK, "", "")
        self._unshow_busy()
        self._report_any_problems(result)
        self._do_cmd_notification("manual_cmd")

