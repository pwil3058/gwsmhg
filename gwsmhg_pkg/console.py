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

import os, gtk, pango, time
from gwsmhg_pkg import dialogue, utils, cmd_result, gutils, ws_event
from gwsmhg_pkg import sourceview

class ConsoleLogBuffer(sourceview.SourceBuffer):
    def __init__(self, view=None, table=None):
        if not table:
            table = sourceview.SourceTagTable()
        sourceview.SourceBuffer.__init__(self, table=table)
        self._view = view
        self.bold_tag = self.create_tag("BOLD", weight=pango.WEIGHT_BOLD, foreground="black", family="monospace")
        self.cmd_tag = self.create_tag("CMD", foreground="black", family="monospace")
        self.stdout_tag = self.create_tag("STDOUT", foreground="black", family="monospace")
        self.stderr_tag = self.create_tag("STDERR", foreground="#AA0000", family="monospace")
        self.stdin_tag = self.create_tag("STDIN", foreground="#00AA00", family="monospace")
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
        model_iter = self.get_end_iter()
        assert model_iter is not None, "ConsoleLogBuffer"
        self.insert_with_tags(model_iter, text, tag)
        self._view and self._view.scroll_to_mark(self._eobuf, 0.001)
    def start_cmd(self, cmd):
        self._append_tagged_text("%s: " % time.strftime("%Y-%m-%d %H:%M:%S"), self.bold_tag)
        self._append_tagged_text(cmd + os.linesep, self.cmd_tag)
    def append_stdin(self, msg):
        self._append_tagged_text(msg, self.stdin_tag)
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

class ConsoleLogView(sourceview.SourceView):
    def __init__(self, text_buffer, _table=None):
        sourceview.SourceView.__init__(self, text_buffer)
        text_buffer._view = self
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

class ConsoleLog(gtk.VBox, dialogue.BusyIndicatorUser):
    def __init__(self, busy_indicator=None, runentry=False, _table=None):
        gtk.VBox.__init__(self)
        dialogue.BusyIndicatorUser.__init__(self, busy_indicator)
        self._buffer = ConsoleLogBuffer()
        self._view = ConsoleLogView(text_buffer=self._buffer)
        self._action_group = gtk.ActionGroup("console_log")
        self.ui_manager = gutils.UIManager()
        self.ui_manager.insert_action_group(self._action_group, -1)
        self._action_group.add_actions(
            [
                ("console_log_clear", gtk.STOCK_CLEAR, "_Clear", None,
                 "Clear the console log", self._clear_acb),
                ("menu_console", None, "_Console"),
            ])
        self.change_summary_merge_id = self.ui_manager.add_ui_from_string(CONSOLE_LOG_UI_DESCR)
        self._menubar = self.ui_manager.get_widget("/console_log_menubar")
        hbox = gtk.HBox()
        hbox.pack_start(self._menubar, expand=False)
        cmd_entry = gutils.EntryWithHistory()
        if runentry:
            hbox.pack_start(gtk.Label("Run: "), expand=False)
            cmd_entry.connect("activate", self._cmd_entry_cb)
        else:
            hbox.pack_start(gtk.Label(": hg "), expand=False)
            cmd_entry.connect("activate", self._hg_cmd_entry_cb)
        hbox.pack_start(cmd_entry, expand=True, fill=True)
        self.pack_start(hbox, expand=False)
        self.pack_start(gutils.wrap_in_scrolled_window(self._view), expand=True, fill=True)
        self.show_all()
    def get_action(self, action_name):
        for action_group in self.ui_manager.get_action_groups():
            action = action_group.get_action(action_name)
            if action:
                return action
        return None
    def _clear_acb(self, _action):
        self._buffer.clear()
    def start_cmd(self, cmd):
        self._buffer.start_cmd(cmd)
        while gtk.events_pending(): gtk.main_iteration()
    def append_stdin(self, msg):
        self._buffer.append_stdin(msg)
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
        text = entry.get_text_and_clear_to_history()
        if not text:
            return
        self.show_busy()
        pre_dir = os.getcwd()
        result = utils.run_cmd_in_console(text, self)
        self.unshow_busy()
        dialogue.report_any_problems(result)
        if pre_dir == os.getcwd():
            ws_event.notify_events(ws_event.ALL_BUT_CHANGE_WD)
        else:
            from gwsmhg_pkg import ifce
            ifce.chdir()
    def _hg_cmd_entry_cb(self, entry):
        text = entry.get_text_and_clear_to_history()
        if not text:
            return
        self.show_busy()
        result = utils.run_cmd_in_console("hg " + text, self)
        self.unshow_busy()
        dialogue.report_any_problems(result)
        ws_event.notify_events(ws_event.ALL_BUT_CHANGE_WD)
