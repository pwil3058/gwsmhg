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

class notification_cb:
    def __init__(self, events, cb):
        self._events = events
        self._cb = cb

_notification_cbs = []

def add_notification_cb(events, cb):
    ncb = notification_cb(events, cb)
    _notification_cbs.append(ncb)
    return ncb

def del_notification_cb(ncb):
    index = _notification_cbs.index(ncb)
    if index >= 0:
        del _notification_cbs[index]

def del_notification_cbs(ncb_list):
    for ncb in ncb_list:
        del_notification_cb(ncb)

def notify_events(events, data=None):
    invalid_cbs = []
    for ncb in _notification_cbs:
        if ncb._events & events:
            try:
                if data:
                    ncb._cb(data)
                else:
                    ncb._cb()
            except:
                invalid_cbs.append(ncb)
    del_notification_cbs(invalid_cbs)

class Listener:
    def __init__(self):
        try:
            len(self._listener_cbs)
            print "already inited", self
        except:
            self._listener_cbs = []
        self.connect('destroy', self._listener_destroy_cb)
    def add_notification_cb(self, events, cb):
        self._listener_cbs.append(add_notification_cb(events, cb))
    def _listener_destroy_cb(self, widget):
        del_notification_cbs(self._listener_cbs)
