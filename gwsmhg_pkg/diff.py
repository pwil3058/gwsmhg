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

import os, gtk, gtksourceview, pango, re
from gwsmhg_pkg import utils, cmd_result, gutils, icons

STATES = [gtk.STATE_NORMAL, gtk.STATE_ACTIVE, gtk.STATE_PRELIGHT, gtk.STATE_PRELIGHT, gtk.STATE_INSENSITIVE]

class tws_line_count_display(gtk.HBox):
    def __init__(self):
        gtk.HBox.__init__(self)
        self.pack_start(gtk.Label("Added TWS lines:"), expand=False, fill=False)
        self._entry = gtk.Entry()
        self._entry.set_width_chars(1)
        self._entry.set_text(str(0))
        self._entry.set_editable(False)
        self.pack_start(self._entry, expand=False, fill=False)
        self.show_all()
    def set_value(self, val):
        sval = str(val)
        self._entry.set_width_chars(len(sval))
        self._entry.set_text(sval)
        if val:
            for state in STATES:
                self._entry.modify_base(state, gtk.gdk.Color("#FF0000"))
        else:
            for state in STATES:
                self._entry.modify_base(state, gtk.gdk.Color("#00FF00"))

class DiffTextBuffer(gtksourceview.SourceBuffer, cmd_result.ProblemReporter):
    def __init__(self, scm_ifce, file_list=[], fromrev=None, torev=None, table=None):
        cmd_result.ProblemReporter.__init__(self)
        if not table:
            table = gtksourceview.SourceTagTable()
        gtksourceview.SourceBuffer.__init__(self, table)
        self._fromrev = fromrev
        self._torev = torev
        self._file_list = file_list
        self._scm_ifce = scm_ifce
        self._tws_change_cbs = []
        self.tws_check = re.compile('^(\+.*\S)(\s+\n)$')
        self.tws_list = []
        self.tws_index = 0
        self._action_group = gtk.ActionGroup("diff_text")
        self._action_group.add_actions(
            [
                ("diff_save", gtk.STOCK_SAVE, "_Save", None,
                 "Save the diff to previously nominated file", self._save_acb),
                ("diff_save_as", gtk.STOCK_SAVE_AS, "Save _as", None,
                 "Save the diff to a nominated file", self._save_as_acb),
                ("diff_refresh", gtk.STOCK_REFRESH, "_Refresh", None,
                 "Refresh contents of the diff", self._refresh_acb),
            ])
        if not torev:
            self.a_name_list = ["diff_save", "diff_save_as", "diff_refresh"]
        else:
            # the diff between two revs is immutable so refresh is redundant
            self.a_name_list = ["diff_save", "diff_save_as"]
        self.diff_buttons = gutils.ActionButtonList([self._action_group], self.a_name_list)
        self._save_file = None
        self.check_set_save_sensitive()
        self.tws_display = tws_line_count_display()
        self.index_tag = self.create_tag("INDEX", weight=pango.WEIGHT_BOLD, foreground="#0000AA", family="monospace")
        self.sep_tag = self.create_tag("SEP", weight=pango.WEIGHT_BOLD, foreground="#0000AA", family="monospace")
        self.minus_tag = self.create_tag("MINUS", foreground="#AA0000", family="monospace")
        self.lab_tag = self.create_tag("LAB", foreground="#AA0000", family="monospace")
        self.plus_tag = self.create_tag("PLUS", foreground="#006600", family="monospace")
        self.added_tws_tag = self.create_tag("ADDED_TWS", background="#006600", family="monospace")
        self.star_tag = self.create_tag("STAR", foreground="#006600", family="monospace")
        self.rab_tag = self.create_tag("RAB", foreground="#006600", family="monospace")
        self.change_tag = self.create_tag("CHANGED", foreground="#AA6600", family="monospace")
        self.stats_tag = self.create_tag("STATS", foreground="#AA00AA", family="monospace")
        self.func_tag = self.create_tag("FUNC", foreground="#00AAAA", family="monospace")
        self.unchanged_tag = self.create_tag("UNCHANGED", foreground="black", family="monospace")
    def register_tws_change_cb(self, func):
        self._tws_change_cbs.append(func)
    def _append_tagged_text(self, text, tag):
        self.insert_with_tags(self.get_end_iter(), text, tag)
    def _append_patch_line(self, line):
        fc = line[0]
        if fc == " ":
            self._append_tagged_text(line, self.unchanged_tag)
        elif fc == "+":
            match = self.tws_check.match(line)
            if match:
                self._append_tagged_text(match.group(1), self.plus_tag)
                self._append_tagged_text(match.group(2), self.added_tws_tag)
                return len(match.group(1))
            else:
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
        return 0
    def set_contents(self):
        res, text, serr = self._scm_ifce.get_diff_for_files(self._file_list, self._fromrev, self._torev)
        self._report_any_problems((res, text, serr))
        old_count = len(self.tws_list)
        self.begin_not_undoable_action()
        self.set_text("")
        self.tws_list = []
        line_no = 0
        for line in text.splitlines():
            offset = self._append_patch_line(line + os.linesep)
            if offset:
                self.tws_list.append((line_no, offset - 2))
            line_no += 1
        self.end_not_undoable_action()
        new_count = len(self.tws_list)
        self.tws_display.set_value(new_count)
        if not (new_count == old_count):
            for func in self._tws_change_cbs:
                func(new_count)
    def _tws_index_iter(self):
        pos = self.tws_list[self.tws_index]
        iter = self.get_iter_at_line_offset(pos[0], pos[1])
        self.place_cursor(iter)
        return iter
    def get_tws_first_iter(self):
        self.tws_index = 0
        return self._tws_index_iter()
    def get_tws_prev_iter(self):
        if self.tws_index:
            self.tws_index -= 1
        return self._tws_index_iter()
    def get_tws_next_iter(self):
        self.tws_index += 1
        if self.tws_index >= len(self.tws_list):
            self.tws_index = len(self.tws_list) - 1
        return self._tws_index_iter()
    def get_tws_last_iter(self):
        self.tws_index = len(self.tws_list) - 1
        return self._tws_index_iter()
    def _save_to_file(self):
        try:
            file = open(self._save_file, 'w')
        except IOError, (errno, strerror):
            self._report_any_problems((cmd_result.ERROR, "", strerror))
            self.check_set_save_sensitive()
            return
        text = self.get_text(self.get_start_iter(), self.get_end_iter())
        file.write(text)
        file.close()
        self.check_set_save_sensitive()
    def check_save_sensitive(self):
        return self._save_file is not None and os.path.exists(self._save_file)
    def check_set_save_sensitive(self):
        set_sensitive = self.check_save_sensitive()
        self._action_group.get_action("diff_save").set_sensitive(set_sensitive)
    def _refresh_acb(self, action):
        self.set_contents()
    def _save_acb(self, action):
        self._save_to_file()
    def _save_as_acb(self, action):
        if self._save_file:
            suggestion = self._save_file
        else:
            suggestion = os.getcwd()
        self._save_file = gutils.ask_file_name("Save as ...", suggestion=suggestion, existing=False)
        self._save_to_file()
    def get_action_button_box(self):
        return gutils.ActionHButtonBox([self._action_group], action_name_list=self.a_name_list)

class DiffTextView(gtksourceview.SourceView):
    def __init__(self, scm_ifce, file_list=[], fromrev=None, torev=None):
        self._file_list = file_list
        buffer = DiffTextBuffer(scm_ifce, file_list, fromrev=fromrev, torev=torev)
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
        self._action_group = gtk.ActionGroup("diff_tws_nav")
        self._action_group.add_actions(
            [
                ("tws_nav_first", gtk.STOCK_GOTO_TOP, "_First", None,
                 "Scroll to first line with added trailing white space",
                 self._tws_nav_first_acb),
                ("tws_nav_prev", gtk.STOCK_GO_UP, "_Prev", None,
                 "Scroll to previous line with added trailing white space",
                 self._tws_nav_prev_acb),
                ("tws_nav_next", gtk.STOCK_GO_DOWN, "_Next", None,
                 "Scroll to next line with added trailing white space",
                 self._tws_nav_next_acb),
                ("tws_nav_last", gtk.STOCK_GOTO_BOTTOM, "_Last", None,
                 "Scroll to last line with added trailing white space",
                 self._tws_nav_last_acb),
            ])
        self.tws_nav_buttonbox = gutils.ActionHButtonBox([self._action_group],
            ["tws_nav_first", "tws_nav_prev", "tws_nav_next", "tws_nav_last"])
    def _tws_nav_first_acb(self, action):
        self.scroll_to_iter(self.get_buffer().get_tws_first_iter(), 0.01)
        iter = self.get_buffer().get_tws_first_iter()
        self.scroll_to_iter(iter, 0.01)
    def _tws_nav_prev_acb(self, action):
        self.scroll_to_iter(self.get_buffer().get_tws_prev_iter(), 0.01)
    def _tws_nav_next_acb(self, action):
        self.scroll_to_iter(self.get_buffer().get_tws_next_iter(), 0.01)
    def _tws_nav_last_acb(self, action):
        self.scroll_to_iter(self.get_buffer().get_tws_last_iter(), 0.01)

class DiffTextWidget(gtk.VBox):
    def __init__(self, parent, scm_ifce, file_list=[], fromrev=None, torev=None):
        gtk.VBox.__init__(self)
        self.diff_view = DiffTextView(scm_ifce=scm_ifce, file_list=file_list, fromrev=fromrev, torev=torev)
        self.pack_start(gutils.wrap_in_scrolled_window(self.diff_view))
        self._tws_nav_buttons_packed = False
        buffer = self.diff_view.get_buffer()
        buffer.register_tws_change_cb(self._tws_change_cb)
        buffer.set_contents()
        self.show_all()
    def _tws_change_cb(self, new_count):
        if self._tws_nav_buttons_packed and not new_count:
            self.remove(self.diff_view.tws_nav_buttonbox)
            self.diff_view.set_cursor_visible(False)
            self._tws_nav_buttons_packed = False
        elif not self._tws_nav_buttons_packed and new_count:
            self.pack_start(self.diff_view.tws_nav_buttonbox, expand=False, fill=True)
            self.diff_view.set_cursor_visible(True)
            self._tws_nav_buttons_packed = True

class DiffTextDialog(gtk.Dialog):
    def __init__(self, parent, scm_ifce, file_list=[], fromrev=None, torev=None, modal=False):
        if modal or (parent and parent.get_modal()):
            flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
        else:
            flags = gtk.DIALOG_DESTROY_WITH_PARENT
        title = "diff: %s" % utils.path_rel_home(os.getcwd())
        mutable = torev is None
        if fromrev:
            parents = [fromrev]
            if torev:
                title += " REV[%s] -> REV[%s]" % (str(fromrev), str(torev))
            else:
                title += " REV[%s] -> []" % (str(fromrev))
        elif torev:
            res, parents, serr = scm_ifce.get_parents(torev)
            if len(parents) == 1:
                title += " REV[%s] -> REV[%s]" % (str(parents[0]), str(torev))
            else:
                title += " * -> [%s]" % (str(torev))
        else:
            res, parents, serr = scm_ifce.get_parents()
            if len(parents) == 1:
                title += " REV[%s] -> []" % (str(parents[0]))
            else:
                title += " * -> []"
        gtk.Dialog.__init__(self, title, parent, flags, ())
        if len(parents) > 1:
            nb = gtk.Notebook()
            for parent in parents:
                vbox = gtk.VBox()
                dtw = DiffTextWidget(self, scm_ifce, file_list, fromrev=parent, torev=torev)
                vbox.pack_start(dtw)
                hbox = gtk.HBox()
                tws_display = dtw.diff_view.get_buffer().tws_display
                hbox.pack_start(tws_display, expand=False, fill=False)
                abb = dtw.diff_view.get_buffer().get_action_button_box()
                hbox.pack_start(abb, expand=False, fill=False)
                vbox.pack_start(hbox, expand=False, fill=False)
                tab_label = gtk.Label("REV[%s]" % str(parent))
                nb.append_page(vbox,tab_label=tab_label)
            self.vbox.add(nb)
        else:
            dtw = DiffTextWidget(self, scm_ifce, file_list, fromrev=parents[0], torev=torev)
            self.vbox.pack_start(dtw)
            tws_display = dtw.diff_view.get_buffer().tws_display
            self.action_area.pack_end(tws_display, expand=False, fill=False)
            for button in dtw.diff_view.get_buffer().diff_buttons.list:
                self.action_area.pack_start(button)
        self.add_buttons(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.connect("response", self._close_cb)
        self.show_all()
    def _close_cb(self, dialog, response_id):
        self.destroy()

