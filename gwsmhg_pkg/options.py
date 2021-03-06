### Copyright (C) 2013 Peter Williams <pwil3058@gmail.com>
###
### This program is free software; you can redistribute it and/or modify
### it under the terms of the GNU General Public License as published by
### the Free Software Foundation; version 2 of the License only.
###
### This program is distributed in the hope that it will be useful,
### but WITHOUT ANY WARRANTY; without even the implied warranty of
### MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
### GNU General Public License for more details.
###
### You should have received a copy of the GNU General Public License
### along with this program; if not, write to the Free Software
### Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

'''Manage configurable options for GWSMHG'''


import os
import collections

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

from . import config_data
from . import cmd_result
from . import utils

_GLOBAL_CFG_FILE = os.path.join(config_data.CONFIG_DIR_NAME, "options.cfg")
GLOBAL_OPTIONS = configparser.SafeConfigParser()

def load_global_options():
    global GLOBAL_OPTIONS
    GLOBAL_OPTIONS = configparser.SafeConfigParser()
    try:
        GLOBAL_OPTIONS.read(_GLOBAL_CFG_FILE)
    except configparser.ParsingError as edata:
        return cmd_result.Result(cmd_result.ERROR, "", _("Error reading global options: {0}\n").format(str(edata)))
    return cmd_result.Result(cmd_result.OK, "", "")

def reload_global_options():
    global GLOBAL_OPTIONS
    new_version = configparser.SafeConfigParser()
    try:
        new_version.read(_GLOBAL_CFG_FILE)
    except configparser.ParsingError as edata:
        return cmd_result.Result(cmd_result.ERROR, "", _("Error reading global options: {0}\n").format(str(edata)))
    GLOBAL_OPTIONS = new_version
    return cmd_result.Result(cmd_result.OK, "", "")

_PGND_CFG_FILE = os.path.expanduser(".hg/gwsmhg.cfg")
PGND_OPTIONS = configparser.SafeConfigParser()

def load_pgnd_options():
    global PGND_OPTIONS
    PGND_OPTIONS = configparser.SafeConfigParser()
    try:
        PGND_OPTIONS.read(_PGND_CFG_FILE)
    except configparser.ParsingError as edata:
        return cmd_result.Result(cmd_result.ERROR, "", _("Error reading playground options: {0}\n").format(str(edata)))
    return cmd_result.Result(cmd_result.OK, "", "")

def reload_pgnd_options():
    global PGND_OPTIONS
    new_version = configparser.SafeConfigParser()
    try:
        new_version.read(_PGND_CFG_FILE)
    except configparser.ParsingError as edata:
        return cmd_result.Result(cmd_result.ERROR, "", _("Error reading playground options: {0}\n").format(str(edata)))
    PGND_OPTIONS = new_version
    return cmd_result.Result(cmd_result.OK, "", "")

class DuplicateDefn(Exception): pass

Defn = collections.namedtuple("Defn", ["str_to_val", "default", "help"])

DEFINITIONS = {}

def define(section, oname, odefn):
    if not section in DEFINITIONS:
        DEFINITIONS[section] = {oname: odefn,}
    elif oname in DEFINITIONS[section]:
        raise DuplicateDefn("{0}:{1} already defined".format(section, oname))
    else:
        DEFINITIONS[section][oname] = odefn

def str_to_bool(string):
    lowstr = string.lower()
    if lowstr in ["true", "yes", "on", "1"]:
        return True
    elif lowstr in ["false", "no", "off", "0"]:
        return False
    else:
        return None

def get(section, oname):
    # This should cause an exception if section:oname is not known
    # which is what we want
    str_to_val = DEFINITIONS[section][oname].str_to_val
    value = None
    if PGND_OPTIONS.has_option(section, oname):
        value = str_to_val(PGND_OPTIONS.get(section, oname))
    elif GLOBAL_OPTIONS.has_option(section, oname):
        value = str_to_val(GLOBAL_OPTIONS.get(section, oname))
    return value if value is not None else DEFINITIONS[section][oname].default
