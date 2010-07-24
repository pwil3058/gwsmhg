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

"""Provide mechanism for notifying components of events that require them
to update their displayed/cached data
"""

import gobject

FILE_MOD = 1
FILE_ADD = 2
FILE_DEL = 4
FILE_HGIGNORE = 8
REPO_MOD = 16
REPO_HGRC = 32
USER_HGRC = 64
CHANGE_WD = 128
CHECKOUT = 256
UNAPPLIED_PATCH_MOD = 512
PMIC_CHANGE = 1024

ALL_EVENTS = PMIC_CHANGE * 2 - 1
ALL_BUT_CHANGE_WD = ALL_EVENTS &  ~CHANGE_WD

FILE_CHANGES = FILE_MOD | FILE_ADD | FILE_DEL | FILE_HGIGNORE


_notification_cbs = []


def add_notification_cb(events, callback):
    """Add the given events and callback as tuple to the notification database.
    Return the tuple to the caller to facilitate deletion at a later time.
    """
    global _notification_cbs
    ncb = (events, callback)
    _notification_cbs.append(ncb)
    return ncb


def del_notification_cb(ncb):
    """Remove the given (events, callback) pair notification database."""
    global _notification_cbs
    index = _notification_cbs.index(ncb)
    if index >= 0:
        del _notification_cbs[index]


def del_notification_cbs(ncb_list):
    """Remove the (events, callback) pairs in the given list from the
    notification database.
    """
    for ncb in ncb_list:
        del_notification_cb(ncb)


def notify_events(events, data=None):
    """Notify interested objects of events that have occured."""
    invalid_cbs = []
    for registered_events, callback in _notification_cbs:
        if registered_events & events:
            try:
                if data:
                    callback(data)
                else:
                    callback()
            except StandardError:
                invalid_cbs.append((registered_events, callback))
    del_notification_cbs(invalid_cbs)


class Listener(gobject.GObject):
    """A base class for transient GTK object classes that wish to register
    event callbacks so that their callbacks are deleted when they are
    destroyed.
    """
    def __init__(self):
        gobject.GObject.__init__(self)
        self._listener_cbs = []
        self.connect('destroy', self._listener_destroy_cb)

    def add_notification_cb(self, events, callback):
        """Add the given events and callback as tuple to the notification
        database and record the tuple to facilitate deletion at a later time.
        """
        self._listener_cbs.append(add_notification_cb(events, callback))

    def _listener_destroy_cb(self, widget):
        """Remove all of my callbacks from the notification database"""
        del_notification_cbs(self._listener_cbs)

