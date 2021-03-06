#!/usr/bin/env python
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

from distutils.core import setup
import py2exe
import os, setup_generic

os.environ['PATH'] += ';gtk/lib;gtk/bin;lib/site-packages/cairo'

DATA_FILES = setup_generic.PIXMAPS + setup_generic.COPYRIGHT + \
             [('share/pixmaps', ['gwsmhg.ico'])]

setup(
    name = setup_generic.NAME,
    version = setup_generic.VERSION,
    description = setup_generic.DESCRIPTION,
    long_description = setup_generic.LONG_DESCRIPTION,
    classifiers = setup_generic.CLASSIFIERS,
    license = setup_generic.LICENSE,
    author = setup_generic.AUTHOR,
    author_email = setup_generic.AUTHOR_EMAIL,
    url = setup_generic.URL,
    windows = [
        {
            'script': setup_generic.SCRIPTS[0],
            'icon_resources': [(1, 'gwsmhg.ico')],
        }
    ],
    packages = setup_generic.PACKAGES,
    data_files = DATA_FILES,
    options = {
        'py2exe': {
            'packages':'encodings',
            'includes': 'cairo, pango, pangocairo, atk, gobject',
        }
    },
)

