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
import os, setup_generic

DATA_FILES = setup_generic.PIXMAPS

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
    scripts = setup_generic.SCRIPTS,
    packages = setup_generic.PACKAGES,
    data_files = DATA_FILES
)

