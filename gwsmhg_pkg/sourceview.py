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

try:
    import gtksourceview
    
    class SourceView(gtksourceview.SourceView):
        def __init__(self, buffer=None):
            gtksourceview.SourceView.__init__(self, buffer=buffer)
    class SourceTagTable(gtksourceview.SourceTagTable):
        def __init__(self):
            gtksourceview.SourceTagTable.__init__(self)
    class SourceBuffer(gtksourceview.SourceBuffer):
        def __init__(self, table=None):
            gtksourceview.SourceBuffer.__init__(self, table=table)

except ImportError:
    import gtk
    
    class SourceView(gtk.TextView):
        def __init__(self, buffer=None):
            gtk.TextView.__init__(self, buffer=buffer)
        def set_margin(self, val):
            pass
        def set_show_margin(self, val):
            pass
    class SourceTagTable(gtk.TextTagTable):
        def __init__(self):
            gtk.TextTagTable.__init__(self)
    class SourceBuffer(gtk.TextBuffer):
        def __init__(self, table=None):
            gtk.TextBuffer.__init__(self, table=table)
        def begin_not_undoable_action(self):
            pass
        def end_not_undoable_action(self):
            pass

