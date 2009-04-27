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

import gtk, os.path, gobject, cmd_result

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

def ask_dir_name(prompt, suggestion=None, existing=True, parent=None):
    if existing:
        mode = gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER
        if suggestion and not os.path.exists(suggestion):
            suggestion = None
    else:
        mode = gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER
    dialog = gtk.FileChooserDialog(prompt, parent, mode,
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

class QuestionDialog(gtk.Dialog):
    def __init__(self, title=None, parent=None, flags=0, buttons=None, question=""):
        try:
            gtk.Dialog.__init__(self, title, parent, flags, buttons)
        except:
            parent=None
            gtk.Dialog.__init__(self, title, parent, flags, buttons)
        if parent is None:
            self.set_position(gtk.WIN_POS_MOUSE)
        else:
            self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
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

FORCE = 1
REFRESH = 2
RECOVER = 3
EDIT = 4
SKIP = 5
SKIP_ALL = 6

def ask_force_refresh_or_cancel(question, flags, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
    if flags & cmd_result.SUGGEST_REFRESH:
        buttons += ("_Refresh and Retry", REFRESH)
    if flags & cmd_result.SUGGEST_FORCE:
        buttons += ("_Force", FORCE)
    return ask_question(question, parent, buttons)

def ask_recover_or_cancel(question, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, "_Recover", RECOVER)
    return ask_question(question, parent, buttons)

def ask_edit_force_or_cancel(question, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, "_Edit", EDIT, "_Force", FORCE)
    return ask_question(question, parent, buttons)

def ask_rename_force_or_cancel(question, parent=None):
    buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, "_Rename", EDIT, "_Force", FORCE)
    return ask_question(question, parent, buttons)

def ask_rename_force_or_skip(question, parent=None):
    buttons = ("_Rename", EDIT, "_Force", FORCE, "_Skip", SKIP, "Skip _All", SKIP_ALL)
    return ask_question(question, parent, buttons)

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

class ReadTextDialog(gtk.Dialog):
    def __init__(self, title=None, prompt=None, suggestion="", parent=None):
        flags = gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK)
        try:
            gtk.Dialog.__init__(self, title, parent, flags, buttons)
        except:
            parent=None
            gtk.Dialog.__init__(self, title, parent, flags, buttons)
        if parent is None:
            self.set_position(gtk.WIN_POS_MOUSE)
        else:
            self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        hbox = gtk.HBox()
        self.vbox.add(hbox)
        hbox.show()
        if prompt:
            hbox.pack_start(gtk.Label(prompt), fill=False, expand=False)
        self.entry = gtk.Entry()
        self.entry.set_width_chars(32)
        self.entry.set_text(suggestion)
        hbox.pack_start(self.entry)
        self.show_all()

def get_modified_string(title, prompt, string):
    dialog = ReadTextDialog(title, prompt, string)
    if dialog.run() == gtk.RESPONSE_OK:
        string = dialog.entry.get_text()
    dialog.destroy()
    return string

class PopupUser:
    def __init__(self):
        self._gtk_window = None
    def _get_gtk_window(self):
        if not self._gtk_window:
            try:
                temp = self.get_parent()
            except:
                return None
            while temp:
                self._gtk_window = temp
                try:
                    temp = temp.get_parent()
                except:
                    return None
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
    def _show_busy(self, really=True):
        if not really:
            return
        self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
        while gtk.events_pending():
            gtk.main_iteration()
    def _unshow_busy(self, really=True):
        if not really:
            return
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

class ActionButton(gtk.Button):
    def __init__(self, action, use_underline=True):
        label = action.get_property("label")
        stock_id = action.get_property("stock-id")
        if label:
            gtk.Button.__init__(self, label=label, use_underline=use_underline)
            if stock_id:
                image = gtk.Image()
                image.set_from_stock(stock_id, gtk.ICON_SIZE_BUTTON)
                self.set_image(image)
        elif stock_id:
            gtk.Button.__init__(self, stock_id=stock_id, use_underline=use_underline)
        else:
            gtk.Button.__init__(self, use_underline=use_underline)
        self.set_tooltip_text(action.get_property("tooltip"))
        action.connect_proxy(self)

class ActionButtonList:
    def __init__(self, action_group_list, action_name_list=None, use_underline=True):
        self.list = []
        self.dict = {}
        if action_name_list:
            for a_name in action_name_list:
                for a_group in action_group_list:
                    action = a_group.get_action(a_name)
                    if action:
                        button = ActionButton(action, use_underline)
                        self.list.append(button)
                        self.dict[a_name] = button
                        break
        else:
            for a_group in action_group_list:
                for action in a_group.list_actions():
                    button = ActionButton(action, use_underline)
                    self.list.append(button)
                    self.dict[action.get_name()] = button

class ActionHButtonBox(gtk.HBox):
    def __init__(self, action_group_list, action_name_list=None,
                 use_underline=True, expand=True, fill=True, padding=0):
        gtk.HBox.__init__(self)
        self.button_list = ActionButtonList(action_group_list, action_name_list, use_underline)
        for button in self.button_list.list:
            self.pack_start(button, expand, fill, padding)

TOC_NAME, TOC_LABEL, TOC_TOOLTIP, TOC_STOCK_ID = range(4)

class TimeOutController():
    def __init__(self, toggle_data, function=None, is_on=True, interval=10000):
        self._interval = abs(interval)
        self._timeout_id = None
        self._function = function
        self.toggle_action = gtk.ToggleAction(
                toggle_data[TOC_NAME], toggle_data[TOC_LABEL],
                toggle_data[TOC_TOOLTIP], toggle_data[TOC_STOCK_ID]
            )
        self.toggle_action.connect("toggled", self._toggle_acb)
        self.toggle_action.set_active(is_on)
        self._toggle_acb()
    def _toggle_acb(self, action=None):
        if self.toggle_action.get_active():
            self._timeout_id = gobject.timeout_add(self._interval, self._timeout_cb)
    def _timeout_cb(self):
        if self._function:
            self._function()
        return self.toggle_action.get_active()
    def stop_cycle(self):
        if self._timeout_id:
            gobject.source_remove(self._timeout_id)
            self._timeout_id = None
    def restart_cycle(self):
        self.stop_cycle()
        self._toggle_acb()
    def set_function(self, function):
        self.stop_cycle()
        self._function = function
        self._toggle_acb()
    def set_interval(self, interval):
        if interval > 0 and interval is not self._interval:
            self._interval = interval
            self.restart_cycle()
    def get_interval(self):
        return self._interval
    def set_active(self, active=True):
        if active is not self.toggle_action.get_active():
            self.toggle_action.set_active(active)
        self.restart_cycle()

TOC_DEFAULT_REFRESH_TD = ["auto_refresh_toggle", "Auto _Refresh", "Turn data auto refresh on/off", gtk.STOCK_REFRESH]

class RefreshController(TimeOutController):
    def __init__(self, toggle_data=TOC_DEFAULT_REFRESH_TD, function=None, is_on=True, interval=10000):
        TimeOutController.__init__(self, toggle_data, function=function, is_on=is_on, interval=interval)

TOC_DEFAULT_SAVE_TD = ["auto_save_toggle", "Auto _Save", "Turn data auto save on/off", gtk.STOCK_SAVE]

class SaveController(TimeOutController):
    def __init__(self, toggle_data=TOC_DEFAULT_SAVE_TD, function=None, is_on=True, interval=10000):
        TimeOutController.__init__(self, toggle_data, function=function, is_on=is_on, interval=interval)

ROW_LABEL, ROW_TYPE, ROW_EXPAND, ROW_PROPERTIES = range(4)
PROPERTY_NAME, PROPERTY_VALUE = range(2)

def find_label_index(descr, label):
    index = 0
    for index in range(len(descr)):
        if label == descr[index][0]:
            return index
    return None

# Table descriptor is:
#[
#  [ROW_LABEL, ROW_TYPE, ROW_EXPAND, [ (name, value), (name, value), ...]],
#  [ROW_LABEL, ROW_TYPE, ROW_EXPAND, ROW_PROPERTIES],
#  .....
#]
#
# e.g.
#PARENTS_TABLE_DESCR = \
#[
#    ["Rev", gobject.TYPE_INT, False, [("cell-background", "#F0F0F0")]],
#    ["Age", gobject.TYPE_STRING, False, [("cell-background", "white")]],
#    ["Tags", gobject.TYPE_STRING, False, [("cell-background", "#F0F0F0")]],
#    ["Branches", gobject.TYPE_STRING, False, [("cell-background", "white")]],
#    ["Author", gobject.TYPE_STRING, False, [("cell-background", "#F0F0F0")]],
#    ["Description", gobject.TYPE_STRING, True, [("cell-background", "white")]],
#]

class TableView(gtk.TreeView):
    def __init__(self, descr, sel_mode=gtk.SELECTION_SINGLE, perm_headers=False,
                 bgnd=["white", "#F0F0F0"], popup=None):
        self._model = apply(gtk.ListStore, self._get_type_list(descr))
        self._perm_headers = perm_headers
        gtk.TreeView.__init__(self, self._model)
        lenbgnd = len(bgnd)
        self._ncols = len(descr)
        for colid in range(self._ncols):
            col_d = descr[colid]
            cell = gtk.CellRendererText()
            tvcolumn = gtk.TreeViewColumn(col_d[ROW_LABEL], cell, text=colid)
            if bgnd:
                cell.set_property("cell-background", bgnd[colid % lenbgnd])
            for prop in col_d[ROW_PROPERTIES]:
                cell.set_property(prop[PROPERTY_NAME], prop[PROPERTY_VALUE])
            tvcolumn.set_expand(col_d[ROW_EXPAND])
            self.append_column(tvcolumn)
        self.set_headers_visible(perm_headers)
        self.get_selection().set_mode(sel_mode)
        self.get_selection().unselect_all()
        self.connect("button_press_event", self._handle_button_press_cb)
    def _handle_button_press_cb(self, widget, event, popup=None):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 3 and popup:
                menu = self._ui_manager.get_widget(popup)
                menu.popup(None, None, None, event.button, event.time)
                return True
            elif event.button == 2:
                self.get_selection().unselect_all()
                return True
        return False
    def _get_type_list(self, descr):
        list = []
        for cdescr in descr:
            list.append(cdescr[ROW_TYPE])
        return list
    def set_contents(self, cset_list):
        self._model.clear()
        for cset in cset_list:
            self._model.append(cset)
        if not self._perm_headers:
            self.set_headers_visible(self._model.iter_n_children(None) > 0)
        self.get_selection().unselect_all()
    def get_contents(self):
        list = []
        iter = self._model.get_iter_first()
        while iter:
            row = []
            for index in range(self._ncols):
                row.append(self._model.get_value(iter, index))
            list.append(row)
            iter = self._model.iter_next(iter)
        return list
    def get_selected_data(self, columns):
        store, selection = self.get_selection().get_selected_rows()
        list = []
        for row in selection:
            iter = store.get_iter(row)
            row_data = []
            for col in columns:
                row_data.append(store.get_value(iter, col))
            list.append(row_data)
        return list

