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
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import shlex
try:
    import gtkspell
    GTKSPELL_AVAILABLE = True
except ImportError:
    GTKSPELL_AVAILABLE = False

import os
import gtk
import pango
import gobject

from gwsmhg_pkg import cmd_result
from gwsmhg_pkg import utils
from gwsmhg_pkg import runext

from gwsmhg_pkg import textview
from gwsmhg_pkg import gutils
from gwsmhg_pkg import dialogue
from gwsmhg_pkg import ifce
from gwsmhg_pkg import config
from gwsmhg_pkg import actions

def edit_files_extern(file_list):
    def _edit_files_extern(filelist, edstr=config.DEFAULT_EDITOR):
        cmd = shlex.split(edstr) + filelist
        if cmd[0] in config.EDITORS_THAT_NEED_A_TERMINAL:
            if config.DEFAULT_TERMINAL == "gnome-terminal":
                flag = '-x'
            else:
                flag = '-e'
            cmd = [config.DEFAULT_TERMINAL, flag] + cmd
        return runext.run_cmd_in_bgnd(cmd)
    ed_assigns = config.assign_extern_editors(file_list)
    for edstr in list(ed_assigns.keys()):
        _edit_files_extern(ed_assigns[edstr], edstr)

class MessageWidget(textview.Widget, actions.CAGandUIManager):
    UI_DESCR = ''
    AC_SAVE_OK = actions.ActionCondns.new_flag()
    def __init__(self, save_file_name=None, auto_save=False):
        textview.Widget.__init__(self)
        actions.CAGandUIManager.__init__(self)
        self.view.set_right_margin_position(72)
        self.view.set_show_right_margin(True)
        self.view.set_cursor_visible(True)
        self.view.set_editable(True)
        if GTKSPELL_AVAILABLE:
            gtkspell.Spell(self.view)
        # Set up file stuff
        self._save_interval = 1000 # milliseconds
        self._save_file_name = save_file_name
        self._save_file_digest = None
        self.save_toggle_action.set_active(auto_save)
        self._update_action_sensitivities()
    def populate_action_groups(self):
        # Set up action groups
        self.action_group = gtk.ActionGroup("always on")
        self.conditional_action_group = gtk.ActionGroup("save file dependent")
        self.action_groups[0].add_actions(
            [
                ("text_edit_ack", None, _('_Ack'), None,
                 _('Insert Acked-by tag at cursor position'), self._insert_ack_acb),
                ("text_edit_sign_off", None, _('_Sign Off'), None,
                 _('Insert Signed-off-by tag at cursor position'), self._insert_sign_off_acb),
                ("text_edit_author", None, _('A_uthor'), None,
                 _('Insert Author tag at cursor position'), self._insert_author_acb),
                ("text_edit_save_as", gtk.STOCK_SAVE_AS, _('S_ave as'), "",
                 _('Save summary to a file'), self._save_text_as_acb),
                ("text_edit_load_from", gtk.STOCK_REVERT_TO_SAVED, _('_Load from'), "",
                 _('Load summary from a file'), self._load_text_from_acb),
                ("text_edit_insert_from", gtk.STOCK_PASTE, _('_Insert from'), '',
                 _('Insert the contents of a file at cursor position'), self._insert_text_from_acb),
            ])
        self.action_groups[self.AC_SAVE_OK].add_actions(
            [
                ("text_edit_save_to_file", gtk.STOCK_SAVE, _('_Save'), "",
                 _('Save summary to file'), self._save_text_to_file_acb),
                ("text_edit_load_fm_file", gtk.STOCK_REVERT_TO_SAVED, _('_Revert'), "",
                 _('Load summary from saved file'), self._load_text_fm_file_acb),
            ])
        self.save_toggle_action = gtk.ToggleAction(
                "text_edit_toggle_auto_save", _('Auto Sa_ve'),
                _('Automatically/periodically save summary to file'), gtk.STOCK_SAVE
            )
        self.save_toggle_action.connect("toggled", self._toggle_auto_save_acb)
        self.action_groups[self.AC_SAVE_OK].add_action(self.save_toggle_action)
    def _update_action_sensitivities(self):
        mcondn = actions.MaskedCondns(0 if self._save_file_name is not None else self.AC_SAVE_OK, self.AC_SAVE_OK)
        self.action_groups.update_condns(mcondn)
    @staticmethod
    def _inform_user_data_problem():
        dialogue.inform_user(_('Unable to determine user\'s data'))
    def _insert_sign_off_acb(self, _action=None):
        data = ifce.get_author_name_and_email()
        if data:
            self.bfr.insert_at_cursor("Signed-off-by: %s\n" % data)
        else:
            self._inform_user_data_problem()
    def _insert_ack_acb(self, _action=None):
        data = ifce.get_author_name_and_email()
        if data:
            self.bfr.insert_at_cursor("Acked-by: %s\n" % data)
        else:
            self._inform_user_data_problem()
    def _insert_author_acb(self, _action=None):
        data = ifce.get_author_name_and_email()
        if data:
            self.bfr.insert_at_cursor("Author: %s\n" % data)
        else:
            self._inform_user_data_problem()
    def _ok_to_overwrite_summary(self):
        if self.bfr.get_char_count():
            return dialogue.ask_ok_cancel(_('Buffer contents will be destroyed. Continue?'))
        return True
    def save_text_to_file(self, file_name=None):
        if not file_name:
            file_name = self._save_file_name
        try:
            open(file_name, 'w').write(self.get_contents())
            self._save_file_name = file_name
            self._save_file_digest = self.digest
        except IOError:
            dialogue.alert_user(_('Save failed!'))
    def _save_text_to_file_acb(self, _action=None):
        self.save_text_to_file()
    def _save_text_as_acb(self, _action=None):
        fname = dialogue.ask_file_name(_('Enter file name'), existing=False, suggestion=self._save_file_name)
        if fname and os.path.exists(fname) and not utils.samefile(fname, self._save_file_name):
            if not utils.samefile(fname, ifce.GIT.get_default_commit_save_file()):
                if not dialogue.ask_ok_cancel(os.linesep.join([fname, _('\nFile exists. Overwrite?')])):
                    return
        self.save_text_to_file(file_name=fname)
    def load_text_fm_file(self, file_name=None, already_checked=False):
        if not already_checked and not self._ok_to_overwrite_summary():
            return
        if not file_name:
            file_name = self._save_file_name
        try:
            self.set_contents(open(file_name, 'rb').read())
            self._save_file_name = file_name
            self._save_file_digest = self.digest
        except IOError:
            dialogue.alert_user(_('Load from file failed!'))
    def _load_text_fm_file_acb(self, _action=None):
        self.load_text_fm_file()
    def _load_text_from_acb(self, _action=None):
        if not self._ok_to_overwrite_summary():
            return
        fname = dialogue.ask_file_name(_('Enter file name'), existing=True)
        self.load_text_fm_file(file_name=fname, already_checked=True)
    def _insert_text_from_acb(self, _action=None):
        file_name = dialogue.ask_file_name(_('Enter file name'), existing=True)
        if file_name is not None:
            try:
                text = open(file_name, 'rb').read()
                self.bfr.insert_at_cursor(text)
                self.bfr.set_modified(True)
            except IOError:
                dialogue.alert_user(_('Insert at cursor from file failed!'))
    def get_auto_save(self):
        return self.save_toggle_action.get_active()
    def set_auto_save(self, active=True):
        self.save_toggle_action.set_active(active)
    def get_auto_save_interval(self):
        return self._save_interval
    def set_auto_save_inerval(self, interval):
        self._save_interval = interval
    def do_auto_save(self):
        if self._save_file_name:
            if not self._save_file_digest or self._save_file_digest != self.digest:
                self.save_text_to_file()
        return self.get_auto_save()
    def _toggle_auto_save_acb(self, _action=None):
        if self.get_auto_save():
            gobject.timeout_add(self._save_interval, self.do_auto_save)
    def finish_up(self, clear_save=False):
        if self.get_auto_save():
            self.set_auto_save(False)
            self.do_auto_save()
        if clear_save and self._save_file_name:
            self.save_text_to_file(content="")

class DbMessageWidget(MessageWidget):
    UI_DESCR = ''
    def get_text_fm_db(self):
        raise NotImplentedError('Must be defined in child')
    def set_text_in_db(self, text):
        raise NotImplentedError('Must be defined in child')
    def __init__(self, save_file_name=None, auto_save=False):
        MessageWidget.__init__(self)
        self.view.set_right_margin_position(72)
        self.view.set_show_right_margin(True)
        self.view.set_cursor_visible(True)
        self.view.set_editable(True)
        # Set up file stuff
        self._save_interval = 1000 # milliseconds
        self._save_file_name = save_file_name
        self._save_file_digest = None
        # Make some buttons
        self.save_button = gutils.ActionButton(self.action_groups.get_action("text_edit_save"), use_underline=False)
        self.reload_button = gutils.ActionButton(self.action_groups.get_action("text_edit_load"), use_underline=False)
    def populate_action_groups(self):
        MessageWidget.populate_action_groups(self)
        self.action_group.add_actions(
            [
                ("text_edit_save", gtk.STOCK_SAVE, _('_Save'), "",
                 _('Save summary to database'), self._save_text_acb),
                ("text_edit_load", gtk.STOCK_REVERT_TO_SAVED, _('_Reload'), "",
                 _('Reload summary from database'), self._reload_text_acb),
            ])
    def _save_text_acb(self, _action=None):
        text = self.bfr.get_text(self.bfr.get_start_iter(), self.bfr.get_end_iter())
        result = self.set_text_in_db(text)
        if result.eflags:
            dialogue.report_any_problems(result)
        else:
            # get the tidied up version of the text
            self.load_text_fm_db(False)
    def load_text_fm_db(self, clear_digest=True):
        try:
            self.set_contents(self.get_text_fm_db())
            self.bfr.set_modified(False)
            if clear_digest:
                self._save_file_digest = None
        except cmd_result.Failure as failure:
            dialogue.report_failure(failure)
    def _reload_text_acb(self, _action=None):
        if self._ok_to_overwrite_summary():
            self.load_text_fm_db()

class SummaryBuffer(textview.Buffer):
    def __init__(self):
        textview.Buffer.__init__(self)
        self.action_group = gtk.ActionGroup("summary")
        self.action_group.add_actions(
            [
                ("summary_ack", None, _('_Ack'), None,
                 _('Insert Acked-by tag at cursor position'), self._insert_ack_acb),
                ("summary_sign_off", None, _('_Sign Off'), None,
                 _('Insert Signed-off-by tag at cursor position'), self._insert_sign_off_acb),
                ("summary_author", None, _('A_uthor'), None,
                 _('Insert Author tag at cursor position'), self._insert_author_acb),
            ])
    def _insert_sign_off_acb(self, _action=None):
        data = ifce.SCM.get_author_name_and_email()
        self.insert_at_cursor("Signed-off-by: %s\n" % utils.make_utf8_compliant(data))
    def _insert_ack_acb(self, _action=None):
        data = ifce.SCM.get_author_name_and_email()
        self.insert_at_cursor("Acked-by: %s\n" % utils.make_utf8_compliant(data))
    def _insert_author_acb(self, _action=None):
        data = ifce.SCM.get_author_name_and_email()
        self.insert_at_cursor("Author: %s\n" % utils.make_utf8_compliant(data))

class SummaryView(textview.View):
    def __init__(self, text_buffer=None):
        if not text_buffer:
            text_buffer = SummaryBuffer()
        textview.View.__init__(self, text_buffer)
        fdesc = pango.FontDescription("mono, 10")
        self.modify_font(fdesc)
        self.set_right_margin_position(72)
        self.set_show_right_margin(True)
        context = self.get_pango_context()
        metrics = context.get_metrics(fdesc)
        width = pango.PIXELS(metrics.get_approximate_char_width() * 81)
        x, y = self.buffer_to_window_coords(gtk.TEXT_WINDOW_TEXT, width, width / 3)
        self.set_size_request(x, y)
        self.set_cursor_visible(True)
        self.set_editable(True)
        self.ui_manager = gutils.UIManager()
        self.ui_manager.insert_action_group(text_buffer.action_group, -1)
    def get_action(self, action_name):
        for action_group in self.ui_manager.get_action_groups():
            action = action_group.get_action(action_name)
            if action:
                return action
        return None
    def get_msg(self):
        text_buffer = self.get_buffer()
        return text_buffer.get_text(text_buffer.get_start_iter(), text_buffer.get_end_iter())

class ChangeSummaryBuffer(SummaryBuffer):
    def __init__(self, auto_save=True):
        SummaryBuffer.__init__(self)
        self._save_interval = 1000 # milliseconds
        self._save_file_name = ifce.SCM.get_default_commit_save_file()
        if not os.path.exists(self._save_file_name):
            self.save_summary(content="")
        self.action_group.add_actions(
            [
                ("menu_summary", None, _('_Summary')),
                ("change_summary_save", gtk.STOCK_SAVE, _('_Save'), "",
                 _('Save commit summary'), self._save_summary_acb),
                ("change_summary_save_as", gtk.STOCK_SAVE_AS, _('S_ave as'), "",
                 _('Save commit summary to a file'), self.save_summary_as),
                ("change_summary_load", gtk.STOCK_REVERT_TO_SAVED, _('_Revert'), "",
                 _('Load summary from saved file'), self._load_summary_acb),
                ("change_summary_load_from", gtk.STOCK_REVERT_TO_SAVED, _('_Load from'), "",
                 _('Load summary from a file'), self.load_summary_from),
                ("change_summary_insert_from", gtk.STOCK_PASTE, _('_Insert from'), "",
                 _('Insert contents of a file at cursor position'), self.insert_summary_from),
            ])
        self.save_toggle_action = gtk.ToggleAction(
                "summary_toggle_auto_save", _('Auto Sa_ve'),
                _('Automatically/periodically save summary to file'), gtk.STOCK_SAVE
            )
        self.save_toggle_action.connect("toggled", self._toggle_auto_save_acb)
        self.save_toggle_action.set_active(auto_save)
        self.action_group.add_action(self.save_toggle_action)
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
        except IOError:
            dialogue.alert_user(_('Save failed!'))
    def _save_summary_acb(self, _action=None):
        self.save_summary()
    def save_summary_as(self, _action=None):
        fname = dialogue.ask_file_name(_('Enter file name'), existing=False, suggestion=self._save_file_name)
        if fname and os.path.exists(fname) and not utils.samefile(fname, self._save_file_name):
            if not utils.samefile(fname, ifce.SCM.get_default_commit_save_file()):
                if not dialogue.ask_ok_cancel(os.linesep.join([fname, _('\nFile exists. Overwrite?')])):
                    return
        self.save_summary(file_name=fname)
    def _ok_to_overwrite_summary(self):
        if self.get_char_count():
            return dialogue.ask_ok_cancel(_('Buffer contents will be destroyed. Continue?'))
        return True
    def load_summary(self, file_name=None, already_checked=False):
        if not already_checked and not self._ok_to_overwrite_summary():
            return
        if not file_name:
            file_name = self._save_file_name
        try:
            text = open(file_name, 'rb').read()
            self.set_text(utils.make_utf8_compliant(text))
            self._save_file_name = file_name
            self.set_modified(False)
        except IOError:
            dialogue.alert_user(_('Load from file failed!'))
    def _load_summary_acb(self, _action=None):
        self.load_summary()
    def load_summary_from(self, _action=None):
        if not self._ok_to_overwrite_summary():
            return
        fname = dialogue.ask_file_name(_('Enter file name'), existing=True)
        self.load_summary(file_name=fname, already_checked=True)
    def insert_summary_from(self, _action=None):
        file_name = dialogue.ask_file_name(_('Enter file name'), existing=True)
        try:
            text = open(file_name, 'rb').read()
            self.insert_at_cursor(utils.make_utf8_compliant(text))
            self.set_modified(True)
        except IOError:
            dialogue.alert_user(_('Insert at cursor from file failed!'))
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
    def _toggle_auto_save_acb(self, _action=None):
        if self.get_auto_save():
            gobject.timeout_add(self._save_interval, self.do_auto_save)
    def finish_up(self, clear_save=False):
        if self.get_auto_save():
            self.set_auto_save(False)
            self.do_auto_save()
        if clear_save:
            self.save_summary(file_name=ifce.SCM.get_default_commit_save_file(),
                              content="")

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
    def __init__(self, text_buffer=None, auto_save=True):
        if not text_buffer:
            text_buffer = ChangeSummaryBuffer(auto_save)
        SummaryView.__init__(self, text_buffer)
        self.change_summary_merge_id = self.ui_manager.add_ui_from_string(CHANGE_SUMMARY_UI_DESCR)

class NewPatchSummaryBuffer(SummaryBuffer):
    def __init__(self):
        SummaryBuffer.__init__(self)
        self.action_group.add_actions(
            [
                ("menu_summary", None, _('_Description')),
                ("patch_summary_insert_from", gtk.STOCK_PASTE, _('_Insert from'), "",
                 _('Insert contents of a file at cursor position'), self._insert_summary_from_acb),
            ])
    def _insert_summary_from_acb(self, _action=None):
        file_name = dialogue.ask_file_name(_('Enter file name'), existing=True)
        if file_name is not None:
            try:
                text = open(file_name, 'rb').read()
                self.insert_at_cursor(utils.make_utf8_compliant(text))
                self.set_modified(True)
            except IOError:
                dialogue.alert_user(_('Insert at cursor from file failed!'))

class PatchSummaryBuffer(NewPatchSummaryBuffer):
    def __init__(self, get_summary, set_summary, patch=None):
        self.patch = patch
        self._set_summary = set_summary
        self._get_summary = get_summary
        NewPatchSummaryBuffer.__init__(self)
        self.action_group.add_actions(
            [
                ("patch_summary_save", gtk.STOCK_SAVE, _('_Save'), "",
                 _('Save commit summary'), self._save_summary_acb),
                ("patch_summary_load", gtk.STOCK_REVERT_TO_SAVED, _('_Reload'), "",
                 _('Load summary from saved file'), self._load_summary_acb),
            ])
    def _save_summary_acb(self, _action=None):
        text = self.get_text(self.get_start_iter(), self.get_end_iter())
        result = self._set_summary(self.patch, text)
        if result.ecode:
            dialogue.report_any_problems(result)
        else:
            self.set_modified(False)
    def _ok_to_overwrite_summary(self):
        if self.get_char_count() and self.get_modified():
            return dialogue.ask_ok_cancel(_('Buffer contents will be destroyed. Continue?'))
        return True
    def load_summary(self):
        try:
            text = self._get_summary(self.patch)
            # if the patch was imported its header may not be UTF-8 compliant
            self.set_text(utils.make_utf8_compliant(text))
            self.set_modified(False)
        except cmd_result.Failure as failure:
            dialogue.report_failure(failure)
    def _load_summary_acb(self, _action=None):
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
    def __init__(self, text_buffer=None):
        if not text_buffer:
            text_buffer = NewPatchSummaryBuffer()
        SummaryView.__init__(self, text_buffer)
        self.patch_summary_merge_id = self.ui_manager.add_ui_from_string(NEW_PATCH_SUMMARY_UI_DESCR)

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
    def __init__(self, get_summary, set_summary, patch=None):
        text_buffer = PatchSummaryBuffer(get_summary, set_summary, patch)
        NewPatchSummaryView.__init__(self, text_buffer)
        self.patch_summary_merge_id = self.ui_manager.add_ui_from_string(PATCH_SUMMARY_UI_DESCR)
        action = text_buffer.action_group.get_action("patch_summary_save")
        self.save_button = gutils.ActionButton(action, use_underline=False)
    def load_summary(self):
        self.get_buffer().load_summary()
