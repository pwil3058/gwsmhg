# -*- python -*-

### Copyright (C) 2005 Peter Williams <peter_ono@users.sourceforge.net>

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

import gtk, os
from gwsmhg_pkg import cmd_result, icons, ws_event

main_window = None

def init(window):
    global main_window
    main_window = window

class BusyIndicator:
    def __init__(self):
        pass
    def show_busy(self):
        if self.window:
            self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
            while gtk.events_pending():
                gtk.main_iteration()
    def unshow_busy(self):
        if self.window:
            self.window.set_cursor(None)

class BusyIndicatorUser:
    def __init__(self, busy_indicator):
        if busy_indicator:
            self._busy_indicator = busy_indicator
        else:
            self._busy_indicator = main_window
    def show_busy(self):
        self._busy_indicator.show_busy()
    def unshow_busy(self):
        self._busy_indicator.unshow_busy()

class Dialog(gtk.Dialog, BusyIndicator):
    def __init__(self, title=None, parent=None, flags=0, buttons=None):
        if not parent:
            parent = main_window
        gtk.Dialog.__init__(self, title=title, parent=parent, flags=flags, buttons=buttons)
        if not parent:
            self.set_icon_from_file(icons.app_icon_file)
        BusyIndicator.__init__(self)
    def report_any_problems(self, result):
        report_any_problems(result, self)
    def inform_user(self, msg):
        inform_user(msg, parent=self)
    def warn_user(self, msg):
        warn_user(msg, parent=self)
    def alert_user(self, msg):
        alert_user(msg, parent=self)

class AmodalDialog(Dialog, ws_event.Listener):
    def __init__(self, title=None, parent=None, flags=0, buttons=None):
        flags &= ~gtk.DIALOG_MODAL
        Dialog.__init__(self, title=title, parent=parent, flags=flags, buttons=buttons)
        ws_event.Listener.__init__(self)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_NORMAL)
        self.add_notification_cb(ws_event.CHANGE_WD, self._change_wd_cb)
    def _change_wd_cb(self, arg=None):
        self.destroy()

class MessageDialog(gtk.MessageDialog):
    def __init__(self, parent=None, flags=0, type=gtk.MESSAGE_INFO, buttons=gtk.BUTTONS_NONE, message_format=None):
        if not parent:
            parent = main_window
        gtk.MessageDialog.__init__(self, parent=parent, flags=flags, type=type, buttons=buttons, message_format=message_format)

class FileChooserDialog(gtk.FileChooserDialog):
    def __init__(self, title=None, parent=None, action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=None, backend=None):
        if not parent:
            parent = main_window
        gtk.FileChooserDialog.__init__(self, title=title, parent=parent, action=action, buttons=buttons, backend=backend)

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

class QuestionDialog(Dialog):
    def __init__(self, title=None, parent=None, flags=0, buttons=None, question=""):
        Dialog.__init__(self, title=title, parent=parent, flags=flags, buttons=buttons)
        hbox = gtk.HBox()
        self.vbox.add(hbox)
        hbox.show()
        self.image = gtk.Image()
        self.image.set_from_stock(gtk.STOCK_DIALOG_QUESTION, gtk.ICON_SIZE_DIALOG)
        hbox.pack_start(self.image, expand=False)
        self.image.show()
        self.tv = gtk.TextView()
        self.tv.set_cursor_visible(False)
        self.tv.set_editable(False)
        self.tv.set_size_request(320, 80)
        self.tv.show()
        self.tv.get_buffer().set_text(question)
        hbox.add(wrap_in_scrolled_window(self.tv))
    def set_question(self, question):
        self.tv.get_buffer().set_text(question)

def ask_question(question, parent=None,
                 buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                          gtk.STOCK_OK, gtk.RESPONSE_OK)):
    dialog = QuestionDialog(parent=parent,
                            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                            buttons=buttons, question=question)
    response = dialog.run()
    dialog.destroy()
    return response

def ask_ok_cancel(question, parent=None):
    return ask_question(question, parent) == gtk.RESPONSE_OK

def ask_yes_no(question, parent=None):
    buttons = (gtk.STOCK_NO, gtk.RESPONSE_NO, gtk.STOCK_YES, gtk.RESPONSE_YES)
    return ask_question(question, parent, buttons) == gtk.RESPONSE_YES

def confirm_list_action(list, question, parent=None):
    return ask_ok_cancel('\n'.join(list + ['\n', question]), parent)

RESPONSE_SKIP = 1
RESPONSE_SKIP_ALL = 2

RESPONSE_FORCE = 3
RESPONSE_REFRESH = 4
RESPONSE_RECOVER = 5
RESPONSE_RENAME = 6
RESPONSE_DISCARD = 7
RESPONSE_EDIT = 8
RESPONSE_MERGE = 9

def ask_force_refresh_or_cancel(question, flags=cmd_result.SUGGEST_ALL, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    if flags & cmd_result.SUGGEST_REFRESH:
        buttons += ("_Refresh and Retry", RESPONSE_REFRESH)
    if flags & cmd_result.SUGGEST_FORCE:
        buttons += ("_Force", RESPONSE_FORCE)
    return ask_question(question, parent, buttons)

def ask_force_or_cancel(question, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, "_Force", RESPONSE_FORCE)
    return ask_question(question, parent, buttons)

def ask_merge_discard_or_cancel(question, flags=cmd_result.SUGGEST_ALL, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    if flags & cmd_result.SUGGEST_MERGE:
        buttons += ("_Merge", RESPONSE_MERGE)
    if flags & cmd_result.SUGGEST_DISCARD:
        buttons += ("_Discard Changes", RESPONSE_DISCARD)
    return ask_question(question, parent, buttons)

def ask_recover_or_cancel(question, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, "_Recover", RESPONSE_RECOVER)
    return ask_question(question, parent, buttons)

def ask_edit_force_or_cancel(question, flags=cmd_result.SUGGEST_ALL, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    if flags & cmd_result.SUGGEST_EDIT:
        buttons += ("_Edit", RESPONSE_EDIT)
    if flags & cmd_result.SUGGEST_FORCE:
        buttons += ("_Force", RESPONSE_FORCE)
    return ask_question(question, parent, buttons)

def ask_rename_force_or_cancel(question, flags=cmd_result.SUGGEST_ALL, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    if flags & cmd_result.SUGGEST_RENAME:
        buttons += ("_Rename", RESPONSE_RENAME)
    if flags & cmd_result.SUGGEST_FORCE:
        buttons += ("_Force", RESPONSE_FORCE)
    return ask_question(question, parent, buttons)

def ask_rename_force_or_skip(question, flags=cmd_result.SUGGEST_ALL, parent=None):
    buttons = ()
    if flags & cmd_result.SUGGEST_RENAME:
        buttons += ("_Rename", RESPONSE_RENAME)
    if flags & cmd_result.SUGGEST_FORCE:
        buttons += ("_Force", RESPONSE_FORCE)
    buttons += ("_Skip", RESPONSE_SKIP, "Skip _All", RESPONSE_SKIP_ALL)
    return ask_question(question, parent, buttons)

def ask_file_name(prompt, suggestion=None, existing=True, parent=None):
    if existing:
        mode = gtk.FILE_CHOOSER_ACTION_OPEN
        if suggestion and not os.path.exists(suggestion):
            suggestion = None
    else:
        mode = gtk.FILE_CHOOSER_ACTION_SAVE
    dialog = FileChooserDialog(prompt, parent, mode,
                               (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                gtk.STOCK_OK, gtk.RESPONSE_OK))
    dialog.set_default_response(gtk.RESPONSE_OK)
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

def ask_dir_name(prompt, suggestion=None, existing=True, parent=None):
    if existing:
        mode = gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER
        if suggestion and not os.path.exists(suggestion):
            suggestion = None
    else:
        mode = gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER
    dialog = FileChooserDialog(prompt, parent, mode,
                               (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                gtk.STOCK_OK, gtk.RESPONSE_OK))
    dialog.set_default_response(gtk.RESPONSE_OK)
    if suggestion:
        if os.path.isdir(suggestion):
            dialog.set_current_folder(suggestion)
        else:
            dirname = os.path.dirname(suggestion)
            if dirname:
                dialog.set_current_folder(dirname)
    response = dialog.run()
    if response == gtk.RESPONSE_OK:
        new_dir_name = dialog.get_filename()
    else:
        new_dir_name = None
    dialog.destroy()
    return new_dir_name

def inform_user(msg, parent=None, problem_type=gtk.MESSAGE_INFO):
    dialog = MessageDialog(parent=parent,
                           flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                           type=problem_type, buttons=gtk.BUTTONS_CLOSE,
                           message_format=msg)
    dialog.run()
    dialog.destroy()

def warn_user(msg, parent=None):
    inform_user(msg, parent=parent, problem_type=gtk.MESSAGE_WARNING)

def alert_user(msg, parent=None):
    inform_user(msg, parent=parent, problem_type=gtk.MESSAGE_ERROR)

def report_any_problems(result, parent=None):
    if cmd_result.is_ok(result[0]):
        return
    elif cmd_result.is_error(result[0]):
        problem_type = gtk.MESSAGE_ERROR
    else:
        problem_type = gtk.MESSAGE_WARNING
    inform_user(os.linesep.join(result[1:]), parent, problem_type)

report_request_msg = \
'''
Please report this problem by either:
  submitting a bug report at <https://sourceforge.net/tracker/?group_id=258223&atid=1127211>
or:
  e-mailing <gwsmhg-discussion@lists.sourceforge.net>
and including a copy of the details below this message.

Thank you.
'''

def report_exception(exc_data, parent=None):
    import traceback
    msg = ''.join(traceback.format_exception(exc_data[0], exc_data[1], exc_data[2]))
    dialog = MessageDialog(parent=parent,
                           flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                           type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_CLOSE,
                           message_format=report_request_msg)
    dialog.set_title('gwsmhg: Unexpected Exception')
    dialog.format_secondary_text(msg)
    dialog.run()
    dialog.destroy()

class CancelOKDialog(Dialog):
    def __init__(self, title=None, parent=None):
        flags = gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK)
        Dialog.__init__(self, title, parent, flags, buttons)

class ReadTextDialog(CancelOKDialog):
    def __init__(self, title=None, prompt=None, suggestion="", parent=None):
        CancelOKDialog.__init__(self, title, parent) 
        self.hbox = gtk.HBox()
        self.vbox.add(self.hbox)
        self.hbox.show()
        if prompt:
            self.hbox.pack_start(gtk.Label(prompt), fill=False, expand=False)
        self.entry = gtk.Entry()
        self.entry.set_width_chars(32)
        self.entry.set_text(suggestion)
        self.hbox.pack_start(self.entry)
        self.show_all()

class ReadTextAndToggleDialog(ReadTextDialog):
    def __init__(self, title=None, prompt=None, suggestion="", toggle_prompt=None, toggle_state=False, parent=None):
        ReadTextDialog.__init__(self, title=title, prompt=prompt, suggestion=suggestion, parent=parent)
        self.toggle = gtk.CheckButton(label=toggle_prompt)
        self.toggle.set_active(toggle_state)
        self.hbox.pack_start(self.toggle)
        self.show_all()

def get_modified_string(title, prompt, string):
    dialog = ReadTextDialog(title, prompt, string)
    if dialog.run() == gtk.RESPONSE_OK:
        string = dialog.entry.get_text()
    dialog.destroy()
    return string

