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

import gtk, gtk.gdk, os.path, sys, collections

from . import config_data

# find the icons directory
# first look in the source directory (so that we can run uninstalled)
_libdir = os.path.join(sys.path[0], 'pixmaps')
if not os.path.exists(_libdir) or not os.path.isdir(_libdir):
    _TAILEND = os.path.join('share', 'pixmaps', config_data.APP_NAME)
    _prefix = sys.path[0]
    while _prefix:
        _libdir = os.path.join(_prefix, _TAILEND)
        if os.path.exists(_libdir) and os.path.isdir(_libdir):
            break
        _prefix = os.path.dirname(_prefix)

APP_ICON = config_data.APP_NAME
APP_ICON_FILE = os.path.join(os.path.dirname(_libdir), APP_ICON + os.extsep + 'png')

STOCK_APPLIED = 'gwsmhg_stock_applied'
STOCK_APPLIED_NEEDS_REFRESH = 'gwsmhg_stock_applied_needs_refresh'
STOCK_APPLIED_UNREFRESHABLE = 'gwsmhg_stock_applied_unrefreshable'
STOCK_BRANCH = 'gwsmhg_stock_branch'
STOCK_COMMIT = 'gwsmhg_stock_commit'
STOCK_DIFF = 'gwsmhg_stock_diff'
STOCK_FILE_PROBLEM = 'gwsmhg_stock_file_problem'
STOCK_FINISH_PATCH = 'gwsmhg_stock_finish_patch'
STOCK_FOLD_PATCH = 'gwsmhg_stock_fold_patch'
STOCK_IMPORT_PATCH = 'gwsmhg_stock_import_patch'
STOCK_MERGE = 'gwsmhg_stock_merge'
STOCK_NEW_PATCH = 'gwsmhg_stock_new_patch'
STOCK_PATCH_GUARD = 'gwsmhg_stock_patch_guard'
STOCK_PATCH_GUARD_SELECT = 'gwsmhg_stock_patch_guard_select'
STOCK_POP_PATCH = 'gwsmhg_stock_pop_patch'
STOCK_PUSH_PATCH = 'gwsmhg_stock_push_patch'
STOCK_REFRESH_PATCH = 'gwsmhg_stock_refresh_patch'
STOCK_TAG = 'gwsmhg_stock_tag'

_STOCK_ITEMS_OWN_PNG = [
    (STOCK_APPLIED, _('Applied'), 0, 0, None),
    (STOCK_APPLIED_NEEDS_REFRESH, _('Applied (needs refresh)'), 0, 0, None),
    (STOCK_APPLIED_UNREFRESHABLE, _('Applied (unrefreshable)'), 0, 0, None),
    (STOCK_BRANCH, _('Branch'), 0, 0, None),
    (STOCK_COMMIT, _('Commit'), 0, 0, None),
    (STOCK_DIFF, _('Diff'), 0, 0, None),
    (STOCK_FILE_PROBLEM, _('File Problem'), 0, 0, None),
    (STOCK_FINISH_PATCH, _('Finish'), 0, 0, None),
    (STOCK_FOLD_PATCH, _('Fold'), 0, 0, None),
    (STOCK_IMPORT_PATCH, _('Import'), 0, 0, None),
    (STOCK_MERGE, _('Merge'), 0, 0, None),
    (STOCK_NEW_PATCH, _('New'), 0, 0, None),
    (STOCK_PATCH_GUARD, _('Guard'), 0, 0, None),
    (STOCK_PATCH_GUARD_SELECT, _('Select'), 0, 0, None),
    (STOCK_POP_PATCH, _('Pop'), 0, 0, None),
    (STOCK_PUSH_PATCH, _('Push'), 0, 0, None),
    (STOCK_REFRESH_PATCH, _('Refresh'), 0, 0, None),
    (STOCK_TAG, _('Tag'), 0, 0, None),
]

gtk.stock_add(_STOCK_ITEMS_OWN_PNG)

_FACTORY = gtk.IconFactory()
_FACTORY.add_default()

def _png_file_name(item_name):
    return os.path.join(_libdir, item_name[len('gwsmhg_'):] + os.extsep + 'png')

def make_pixbuf(name):
    return gtk.gdk.pixbuf_new_from_file(_png_file_name(name))

for _item in _STOCK_ITEMS_OWN_PNG:
    _name = _item[0]
    _FACTORY.add(_name, gtk.IconSet(make_pixbuf(_name)))

StockAlias = collections.namedtuple('StockAlias', ['name', 'alias', 'text'])

# Icons that are aliased to Gtk or other stock items
STOCK_BACKOUT = 'gwsmhg_stock_backout'
STOCK_CHECKOUT = 'gwsmhg_stock_checkout'
STOCK_CLONE = 'gwsmhg_stock_clone'
STOCK_CONFIG = 'gwsmhg_stock_config'
STOCK_EDIT = 'gwsmhg_stock_edit'
STOCK_GRAPH = 'gwsmhg_stock_graph'
STOCK_GUESS = 'gwsmhg_stock_guess'
STOCK_INIT = 'gwsmhg_stock_init'
STOCK_INSERT = 'gwsmhg_stock_insert'
STOCK_LOG = 'gwsmhg_stock_log'
STOCK_MARK_RESOLVE = 'gwsmhg_stock_mark_resolve'
STOCK_MARK_UNRESOLVE = 'gwsmhg_stock_mark_uresolve'
STOCK_MOVE = 'gwsmhg_stock_move'
STOCK_PULL = 'gwsmhg_stock_pull'
STOCK_PUSH = 'gwsmhg_stock_push'
STOCK_QGUARD = 'gwsmhg_qguard'
STOCK_QNEW = 'gwsmhg_qnew'
STOCK_QPUSH_MERGE = 'gwsmhg_qpush_merge'
STOCK_QPUSH_MERGE_ALL = 'gwsmhg_qpush_merge_all'
STOCK_QREFRESH = 'gwsmhg_qrefresh'
STOCK_QSELECT = 'gwsmhg_qselect'
STOCK_RECOVERY = 'gwsmhg_stock_recovery'
STOCK_REMOVE = 'gwsmhg_stock_remove'
STOCK_RENAME = 'gwsmhg_stock_rename'
STOCK_RESOLVE = 'gwsmhg_stock_resolve'
STOCK_REVERT = 'gwsmhg_stock_revert'
STOCK_ROLLBACK = 'gwsmhg_stock_rollback'
STOCK_SELECT_GUARD = 'gwsmhg_stock_select_guard'
STOCK_SERVE = 'gwsmhg_stock_serve'
STOCK_SHELVE = 'gwsmhg_stock_shelve'
STOCK_STATUS = 'gwsmhg_stock_status'
STOCK_STATUS_NOT_OK = 'gwsmhg_stock_status_not_ok'
STOCK_STATUS_OK = 'gwsmhg_stock_ok'
STOCK_SYNCH = 'gwsmhg_stock_synch'
STOCK_UPDATE = 'gwsmhg_stock_update'
STOCK_VERIFY = 'gwsmhg_stock_verify'

# Icons that have to be designed eventually (using GtK stock in the meantime)
_STOCK_ALIAS_LIST = [
    StockAlias(name=STOCK_BACKOUT, alias=gtk.STOCK_MEDIA_REWIND, text=''),
    StockAlias(name=STOCK_CHECKOUT, alias=gtk.STOCK_EXECUTE, text=''),
    StockAlias(name=STOCK_CLONE, alias=gtk.STOCK_COPY, text=''),
    StockAlias(name=STOCK_CONFIG, alias=gtk.STOCK_PREFERENCES, text=''),
    StockAlias(name=STOCK_EDIT, alias=gtk.STOCK_EDIT, text=''),
    StockAlias(name=STOCK_GRAPH, alias=gtk.STOCK_FILE, text=''),
    StockAlias(name=STOCK_GUESS, alias=gtk.STOCK_DIALOG_QUESTION, text=''),
    StockAlias(name=STOCK_INIT, alias=STOCK_APPLIED, text=''),
    StockAlias(name=STOCK_INSERT, alias=gtk.STOCK_ADD, text='_Insert'),
    StockAlias(name=STOCK_LOG, alias=gtk.STOCK_FIND, text=''),
    StockAlias(name=STOCK_MARK_RESOLVE, alias=gtk.STOCK_APPLY, text=''),
    StockAlias(name=STOCK_MARK_UNRESOLVE, alias=gtk.STOCK_CANCEL, text=''),
    StockAlias(name=STOCK_MOVE, alias=gtk.STOCK_PASTE, text=''),
    StockAlias(name=STOCK_PULL, alias=gtk.STOCK_GO_FORWARD, text=''),
    StockAlias(name=STOCK_PUSH, alias=gtk.STOCK_GO_BACK, text=''),
    StockAlias(name=STOCK_QGUARD, alias=STOCK_PATCH_GUARD, text='QGuard'),
    StockAlias(name=STOCK_QNEW, alias=STOCK_NEW_PATCH, text='QNew'),
    StockAlias(name=STOCK_QPUSH_MERGE, alias=STOCK_PUSH_PATCH, text='QPush -m'),
    StockAlias(name=STOCK_QPUSH_MERGE_ALL, alias=STOCK_PUSH_PATCH, text='QPush -ma'),
    StockAlias(name=STOCK_QREFRESH, alias=STOCK_REFRESH_PATCH, text='QRefresh'),
    StockAlias(name=STOCK_QSELECT, alias=STOCK_PATCH_GUARD_SELECT, text='QSelect'),
    StockAlias(name=STOCK_RECOVERY, alias=gtk.STOCK_REVERT_TO_SAVED, text=''),
    StockAlias(name=STOCK_REMOVE, alias=gtk.STOCK_REMOVE, text=''),
    StockAlias(name=STOCK_RENAME, alias=gtk.STOCK_PASTE, text=''),
    StockAlias(name=STOCK_RESOLVE, alias=gtk.STOCK_CONVERT, text='Resolve'),
    StockAlias(name=STOCK_REVERT, alias=gtk.STOCK_UNDO, text=''),
    StockAlias(name=STOCK_ROLLBACK, alias=gtk.STOCK_UNDO, text=''),
    StockAlias(name=STOCK_SELECT_GUARD, alias=STOCK_APPLIED, text=''),
    StockAlias(name=STOCK_SERVE, alias=gtk.STOCK_EXECUTE, text=''),
    StockAlias(name=STOCK_SHELVE, alias=gtk.STOCK_EXECUTE, text=''),
    StockAlias(name=STOCK_STATUS, alias=gtk.STOCK_INFO, text=''),
    StockAlias(name=STOCK_STATUS_NOT_OK, alias=gtk.STOCK_CANCEL, text=''),
    StockAlias(name=STOCK_STATUS_OK, alias=gtk.STOCK_APPLY, text=''),
    StockAlias(name=STOCK_SYNCH, alias=gtk.STOCK_REFRESH, text=''),
    StockAlias(name=STOCK_UPDATE, alias=gtk.STOCK_EXECUTE, text=''),
    StockAlias(name=STOCK_VERIFY, alias=STOCK_APPLIED, text=''),
]

_STYLE = gtk.Frame().get_style()

for _item in _STOCK_ALIAS_LIST:
    _FACTORY.add(_item.name, _STYLE.lookup_icon_set(_item.alias))

gtk.stock_add([(item.name, item.text, 0, 0, None) for item in _STOCK_ALIAS_LIST])
