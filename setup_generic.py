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

import glob

NAME = 'gwsmhg'

VERSION = '0.9'

DESCRIPTION = 'a PyGTK GUI wrapper for hg and mq'

LONG_DESCRIPTION =\
'''
Mercurial (hg) is a distributed source control tool and Mercurial Queues (mq)
is a patch management tool extension to hg. gwsmhg is a PyGTK GUI wrapper for
hg and mq allowing them to be used in an integrated manner to manage a work
space.
'''

pixmaps = glob.glob('pixmaps/*.png')

PIXMAPS = [('share/pixmaps', ['gwsmhg.png']), ('share/pixmaps/gwsmhg', pixmaps)]

COPYRIGHT = [('share/doc/gwsmhg', ['COPYING', 'copyright'])]

LICENSE = 'GNU General Public License (GPL) Version 2.0'

CLASSIFIERS = [
    'Development Status :: Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: %s' % LICENSE,
    'Programming Language :: Python',
    'Topic :: Software Development :: Source Control',
    'Operating System :: MacOS :: MacOS X',
    'Operating System :: Microsoft :: Windows',
    'Operating System :: POSIX',
]

AUTHOR = 'Peter Williams'

AUTHOR_EMAIL = 'peter_ono@users.sourceforge.net'

URL = 'http://gwsmhg.sourceforge.net/'

SCRIPTS = ['gwsmhg']

PACKAGES = ['gwsmhg_pkg']

