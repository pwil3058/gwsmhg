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

import gtk
from gwsmhg_pkg import gutils, actions

# Model description is [ (label, type), ... ]

def model_col(descr, label):
    col = 0
    for col in range(len(descr)):
        if label == descr[col][0]:
            return col
    return None

class Model(gtk.ListStore):
    def __init__(self, descr):
        self._col_labels, self._col_types = self._extract_labels_and_types(descr)
        apply(gtk.ListStore.__init__, [self] + self._col_types)
    def _extract_labels_and_types(self, descr):
        labels = []
        types = []
        for label, type in descr:
            labels.append(label)
            types.append(type)
        return (labels, types)
    def get_col(self, label):
        return self._col_labels.index(label)
    def get_cols(self, labels):
        cols = []
        for label in labels:
            cols.append(self._col_labels.index(label))
        return cols
    def get_values(self, iter, cols):
        return apply(self.get, [iter] + cols)
    def set_values(self, iter, col_vals):
        return apply(self.get, [iter] + col_vals)
    def get_row(self, iter):
        return self.get_values(iter, range(self.get_n_columns()))
    def get_labelled_value(self, iter, label):
        return self.get_value(iter, self.get_col(label))
    def get_labelled_values(self, iter, labels):
        return self.get_values(iter, self.get_cols(labels))
    def set_labelled_value(self, iter, label, value):
        self.set_value(iter, self.get_col(label), value)
    def set_labelled_values(self, iter, label_values):
        col_values = []
        for index in len(label_values):
            if (index % 2) == 0:
                col_values.append(self.get_col(label_values[index]))
            else:
                col_values.append(label_values[index])
        self.set_values(iter, col_values)
    def append_contents(self, rows):
        for row in rows:
            self.append(row)
    def set_contents(self, rows):
        self.clear()
        for row in rows:
            self.append(row)
    def get_contents(self):
        contents = []
        iter = self.get_iter_first()
        while iter:
            contents.append(self.get_row(iter))
            iter = self.iter_next(iter)
        return contents
    def get_row_with_key_value(self, key_label, key_value):
        index = self.get_col(key_label)
        iter = self.get_iter_first()
        while iter:
            if self.get_value(iter, index) == key_value:
                return iter
            else:
                iter = self.iter_next(iter)
        return None

# Table description is [ properties, selection_mode, [column_descr, ...] ]
# Properties is [ (property_name, value), ... ]
# Selection_mode is one of gtk.SELECTION_NONE, gtk.SELECTION_SINGLE,
#   gtk.SELECTION_BROWSE or gtk.SELECTION_MULTIPLE
# Column_descr is [
#   title, properties, [cell_renderer, ...]
# ]
# Cell_renderer is [
#   creation_data, properties, cell_renderer_func, attributes
# ]
# Creation_data is [ creation_function, expand, start ]
# Attributes is [ (attribute_name, model_column_number), ... ]
# Edit_cb_descr is [ edit_cb_function, edit_cb_data ]

_T_PROPS = 0
_T_SEL_MODE = 1
_T_COLS = 2
_P_NAME = 0
_P_VAL = 1
_C_TITLE = 0
_C_PROPS = 1
_C_CRS = 2
_CR_CREATE = 0
_CR_PROPS = 1
_CR_CELL_DATA_FUNC = 2
_CR_ATTRS = 3
_A_NAME = 0
_A_INDEX = 1
_CR_CREATE_FUNC = 0
_CR_CREATE_EXPAND = 1
_CR_PACK_START = 2

class View(gtk.TreeView):
    def __init__(self, descr, model=None):
        gtk.TreeView.__init__(self, model)
        for prop in descr[_T_PROPS]:
            self.set_property(prop[_P_NAME], prop[_P_VAL])
        if descr[_T_SEL_MODE] is not None:
            self.get_selection().set_mode(descr[_T_SEL_MODE])
        self._view_col_dict = {}
        self._view_col_list = []
        for col_d in descr[_T_COLS]:
            self._view_add_column(col_d)
        self.connect("button_press_event", self._handle_button_press_cb)
        self._modified_cbs = []
    def _view_add_column(self, col_d):
        col = gtk.TreeViewColumn(col_d[_C_TITLE])
        col_cells = (col, [])
        self._view_col_dict[col_d[_C_TITLE]] = col_cells
        self._view_col_list.append(col_cells)
        self.append_column(col)
        for prop in col_d[_C_PROPS]:
            col.set_property(prop[_P_NAME], prop[_P_VAL])
        for cell_d in col_d[_C_CRS]:
            self._view_add_cell(col, cell_d)
    def _view_add_cell(self, col, cell_d):
        cell = cell_d[_CR_CREATE][_CR_CREATE_FUNC]()
        self._view_col_dict[col.get_title()][1].append(cell)
        if cell_d[_CR_CREATE][_CR_CREATE_EXPAND] is not None:
            if cell_d[_CR_CREATE][_CR_PACK_START]:
                col.pack_start(cell, cell_d[_CR_CREATE][_CR_CREATE_EXPAND])
            else:
                col.pack_end(cell, cell_d[_CR_CREATE][_CR_CREATE_EXPAND])
        else:
            if cell_d[_CR_CREATE][_CR_PACK_START]:
                col.pack_start(cell)
            else:
                col.pack_end(cell)
        for prop in cell_d[_CR_PROPS]:
            cell.set_property(prop[_P_NAME], prop[_P_VAL])
        if cell_d[_CR_CELL_DATA_FUNC] is not None:
            col.set_cell_data_func(cell, cell_d[_CR_CELL_DATA_FUNC][0],
                                   cell_d[_CR_CELL_DATA_FUNC][1])
        for attr in cell_d[_CR_ATTRS]:
            col.add_attribute(cell, attr[_A_NAME], attr[_A_INDEX])
            if attr[_A_NAME] == 'text':
                cell.connect('edited', self._cell_text_edited_cb, attr[_A_INDEX])
            elif attr[_A_NAME] == 'active':
                cell.connect('toggled', self._cell_toggled_cb, attr[_A_INDEX])
    def _notify_modification(self):
        for cb, data in self._modified_cbs:
            if data is None:
                cb()
            else:
                cb(data)
    def register_modification_callback(self, cb, data=None):
        self._modified_cbs.append([cb, data])
    def _handle_button_press_cb(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 2:
                self.get_selection().unselect_all()
                return True
        return False
    def _cell_text_edited_cb(self, cell, path, new_text, index):
        self.get_model()[path][index] = new_text
        self._notify_modification()
    def _cell_toggled_cb(self, cell, path, index):
        self.model[path][index] = cell.get_active()
        self._notify_modification()
    def get_col_with_title(self, title):
        return self._view_col_dict[title][0]
    def get_cell_with_title(self, title, index=0):
        return self._view_col_dict[title][1][index]
    def get_cell(self, col_index, cell_index=0):
        return self._view_col_list[col_index][1][cell_index]

ALWAYS_ON = 'table_always_on'
MODIFIED = 'table_modified'
NOT_MODIFIED = 'table_not_modified'
SELECTION = 'table_selection'
NO_SELECTION = 'table_no_selection'
UNIQUE_SELECTION = 'table_unique_selection'

TABLE_STATES = \
    [ALWAYS_ON, MODIFIED, NOT_MODIFIED, SELECTION, NO_SELECTION,
     UNIQUE_SELECTION]

class Table(gtk.VBox):
    def __init__(self, model_descr, table_descr, size_req=None):
        gtk.VBox.__init__(self)
        self.model = Model(model_descr)
        self.view = View(table_descr, self.model)
        self.seln = self.view.get_selection()
        if size_req:
            self.view.set_size_request(size_req[0], size_req[1])
        self.pack_start(gutils.wrap_in_scrolled_window(self.view))
        self.action_groups = {}
        for key in TABLE_STATES:
            self.action_groups[key] = gtk.ActionGroup(key)
        self.action_groups[ALWAYS_ON].add_actions(
            [
                ('table_add_row', gtk.STOCK_ADD, '_Add', None,
                 'Add a new entry to the table', self._add_row_acb),
            ])
        self.action_groups[MODIFIED].add_actions(
            [
                ('table_undo_changes', gtk.STOCK_UNDO, '_Undo', None,
                 'Undo unapplied changes', self._undo_changes_acb),
                ('table_apply_changes', gtk.STOCK_APPLY, '_Apply', None,
                 'Apply outstanding changes', self._apply_changes_acb),
            ])
        self.action_groups[SELECTION].add_actions(
            [
                ('table_delete_selection', gtk.STOCK_DELETE, '_Delete', None,
                 'Delete selected row(s)', self._delete_selection_acb),
                ('table_insert_row', gtk.STOCK_ADD, '_Insert', None,
                 'Insert a new entry before the selected row(s)', self._insert_row_acb),
            ])
        self._modified = False
        self.model.connect('row-inserted', self._row_inserted_cb)
        self.seln.connect('changed', self._selection_changed_cb)
        self.view.register_modification_callback(self._set_modified, True)
        self.seln.unselect_all()
        self._selection_changed_cb(self.seln)
    def _set_modified(self, val):
        self._modified = val
        self.action_groups[MODIFIED].set_sensitive(val)
        self.action_groups[NOT_MODIFIED].set_sensitive(not val)
    def _fetch_contents(self):
        pass # define in child
    def set_contents(self):
        self.model.set_contents(self._fetch_contents())
        self._set_modified(False)
    def get_contents(self):
        return self.model.get_contents()
    def apply_changes(self):
        pass # define in child
    def _row_inserted_cb(self, model, path, iter):
        self._set_modified(True)
    def _selection_changed_cb(self, selection):
        rows = selection.count_selected_rows()
        self.action_groups[SELECTION].set_sensitive(rows > 0)
        self.action_groups[NO_SELECTION].set_sensitive(rows == 0)
        self.action_groups[UNIQUE_SELECTION].set_sensitive(rows == 1)
    def _undo_changes_acb(self, action=None):
        self.set_contents()
    def _apply_changes_acb(self, action=None):
        self.apply_changes()
    def _add_row_acb(self, action=None):
        iter = self.model.append(None)
        self.view.get_selection().select_iter(iter)
        return
    def _delete_selection_acb(self, action=None):
        model, paths = self.seln.get_selected_rows()
        iters = []
        for path in paths:
            iters.append(model.get_iter(path))
        for iter in iters:
            model.remove(iter)
    def _insert_row_acb(self, action=None):
        model, paths = self.seln.get_selected_rows()
        if not paths:
            return
        iter = self.model.insert_before(model.get_iter(paths[0]), None)
        self.view.get_selection().select_iter(iter)
        return
    def get_selected_data(self, columns=None):
        store, selected_rows = self.seln.get_selected_rows()
        if not columns:
            columns = range(store.get_n_columns())
        list = []
        for row in selected_rows:
            iter = store.get_iter(row)
            assert iter is not None
            list.append(store.get_values(iter, columns))
        return list

from gwsmhg_pkg import dialogue

class TableWithAGandUI(gtk.VBox, actions.AGandUIManager, dialogue.BusyIndicatorUser):
    def __init__(self, model_descr, table_descr, popup=None, scroll_bar=True,
                 busy_indicator=None, size_req=None):
        self._popup = popup
        gtk.VBox.__init__(self)
        dialogue.BusyIndicatorUser.__init__(self, busy_indicator)
        self.header = gutils.SplitBar()
        self.pack_start(self.header, expand=False)
        self.model = Model(model_descr)
        self.view = View(table_descr, self.model)
        actions.AGandUIManager.__init__(self, self.view.get_selection())
        if size_req:
            self.view.set_size_request(size_req[0], size_req[1])
        if scroll_bar:
            self.pack_start(gutils.wrap_in_scrolled_window(self.view))
        else:
            self.pack_start(self.view)
        self.view.connect("button_press_event", self._handle_button_press_cb)
        self.view.connect("key_press_event", self._handle_key_press_cb)
    def _handle_button_press_cb(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 3 and self._popup:
                menu = self.ui_manager.get_widget(self._popup)
                menu.popup(None, None, None, event.button, event.time)
                return True
            elif event.button == 2:
                self.seln.unselect_all()
                return True
        return False
    def _handle_key_press_cb(self, widget, event):
        if event.keyval == gtk.gdk.keyval_from_name('Escape'):
            self.seln.unselect_all()
            return True
        return False
    def _fetch_contents(self):
        pass # define in child
    def set_contents(self):
        self.show_busy()
        self.view.set_model(None)
        self.model.set_contents(self._fetch_contents())
        self.view.set_model(self.model)
        self.view.columns_autosize()
        self.seln.unselect_all()
        self.unshow_busy()
    def get_contents(self):
        return self.model.get_contents()
    def get_selected_data(self, columns=None):
        store, selected_rows = self.seln.get_selected_rows()
        if not columns:
            columns = range(store.get_n_columns())
        list = []
        for row in selected_rows:
            iter = store.get_iter(row)
            assert iter is not None
            list.append(store.get_values(iter, columns))
        return list
    def get_selected_keys(self, keycol=0):
        store, selected_rows = self.seln.get_selected_rows()
        keys = []
        for row in selected_rows:
            iter = store.get_iter(row)
            assert iter is not None
            keys.append(store.get_value(iter, keycol))
        return keys
    def get_selected_data_by_label(self, labels):
        return self.get_selected_data(self.model.get_cols(labels))
    def get_selected_keys_by_label(self, label):
        return self.get_selected_keys(self.model.get_col(label))
    def get_selected_key(self, keycol=0):
        keys = self.get_selected_keys(keycol)
        assert len(keys) <= 1
        if keys:
            return keys[0]
        else:
            return None
    def get_selected_key_by_label(self, label):
        return self.get_selected_key(self.model.get_col(label))
    def select_and_scroll_to_row_with_key_value(self, key_label, key_value):
        iter = self.model.get_row_with_key_value(key_label, key_value)
        if not iter:
            return False
        self.seln.select_iter(iter)
        path = self.model.get_path(iter)
        self.view.scroll_to_cell(path, use_align=True, row_align=0.5)
        return True

class MapManagedTable(TableWithAGandUI, gutils.MappedManager):
    def __init__(self, model_descr, table_descr, popup=None, scroll_bar=True,
                 busy_indicator=None, size_req=None):
        TableWithAGandUI.__init__(self, model_descr=model_descr,
                                  table_descr=table_descr, popup=popup,
                                  busy_indicator=busy_indicator,
                                  size_req=size_req,
                                  scroll_bar=scroll_bar)
        gutils.MappedManager.__init__(self)
        self._needs_refresh = True
        self.add_conditional_actions(actions.ON_IN_REPO_SELN_INDEP,
            [
                ("table_refresh_contents", gtk.STOCK_REFRESH, "Refresh", None,
                 "Refresh the tables contents", self._refresh_contents_acb),
            ])
        from gwsmhg_pkg import ws_event
        self.add_notification_cb(ws_event.CHANGE_WD, self.update_for_chdir)
    def map_action(self):
        if self._needs_refresh:
            self.show_busy()
            self._refresh_contents()
            self.unshow_busy()
    def unmap_action(self):
        pass
    def _refresh_contents(self):
        self.set_contents()
        self._needs_refresh = False
    def set_contents(self):
        TableWithAGandUI.set_contents(self)
        self._needs_refresh = False
    def refresh_contents(self):
        self._refresh_contents()
        self.seln.unselect_all()
    def refresh_contents_if_mapped(self, *args):
        if self.is_mapped:
            self.refresh_contents()
        else:
            self._needs_refresh = True
    def _refresh_contents_acb(self, action):
        self.show_busy()
        self.refresh_contents()
        self.unshow_busy()
    def update_for_chdir(self, arg=None):
        self.show_busy()
        self.model.set_contents([])
        self.refresh_contents_if_mapped()
        self.unshow_busy()

#class AutoRefreshTableView(MapManagedTableView):
#    def __init__(self, descr, busy_indicator, sel_mode=gtk.SELECTION_SINGLE,
#                 perm_headers=False, bgnd=["white", "#F0F0F0"],
#                 auto_refresh_on=False, auto_refresh_interval=30000):
#        self.rtoc = RefreshController(is_on=auto_refresh_on, interval=auto_refresh_interval)
#        self._normal_interval = auto_refresh_interval
#        MapManagedTableView.__init__(self, descr=descr, sel_mode=sel_mode,
#            perm_headers=False, bgnd=bgnd, busy_indicator=busy_indicator)
#        self.rtoc.set_function(self._refresh_contents)
#        self.show_all()
#    def map_action(self):
#        MapManagedTableView.map_action(self)
#        self.rtoc.restart_cycle()
#    def unmap_action(self):
#        self.rtoc.stop_cycle()
#        MapManagedTableView.unmap_action(self)
#    def refresh_contents(self):
#        self.rtoc.stop_cycle()
#        self._refresh_contents()
#        self.rtoc.restart_cycle()
