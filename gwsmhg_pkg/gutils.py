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

import gtk, os.path

def wrap_in_scrolled_window(widget, policy=(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC), with_frame=True, label=None):
    scrw = gtk.ScrolledWindow()
    scrw.set_policy(policy[0], policy[1])
    scrw.add(widget)
    if with_frame:
        frame = gtk.Frame(label)
        frame.add(scrw)
        frame.show_all()
        return frame
    else:
        scrw.show_all()
        return scrw

def ask_file_name(prompt, suggestion=None, existing=True, parent=None):
    if existing:
        mode = gtk.FILE_CHOOSER_ACTION_OPEN
        if suggestion and not os.path.exists(suggestion):
            suggestion = None
    else:
        mode = gtk.FILE_CHOOSER_ACTION_SAVE
    dialog = gtk.FileChooserDialog(prompt, parent, mode,
                                   (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                   gtk.STOCK_OK, gtk.RESPONSE_OK))
    dialog.set_default_response(gtk.RESPONSE_OK)
    if parent:
        dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
    else:
        dialog.set_position(gtk.WIN_POS_MOUSE)
    if suggestion:
        if os.path.isdir(suggestion):
            dialog.set_current_folder(suggestion)
        else:
            dirname, basename = os.path.split(suggestion)
            if dirname:
                dialog.set_current_folder(dirname)
            if basename:
                dialog.set_current_name(basename)
    response = dialog.run()
    if response == gtk.RESPONSE_OK:
        new_file_name = dialog.get_filename()
    else:
        new_file_name = None
    dialog.destroy()
    return new_file_name

def ask_question(question, parent=None, buttons=gtk.BUTTONS_OK_CANCEL):
    dialog = gtk.MessageDialog(parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            type=gtk.MESSAGE_QUESTION, buttons=buttons,
                            message_format=question)
    if parent:
        dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
    else:
        dialog.set_position(gtk.WIN_POS_MOUSE)
    response = dialog.run()
    dialog.destroy()
    return response

def ask_ok_cancel(question, parent=None):
   return ask_question(question, parent) == gtk.RESPONSE_OK

def ask_yes_no(question, parent=None):
   return ask_question(question, parent, gtk.BUTTONS_YES_NO) == gtk.RESPONSE_YES

def inform_user(msg, parent=None, problem_type=gtk.MESSAGE_ERROR):
    dialog = gtk.MessageDialog(parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            type=problem_type, buttons=gtk.BUTTONS_CLOSE,
                            message_format=msg)
    if parent:
        dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
    else:
        dialog.set_position(gtk.WIN_POS_MOUSE)
    response = dialog.run()
    dialog.destroy()

class PopupUser:
    def __init__(self):
        self._gtk_window = None
    def _get_gtk_window(self):
        if not self._gtk_window:
            temp = self.get_parent()
            while temp:
                self._gtk_window = temp
                temp = temp.get_parent()
        return self._gtk_window

class TooltipsUser:
    def __init__(self, tooltips=None):
        self._tooltips = tooltips
    def set_tooltips(self, tooltips):
        self._tooltips = tooltips
    def get_tooltips(self):
        return self._tooltips
    def enable_tooltips(self):
        if self._tooltips: self._tooltips.enable()
    def disable_tooltips(self):
        if self._tooltips: self._tooltips.disable()
    def set_tip(self, widget, tip_text, tip_text_private=None):
        if self._tooltips: self._tooltips.set_tip(widget, tip_text, tip_text_private)

class BusyIndicator:
    def __init__(self):
        pass
    def _show_busy(self):
        self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
        while gtk.events_pending():
            gtk.main_iteration()
    def _unshow_busy(self):
        self.window.set_cursor(None)

_KEYVAL_UP_ARROW = gtk.gdk.keyval_from_name('Up')
_KEYVAL_DOWN_ARROW = gtk.gdk.keyval_from_name('Down')

class EntryWithHistory(gtk.Entry):
    def __init__(self, max=0):
        gtk.Entry.__init__(self, max)
        self._history_list = []
        self._history_index = 0
        self._history_len = 0
        self._saved_text = ''
        self._key_press_cb_id = self.connect("key_press_event", self._key_press_cb)
    def _key_press_cb(self, widget, event):
        if event.keyval in [_KEYVAL_UP_ARROW, _KEYVAL_DOWN_ARROW]:
            if event.keyval == _KEYVAL_UP_ARROW:
                if self._history_index < self._history_len:
                    if self._history_index == 0:
                        self._saved_text = self.get_text()
                    self._history_index += 1
                    self.set_text(self._history_list[-self._history_index])
                    self.set_position(-1)
            elif event.keyval == _KEYVAL_DOWN_ARROW:
                if self._history_index > 0:
                    self._history_index -= 1
                    if self._history_index > 0:
                        self.set_text(self._history_list[-self._history_index])
                    else:
                        self.set_text(self._saved_text)
                    self.set_position(-1)
            return True
        else:
            return False
    def get_text_and_clear_to_history(self):
        text = self.get_text().rstrip()
        self.set_text("")
        self._history_index = 0
        # beware the empty command string
        if not text:
            return ""
        # don't save entries that start with white space
        if text[0] in [' ', '\t']:
            return text.lstrip()
        # no adjacent duplicate entries allowed
        if (self._history_len == 0) or (text != self._history_list[-1]):
            self._history_list.append(text)
            self._history_len = len(self._history_list)
        return text

