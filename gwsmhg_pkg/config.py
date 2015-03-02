### Copyright (C) 2005-2011 Peter Williams <peter_ono@users.sourceforge.net>

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

import os
import gobject
import gtk
import fnmatch
import collections

from gwsmhg_pkg import dialogue
from gwsmhg_pkg import gutils
from gwsmhg_pkg import utils
from gwsmhg_pkg import table
from gwsmhg_pkg import urlops
from gwsmhg_pkg import tlview

PARow = collections.namedtuple('PARow', [_('Alias'), _('Path')])

PATH_ALIAS_MODEL_DESCR = PARow(Alias=gobject.TYPE_STRING, Path=gobject.TYPE_STRING)

PATH_ALIAS_TABLE_DESCR = tlview.ViewTemplate(
    properties={
        'enable-grid-lines' : False,
        'reorderable' : False,
        'rules_hint' : False,
        'headers-visible' : True,
    },
    selection_mode=gtk.SELECTION_SINGLE,
    columns=[
        tlview.Column(
            title=_('Alias'),
            properties={'expand': False, 'resizable' : True},
            cells=[
                tlview.Cell(
                    creator=tlview.CellCreator(
                        function=gtk.CellRendererText,
                        expand=False,
                        start=True
                    ),
                    properties={'editable' : True},
                    renderer=None,
                    attributes = {'text' : tlview.model_col(PATH_ALIAS_MODEL_DESCR, _('Alias'))}
                ),
            ],
        ),
        tlview.Column(
            title=_('Path'),
            properties={'expand': False, 'resizable' : True},
            cells=[
                tlview.Cell(
                    creator=tlview.CellCreator(
                        function=gtk.CellRendererText,
                        expand=False,
                        start=True
                    ),
                    properties={'editable' : False},
                    renderer=None,
                    attributes = {'text' : tlview.model_col(PATH_ALIAS_MODEL_DESCR, _('Path'))}
                ),
            ],
        ),
    ]
)

CONFIG_DIR_NAME = os.sep.join([utils.HOME, ".gwsmhg.d"])
SAVED_WS_FILE_NAME = os.sep.join([CONFIG_DIR_NAME, "workspaces"])
SAVED_REPO_FILE_NAME = os.sep.join([CONFIG_DIR_NAME, "repositories"])

if not os.path.exists(CONFIG_DIR_NAME):
    os.mkdir(CONFIG_DIR_NAME, 0o775)

def append_saved_ws(path, alias=None):
    fobj = open(SAVED_WS_FILE_NAME, 'a')
    abbr_path = utils.path_rel_home(path)
    if not alias:
        alias = os.path.basename(path)
    fobj.write(os.pathsep.join([alias, abbr_path]))
    fobj.write(os.linesep)
    fobj.close()

_KEYVAL_ESCAPE = gtk.gdk.keyval_from_name('Escape')

class AliasPathTable(table.Table):
    def __init__(self, saved_file):
        self._saved_file = saved_file
        table.Table.__init__(self, model_descr=PATH_ALIAS_MODEL_DESCR,
                             table_descr=PATH_ALIAS_TABLE_DESCR,
                             size_req=(480, 160))
        self.view.register_modification_callback(self.save_to_file)
        self.connect("key_press_event", self._key_press_cb)
        self.connect('button_press_event', self._handle_button_press_cb)
        self.set_contents()
    def _extant_path(self, path):
        return os.path.exists(os.path.expanduser(path))
    def _fetch_contents(self):
        extant_ap_list = []
        if not os.path.exists(self._saved_file):
            return []
        fobj = open(self._saved_file, 'r')
        lines = fobj.readlines()
        fobj.close()
        for line in lines:
            data = PARow(*line.strip().split(os.pathsep, 1))
            if data in extant_ap_list:
                continue
            if self._extant_path(data.Path):
                extant_ap_list.append(data)
        extant_ap_list.sort()
        self._write_list_to_file(extant_ap_list)
        return extant_ap_list
    def _write_list_to_file(self, ap_list):
        fobj = open(self._saved_file, 'w')
        for alpth in ap_list:
            fobj.write(os.pathsep.join(alpth))
            fobj.write(os.linesep)
        fobj.close()
    def _same_paths(self, path1, path2):
        return utils.samefile(os.path.expanduser(path1), path2)
    def _default_alias(self, path):
        return os.path.basename(path)
    def _abbrev_path(self, path):
        return utils.path_rel_home(path)
    def add_ap(self, path, alias=""):
        if self._extant_path(path):
            model_iter = self.model.get_iter_first()
            while model_iter:
                if self._same_paths(self.model.get_labelled_value(model_iter, _('Path')), path):
                    if alias:
                        self.model.set_labelled_value(model_iter, _('Alias'), alias)
                    return
                model_iter = self.model.iter_next(model_iter)
            if not alias:
                alias = self._default_alias(path)
            data = PARow(Path=self._abbrev_path(path), Alias=alias)
            self.model.append(data)
            self.save_to_file()
    def save_to_file(self, _arg=None):
        ap_list = self.get_contents()
        self._write_list_to_file(ap_list)
    def get_selected_ap(self):
        data = self.get_selected_data_by_label([_('Path'), _('Alias')])
        if not data:
            return False
        return data[0]
    def _handle_button_press_cb(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 2:
                self.view.get_selection().unselect_all()
                return True
        return False
    def _key_press_cb(self, widget, event):
        if event.keyval == _KEYVAL_ESCAPE:
            self.view.get_selection().unselect_all()
            return True
        return False

class WSPathTable(AliasPathTable):
    def __init__(self):
        AliasPathTable.__init__(self, SAVED_WS_FILE_NAME)

class PathSelectDialog(dialogue.Dialog):
    def __init__(self, create_table, label, parent=None):
        dialogue.Dialog.__init__(self, title=_('gwsmg: Select %s') % label, parent=parent,
                                 flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                                 buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                          gtk.STOCK_OK, gtk.RESPONSE_OK)
                                )
        hbox = gtk.HBox()
        self.ap_table = create_table()
        hbox.pack_start(self.ap_table)
        self.vbox.pack_start(hbox)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label("%s:" % label), expand=False)
        self._path = gutils.MutableComboBoxEntry()
        self._path.child.set_width_chars(32)
        self._path.child.connect("activate", self._path_cb)
        hbox.pack_start(self._path, expand=True, fill=True)
        self._browse_button = gtk.Button(label=_('_Browse'))
        self._browse_button.connect("clicked", self._browse_cb)
        hbox.pack_start(self._browse_button, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        self.show_all()
        self.ap_table.view.get_selection().unselect_all()
        self.ap_table.view.get_selection().connect("changed", self._selection_cb)
    def _selection_cb(self, _selection=None):
        alpth = self.ap_table.get_selected_ap()
        if alpth:
            self._path.set_text(alpth[0])
    def _path_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def _browse_cb(self, button=None):
        dirname = dialogue.ask_dir_name(_('gwsmhg: Browse for Directory'), existing=True, parent=self)
        if dirname:
            self._path.set_text(utils.path_rel_home(dirname))
    def get_path(self):
        return os.path.expanduser(self._path.get_text())

class WSOpenDialog(PathSelectDialog):
    def __init__(self, parent=None):
        PathSelectDialog.__init__(self, create_table=WSPathTable,
            label=_('Workspace/Directory'), parent=parent)

class RepoPathTable(AliasPathTable):
    def __init__(self):
        AliasPathTable.__init__(self, SAVED_REPO_FILE_NAME)
    def _extant_path(self, path):
        if urlops.parse_url(path).scheme:
            # for the time being treat all paths expressed as URLs as extant
            return True
        return AliasPathTable._extant_path(self, path)
    def _same_paths(self, path1, path2):
        up1 = urlops.parse_url(path1)
        if up1.scheme:
            up2 = urlops.parse_url(path2)
            if up2.scheme:
                # compare normalized URLs for better confidence in result
                return up1.geturl() == up2.geturl()
            else:
                return False
        elif urlops.parse_url(path2).scheme:
            return False
        else:
            return AliasPathTable._same_paths(self, path1, path2)
    def _default_alias(self, path):
        urlp = urlops.parse_url(path)
        if not urlp.scheme:
            return AliasPathTable._default_alias(self, path)
        else:
            return os.path.basename(urlp.path)

class RepoSelectDialog(PathSelectDialog):
    def __init__(self, parent=None):
        PathSelectDialog.__init__(self, create_table=RepoPathTable,
            label=_('Repository'), parent=parent)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(_('As:')))
        self._target = gutils.EntryWithHistory()
        self._target.set_width_chars(32)
        self._target.connect("activate", self._target_cb)
        hbox.pack_start(self._target, expand=True, fill=True)
        self._default_button = gtk.Button(label=_('_Default'))
        self._default_button.connect("clicked", self._default_cb)
        hbox.pack_start(self._default_button, expand=False, fill=False)
        self.vbox.pack_start(hbox, expand=False, fill=False)
        self.show_all()
    def _target_cb(self, entry=None):
        self.response(gtk.RESPONSE_OK)
    def _get_default_target(self):
        rawpath = self.get_path()
        urp = urlops.parse_url(rawpath)
        if urp.scheme:
            path = urp.path
        else:
            path = rawpath
        return os.path.basename(path)
    def _default_cb(self, button=None):
        dflt = self._get_default_target()
        self._target.set_text(dflt)
    def get_target(self):
        target = self._target.get_text()
        if not target:
            target = self._get_default_target()
        return target

# Manage external editors

EDITORS_THAT_NEED_A_TERMINAL = ["vi", "joe"]
DEFAULT_EDITOR = "gedit"
DEFAULT_TERMINAL = "gnome-terminal"
if os.name == 'nt' or os.name == 'dos':
    DEFAULT_EDITOR = "notepad"

for env in ['VISUAL', 'EDITOR']:
    try:
        ed = os.environ[env]
        if ed != "":
            DEFAULT_EDITOR = ed
            break
    except KeyError:
        pass

for env in ['COLORTERM', 'TERM']:
    try:
        term = os.environ[env]
        if term != "":
            DEFAULT_TERMINAL = term
            break
    except KeyError:
        pass

EDITOR_GLOB_FILE_NAME = os.sep.join([CONFIG_DIR_NAME, "editors"])

def _read_editor_defs(edeff=EDITOR_GLOB_FILE_NAME):
    editor_defs = []
    if os.path.isfile(edeff):
        for line in open(edeff, 'r').readlines():
            eqi = line.find('=')
            if eqi < 0:
                continue
            glob = line[:eqi].strip()
            edstr = line[eqi+1:].strip()
            editor_defs.append([glob, edstr])
    return editor_defs

def _write_editor_defs(edefs, edeff=EDITOR_GLOB_FILE_NAME):
    fobj = open(edeff, 'w')
    for edef in edefs:
        fobj.write('='.join(edef))
        fobj.write(os.linesep)
    fobj.close()

if not os.path.exists(EDITOR_GLOB_FILE_NAME):
    _write_editor_defs([('*', DEFAULT_EDITOR)])

def _assign_extern_editors(file_list, edeff=EDITOR_GLOB_FILE_NAME):
    ed_assignments = {}
    unassigned_files = []
    editor_defs = _read_editor_defs(edeff)
    for fobj in file_list:
        assigned = False
        for globs, edstr in editor_defs:
            for glob in globs.split(os.pathsep):
                if fnmatch.fnmatch(fobj, glob):
                    if edstr in ed_assignments:
                        ed_assignments[edstr].append(fobj)
                    else:
                        ed_assignments[edstr] = [fobj]
                    assigned = True
                    break
            if assigned:
                break
        if not assigned:
            unassigned_files.append(fobj)
    return ed_assignments, unassigned_files

def assign_extern_editors(file_list):
    ed_assignments, unassigned_files = _assign_extern_editors(file_list, EDITOR_GLOB_FILE_NAME)
    if unassigned_files:
        if DEFAULT_EDITOR in ed_assignments:
            ed_assignments[DEFAULT_EDITOR] += unassigned_files
        else:
            ed_assignments[DEFAULT_EDITOR] = unassigned_files
    return ed_assignments

GERow = collections.namedtuple('GERow', ['globs', 'editor'])

EDITOR_GLOB_MODEL_DESCR = GERow(globs=gobject.TYPE_STRING, editor=gobject.TYPE_STRING)

EDITOR_GLOB_TABLE_DESCR = tlview.ViewTemplate(
    properties={
        'enable-grid-lines' : True,
        'reorderable' : True,
    },
    selection_mode=gtk.SELECTION_MULTIPLE,
    columns=[
        tlview.Column(
            title=_('File Pattern(s)'),
            properties={'expand' : True},
            cells=[
                tlview.Cell(
                    creator=tlview.CellCreator(
                        function=gtk.CellRendererText,
                        expand=False,
                        start=True
                    ),
                    properties={'editable' : True},
                    renderer=None,
                    attributes={'text' : tlview.model_col(EDITOR_GLOB_MODEL_DESCR, 'globs')}
                ),
            ],
        ),
        tlview.Column(
            title=_('Editor Command'),
            properties={'expand' : True},
            cells=[
                tlview.Cell(
                    creator=tlview.CellCreator(
                        function=gtk.CellRendererText,
                        expand=False,
                        start=True
                    ),
                    properties={'editable' : True},
                    renderer=None,
                    attributes={'text' : tlview.model_col(EDITOR_GLOB_MODEL_DESCR, 'editor')}
                ),
            ],
        ),
    ]
)

class EditorAllocationTable(table.Table):
    def __init__(self, edeff=EDITOR_GLOB_FILE_NAME):
        table.Table.__init__(self, EDITOR_GLOB_MODEL_DESCR,
                             EDITOR_GLOB_TABLE_DESCR, (320, 160))
        self._edeff = edeff
        self.set_contents()
    def _fetch_contents(self):
        return _read_editor_defs(self._edeff)
    def apply_changes(self):
        _write_editor_defs(edefs=self.get_contents(), edeff=self._edeff)
        self.set_contents()

class EditorAllocationDialog(dialogue.Dialog):
    def __init__(self, edeff=EDITOR_GLOB_FILE_NAME, parent=None):
        dialogue.Dialog.__init__(self, title=_('gwsmg: Editor Allocation'), parent=parent,
                                 flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                 buttons=(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE,
                                          gtk.STOCK_OK, gtk.RESPONSE_OK)
                                )
        self._table = EditorAllocationTable(edeff=edeff)
        self._buttons = gutils.ActionHButtonBox(list(self._table.action_groups.values()))
        self.vbox.pack_start(self._table)
        self.vbox.pack_start(self._buttons, expand=False)
        self.connect("response", self._handle_response_cb)
        self.show_all()
        self._table.view.get_selection().unselect_all()
    def _handle_response_cb(self, dialog, response_id):
        if response_id == gtk.RESPONSE_OK:
            self._table.apply_changes()
        self.destroy()
