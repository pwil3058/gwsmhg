#!/usr/bin/env python
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

from distutils.core import setup
import os

VERSION='0.1'

pixmaps = []
for name in ['stock_commit.png', 'stock_diff.png', 'stock_applied.png',
             'stock_finish_patch.png', 'stock_fold_patch.png',
             'stock_import_patch.png', 'stock_pop_patch.png',
             'stock_push_patch.png'
            ]:
    pixmaps.append(os.sep.join(["pixmaps", name]))

setup(name='gwsmhg',
      version=VERSION,
      description='a PyGTK GUI wrapper for hg and mq',
      author='Peter Williams',
      author_email='peter_ono@users.sourceforge.net',
      url='https://sourceforge.net/projects/gwsmhg/',
      scripts=['gwsmhg'],
      packages=['gwsmhg_pkg'],
      data_files=[('share/pixmaps', ['gwsmhg.png']),
                  ('share/pixmaps/gwsmhg', pixmaps),
                  ('share/doc/gwsmhg-' + VERSION, ['COPYING']),
                  ('share/applications', ['gwsmhg.desktop'])]
      )

