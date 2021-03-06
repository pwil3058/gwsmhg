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
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import os

import gtk

from . import cmd_result
from . import config_data

from . import icons
from . import ws_event
from . import gutils

main_window = None

def show_busy():
    if main_window is not None:
        main_window.show_busy()

def unshow_busy():
    if main_window is not None:
        main_window.unshow_busy()

def is_busy():
    return main_window is None or main_window.is_busy

def init(window):
    global main_window
    main_window = window

class BusyIndicator:
    def __init__(self, parent=None):
        self.parent_indicator = parent
        self._count = 0
    def show_busy(self):
        if self.parent:
            self.parent.show_busy()
        self._count += 1
        if self._count == 1 and self.window:
            self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
            while gtk.events_pending():
                gtk.main_iteration()
    def unshow_busy(self):
        if self.parent:
            self.parent.unshow_busy()
        self._count -= 1
        assert self._count >= 0
        if self._count == 0 and self.window:
            self.window.set_cursor(None)
    @property
    def is_busy(self):
        return self._count > 0

class BusyIndicatorUser:
    def __init__(self, busy_indicator=None):
        self._busy_indicator = busy_indicator
    def show_busy(self):
        if self._busy_indicator is not None:
            self._busy_indicator.show_busy()
        else:
            show_busy()
    def unshow_busy(self):
        if self._busy_indicator is not None:
            self._busy_indicator.unshow_busy()
        else:
            unshow_busy()
    def set_busy_indicator(self, busy_indicator=None):
        self._busy_indicator = busy_indicator

class Dialog(gtk.Dialog, BusyIndicator):
    def __init__(self, title=None, parent=None, flags=0, buttons=None):
        if not parent:
            parent = main_window
        gtk.Dialog.__init__(self, title=title, parent=parent, flags=flags, buttons=buttons)
        if not parent:
            self.set_icon_from_file(icons.APP_ICON_FILE)
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
        self.tview = gtk.TextView()
        self.tview.set_cursor_visible(False)
        self.tview.set_editable(False)
        self.tview.set_size_request(320, 80)
        self.tview.show()
        self.tview.get_buffer().set_text(question)
        hbox.add(gutils.wrap_in_scrolled_window(self.tview))
    def set_question(self, question):
        self.tview.get_buffer().set_text(question)

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

def confirm_list_action(alist, question, parent=None):
    return ask_ok_cancel('\n'.join(alist + ['\n', question]), parent)

class Response(object):
    SKIP = 1
    SKIP_ALL = 2
    FORCE = 3
    REFRESH = 4
    RECOVER = 5
    RENAME = 6
    DISCARD = 7
    EDIT = 8
    MERGE = 9
    OVERWRITE = 10

def _form_question(result, clarification):
    if clarification:
        return '\n'.join(list(result[1:]) + [clarification])
    else:
        return '\n'.join(result[1:])

def ask_force_refresh_or_cancel(result, clarification=None, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    if result.ecode & cmd_result.SUGGEST_REFRESH:
        buttons += (_('_Refresh and Retry'), Response.REFRESH)
    if result.ecode & cmd_result.SUGGEST_FORCE:
        buttons += (_('_Force'), Response.FORCE)
    question = _form_question(result, clarification)
    return ask_question(question, parent, buttons)

def ask_force_or_cancel(result, clarification=None, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, _('_Force'), Response.FORCE)
    question = _form_question(result, clarification)
    return ask_question(question, parent, buttons)

def ask_force_skip_or_cancel(result, clarification=None, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, _('_Skip'), Response.SKIP, _('_Force'), Response.FORCE)
    question = _form_question(result, clarification)
    return ask_question(question, parent, buttons)

def ask_merge_discard_or_cancel(result, clarification=None, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    if result.ecode & cmd_result.SUGGEST_MERGE:
        buttons += (_('_Merge'), Response.MERGE)
    if result.ecode & cmd_result.SUGGEST_DISCARD:
        buttons += (_('_Discard Changes'), Response.DISCARD)
    question = _form_question(result, clarification)
    return ask_question(question, parent, buttons)

def ask_recover_or_cancel(result, clarification=None, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, _('_Recover'), Response.RECOVER)
    question = _form_question(result, clarification)
    return ask_question(question, parent, buttons)

def ask_edit_force_or_cancel(result, clarification=None, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    if result.ecode & cmd_result.SUGGEST_EDIT:
        buttons += (_('_Edit'), Response.EDIT)
    if result.ecode & cmd_result.SUGGEST_FORCE:
        buttons += (_('_Force'), Response.FORCE)
    question = _form_question(result, clarification)
    return ask_question(question, parent, buttons)

def ask_rename_force_or_cancel(result, clarification=None, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    if result.ecode & cmd_result.SUGGEST_RENAME:
        buttons += (_('_Rename'), Response.RENAME)
    if result.ecode & cmd_result.SUGGEST_FORCE:
        buttons += (_('_Force'), Response.FORCE)
    question = _form_question(result, clarification)
    return ask_question(question, parent, buttons)

def ask_rename_force_or_skip(result, clarification=None, parent=None):
    buttons = ()
    if result.ecode & cmd_result.SUGGEST_RENAME:
        buttons += (_('_Rename'), Response.RENAME)
    if result.ecode & cmd_result.SUGGEST_FORCE:
        buttons += (_('_Force'), Response.FORCE)
    buttons += (_('_Skip'), Response.SKIP, _('Skip _All'), Response.SKIP_ALL)
    question = _form_question(result, clarification)
    return ask_question(question, parent, buttons)

def ask_rename_overwrite_or_cancel(result, clarification=None, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    if result.ecode & cmd_result.SUGGEST_RENAME:
        buttons += (_('_Rename'), Response.RENAME)
    if result.ecode & cmd_result.SUGGEST_OVERWRITE:
        buttons += (_('_Overwrite'), Response.OVERWRITE)
    question = _form_question(result, clarification)
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
            else:
                dialog.set_current_folder(os.getcwd())
            if basename:
                dialog.set_current_name(basename)
    else:
        dialog.set_current_folder(os.getcwd())
    response = dialog.run()
    if response == gtk.RESPONSE_OK:
        new_file_name = os.path.relpath(dialog.get_filename())
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
        new_dir_name = os.path.relpath(dialog.get_filename())
    else:
        new_dir_name = None
    dialog.destroy()
    return new_dir_name

def ask_uri_name(prompt, suggestion=None, parent=None):
    if suggestion and not os.path.exists(suggestion):
        suggestion = None
    dialog = FileChooserDialog(prompt, parent, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                               (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                gtk.STOCK_OK, gtk.RESPONSE_OK))
    dialog.set_default_response(gtk.RESPONSE_OK)
    dialog.set_local_only(False)
    if suggestion:
        if os.path.isdir(suggestion):
            dialog.set_current_folder(suggestion)
        else:
            dirname = os.path.dirname(suggestion)
            if dirname:
                dialog.set_current_folder(dirname)
    response = dialog.run()
    if response == gtk.RESPONSE_OK:
        uri = os.path.relpath(dialog.get_uri())
    else:
        uri = None
    dialog.destroy()
    return uri

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
    if cmd_result.is_ok(result):
        return
    elif cmd_result.is_warning(result):
        problem_type = gtk.MESSAGE_WARNING
    else:
        problem_type = gtk.MESSAGE_ERROR
    inform_user(os.linesep.join(result[1:]), parent, problem_type)

def report_failure(failure, parent=None):
    result = failure.result
    if result.ecode != 0:
        inform_user(os.linesep.join(result[1:]), parent, gtk.MESSAGE_ERROR)

_REPORT_REQUEST_MSG = \
_('''
Please report this problem by either:
  submitting a bug report at <https://sourceforge.net/tracker/?group_id=258223&amp;atid=1127211>
or:
  e-mailing <gwsmhg-discussion@lists.sourceforge.net>
and including a copy of the details below this message.

Thank you.
''')

def report_exception(exc_data, parent=None):
    import traceback
    msg = ''.join(traceback.format_exception(exc_data[0], exc_data[1], exc_data[2]))
    dialog = MessageDialog(parent=parent,
                           flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                           type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_CLOSE,
                           message_format=_REPORT_REQUEST_MSG)
    dialog.set_title(_(config_data.APP_NAME + ": Unexpected Exception"))
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
