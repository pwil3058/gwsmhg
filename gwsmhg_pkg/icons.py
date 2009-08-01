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

import gtk, gtk.gdk, os.path, sys

STOCK_COMMIT = "stock_commit"
STOCK_DIFF = "stock_diff"
STOCK_POP_PATCH = "stock_pop_patch"
STOCK_PUSH_PATCH = "stock_push_patch"
STOCK_FOLD_PATCH = "stock_fold_patch"
STOCK_FINISH_PATCH = "stock_finish_patch"
STOCK_IMPORT_PATCH = "stock_import_patch"
STOCK_APPLIED = "stock_applied"
STOCK_MERGE = "stock_merge"
STOCK_TAG = "stock_tag"
STOCK_BRANCH = "stock_branch"
APP_ICON = "gwsmhg"

# Icons that have to be designed eventually (using GtK stock in the meantime)
STOCK_PULL = gtk.STOCK_GO_FORWARD
STOCK_PUSH = gtk.STOCK_GO_BACK
STOCK_VERIFY = STOCK_APPLIED
STOCK_CHECKOUT = gtk.STOCK_EXECUTE
STOCK_UPDATE = gtk.STOCK_EXECUTE
STOCK_CLONE = gtk.STOCK_COPY
STOCK_REMOVE = gtk.STOCK_REMOVE
STOCK_MOVE = gtk.STOCK_PASTE
STOCK_INIT = STOCK_APPLIED
STOCK_LOG = gtk.STOCK_FIND
STOCK_RECOVERY = gtk.STOCK_REVERT_TO_SAVED
STOCK_RENAME = gtk.STOCK_PASTE
STOCK_CONFIG = gtk.STOCK_PREFERENCES
STOCK_SERVE = gtk.STOCK_EXECUTE
STOCK_SHELVE = gtk.STOCK_EXECUTE
STOCK_STATUS = gtk.STOCK_INFO
STOCK_SYNCH = gtk.STOCK_REFRESH
STOCK_GUESS = gtk.STOCK_DIALOG_QUESTION
STOCK_ROLLBACK = gtk.STOCK_UNDO
STOCK_BACKOUT = gtk.STOCK_MEDIA_REWIND
STOCK_STATUS_OK = gtk.STOCK_APPLY
STOCK_STATUS_NOT_OK = gtk.STOCK_CANCEL
STOCK_NEW_PATCH = gtk.STOCK_ADD
STOCK_GRAPH = gtk.STOCK_FILE
STOCK_REVERT = gtk.STOCK_UNDO
STOCK_EDIT = gtk.STOCK_EDIT

_icon_name_list = \
    [ STOCK_COMMIT, STOCK_DIFF, STOCK_POP_PATCH, STOCK_PUSH_PATCH,
      STOCK_FOLD_PATCH, STOCK_FINISH_PATCH, STOCK_IMPORT_PATCH, STOCK_APPLIED,
      STOCK_MERGE, STOCK_TAG, STOCK_BRANCH,
    ]

# first look in the source directory
libdir = os.path.join(sys.path[0], "pixmaps")
if not os.path.exists(libdir) or not os.path.isdir(libdir):
    tailend = os.path.join("share", "pixmaps", "gwsmhg")
    prefix = sys.path[0]
    while prefix:
        libdir = os.path.join(prefix, tailend)
        if os.path.exists(libdir) and os.path.isdir(libdir):
            break
        prefix = os.path.dirname(prefix)

app_icon_file = os.path.join(os.path.dirname(libdir), APP_ICON + os.extsep + "png")

factory = gtk.IconFactory()

def make_pixbuf(name):
    #pb = gtk.gdk.pixbuf_new_from_xpm_data(xpm)
    return gtk.gdk.pixbuf_new_from_file(os.path.join(libdir, name + os.extsep + "png"))

for name in _icon_name_list:
    factory.add(name, gtk.IconSet(make_pixbuf(name)))

factory.add_default()

