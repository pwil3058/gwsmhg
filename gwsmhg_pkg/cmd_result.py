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

import gtk
from gwsmhg_pkg import ifce

'''
External command return values
'''

OK = 0
WARNING = 1
ERROR = 2
SUGGEST_FORCE = 4
SUGGEST_REFRESH = 8
SUGGEST_RECOVER = 16
SUGGEST_RENAME = 32
SUGGEST_DISCARD = 64
SUGGEST_MERGE = 128
SUGGEST_FORCE_OR_REFRESH = SUGGEST_FORCE | SUGGEST_REFRESH
WARNING_SUGGEST_FORCE = WARNING | SUGGEST_FORCE
ERROR_SUGGEST_FORCE = ERROR | SUGGEST_FORCE
WARNING_SUGGEST_REFRESH = WARNING | SUGGEST_REFRESH
ERROR_SUGGEST_REFRESH = ERROR | SUGGEST_REFRESH
WARNING_SUGGEST_FORCE_OR_REFRESH = WARNING | SUGGEST_FORCE_OR_REFRESH
ERROR_SUGGEST_FORCE_OR_REFRESH = ERROR | SUGGEST_FORCE_OR_REFRESH
SUGGEST_FORCE_OR_RENAME = SUGGEST_FORCE | SUGGEST_RENAME
SUGGEST_MERGE_OR_DISCARD = SUGGEST_MERGE | SUGGEST_DISCARD

BASIC_VALUES_MASK = OK | WARNING | ERROR

def basic_value(res):
    return res & BASIC_VALUES_MASK

def is_ok(res):
    return basic_value(res) == OK

def is_warning(res):
    return basic_value(res) == WARNING

def is_less_than_warning(res):
    return basic_value(res) < WARNING

def is_error(res):
    return basic_value(res) == ERROR

def is_less_than_error(res):
    return basic_value(res) < ERROR

def map_cmd_result(result, ignore_err_re=None):
    if result[0] == 0:
        if result[2] and not (ignore_err_re and ignore_err_re.match(result[2])):
            outres = WARNING
        else:
            outres = OK
    else:
        outres = ERROR
    return (outres, result[1], result[2])

class ProblemReporter:
    def __init__(self):
        pass
    def _report_problem(self, msg, problem_type=gtk.MESSAGE_ERROR, parent=None):
        if not parent:
            parent = ifce.main_window
        dialog = gtk.MessageDialog(parent=parent,
                                   flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                                   type=problem_type, buttons=gtk.BUTTONS_CLOSE,
                                   message_format=msg)
        response = dialog.run()
        dialog.destroy()
    def _report_error(self, msg):
        self._report_problem(msg)
    def _report_warning(self, msg):
        self._report_problem(msg, gtk.MESSAGE_WARNING)
    def _report_any_problems(self, result):
        if result[0] & ERROR:
            self._report_error(result[1] + result[2])
        elif result[0] & WARNING:
            self._report_warning(result[1] + result[2])

