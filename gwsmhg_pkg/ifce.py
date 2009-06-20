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

SCM = None
PM = None

from gwsmhg_pkg import console

log = None

def init(ifce_module):
    global SCM, PM
    SCM = ifce_module.SCMInterface()
    PM = ifce_module.PMInterface()

def create_log(busy_indicator):
    global log
    log = console.ConsoleLog(busy_indicator)
    return log
