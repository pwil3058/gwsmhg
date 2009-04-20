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

import gtk, gutils

'''
External command return values
'''
OK = 0
INFO = 1
WARNING = 2
ERROR = 4
SUGGEST_FORCE = 8
SUGGEST_REFRESH = 16
SUGGEST_RECOVER = 32
SUGGEST_FORCE_OR_REFRESH = SUGGEST_FORCE | SUGGEST_REFRESH
INFO_SUGGEST_FORCE = INFO | SUGGEST_FORCE
WARNING_SUGGEST_FORCE = WARNING | SUGGEST_FORCE
ERROR_SUGGEST_FORCE = ERROR | SUGGEST_FORCE
INFO_SUGGEST_REFRESH = INFO | SUGGEST_REFRESH
WARNING_SUGGEST_REFRESH = WARNING | SUGGEST_REFRESH
ERROR_SUGGEST_REFRESH = ERROR | SUGGEST_REFRESH
INFO_SUGGEST_FORCE_OR_REFRESH = INFO | SUGGEST_FORCE_OR_REFRESH
WARNING_SUGGEST_FORCE_OR_REFRESH = WARNING | SUGGEST_FORCE_OR_REFRESH
ERROR_SUGGEST_FORCE_OR_REFRESH = ERROR | SUGGEST_FORCE_OR_REFRESH

def map_cmd_result(result, stdout_expected=False):
    if result[0] == 0:
        if result[2]:
            outres = WARNING
        elif not stdout_expected and result[1]:
            outres = INFO
        else:
            outres = OK
    else:
        outres = ERROR
    return (outres, result[1], result[2])

class ProblemReporter(gutils.PopupUser):
    def __init__(self):
        gutils.PopupUser.__init__(self)
        pass
    def _report_problem(self, msg, problem_type=gtk.MESSAGE_ERROR):
        dialog = gtk.MessageDialog(parent=self._get_gtk_window(),
                                   flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                                   type=problem_type, buttons=gtk.BUTTONS_CLOSE,
                                   message_format=msg)
        response = dialog.run()
        dialog.destroy()
    def _report_error(self, msg):
        self._report_problem(msg)
    def _report_warning(self, msg):
        self._report_problem(msg, gtk.MESSAGE_WARNING)
    def _report_info(self, msg):
        self._report_problem(msg, gtk.MESSAGE_INFO)
    def _report_any_problems(self, result):
        if result[0] in [ERROR, ERROR_SUGGEST_FORCE]:
            self._report_error(result[1] + result[2])
        elif result[0] in [WARNING, WARNING_SUGGEST_FORCE]:
            self._report_warning(result[1] + result[2])
        elif result[0] in [INFO, INFO_SUGGEST_FORCE]:
            self._report_info(result[1] + result[2])

