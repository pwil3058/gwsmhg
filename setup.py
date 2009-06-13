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
### Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from distutils.core import setup
import os

VERSION='0.3.1'

LONG_DESCRIPTION =\
'''
Mercurial (hg) is a distributed source control tool and Mercurial Queues (mq)
is a patch management tool extension to hg. gwsmhg is a PyGTK GUI wrapper for
hg and mq allowing them to be used in an integrated manner to manage a work
space.
'''

pixmaps = []
for name in ['stock_commit.png', 'stock_diff.png', 'stock_applied.png',
             'stock_finish_patch.png', 'stock_fold_patch.png',
             'stock_import_patch.png', 'stock_pop_patch.png',
             'stock_push_patch.png', 'stock_merge.png', 'stock_tag.png',
             'stock_branch.png',
            ]:
    pixmaps.append(os.sep.join(["pixmaps", name]))

LICENSE='GNU General Public License (GPL) Version 2.0'

setup(name='gwsmhg',
      version=VERSION,
      description='a PyGTK GUI wrapper for hg and mq',
      long_description=LONG_DESCRIPTION,
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: %s' % LICENSE,
          'Programming Language :: Python',
          'Topic :: Software Development :: Source Control',
          ],
      license=LICENSE,
      author='Peter Williams',
      author_email='peter_ono@users.sourceforge.net',
      url='http://gwsmhg.sourceforge.net/',
      scripts=['gwsmhg'],
      packages=['gwsmhg_pkg'],
      data_files=[('share/pixmaps', ['gwsmhg.png']),
                  ('share/pixmaps/gwsmhg', pixmaps),
                  ('share/doc/gwsmhg-' + VERSION, ['COPYING']),
                  ('share/applications', ['gwsmhg.desktop'])]
      )

