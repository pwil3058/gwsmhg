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
SUGGEST_EDIT = 128
SUGGEST_MERGE = 256
SUGGEST_ALL = (SUGGEST_MERGE * 2) - 1 - WARNING|ERROR
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

