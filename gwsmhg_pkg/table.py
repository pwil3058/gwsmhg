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

from gwsmhg_pkg import gutils, actions, tlview, icons

class Model(tlview.ListStore):
    def __init__(self, descr):
        tlview.ListStore.__init__(self, descr)

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
        self.view = tlview.View(table_descr, self.model)
        self.seln = self.view.get_selection()
        if size_req:
            self.view.set_size_request(*size_req)
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
                ('table_insert_row', icons.STOCK_INSERT, '_Insert', None,
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
    def _row_inserted_cb(self, model, path, model_iter):
        self._set_modified(True)
    def _selection_changed_cb(self, selection):
        rows = selection.count_selected_rows()
        self.action_groups[SELECTION].set_sensitive(rows > 0)
        self.action_groups[NO_SELECTION].set_sensitive(rows == 0)
        self.action_groups[UNIQUE_SELECTION].set_sensitive(rows == 1)
    def _undo_changes_acb(self, _action=None):
        self.set_contents()
    def _apply_changes_acb(self, _action=None):
        self.apply_changes()
    def _add_row_acb(self, _action=None):
        model_iter = self.model.append(None)
        self.view.get_selection().select_iter(model_iter)
        return
    def _delete_selection_acb(self, _action=None):
        model, paths = self.seln.get_selected_rows()
        iters = []
        for path in paths:
            iters.append(model.get_iter(path))
        for model_iter in iters:
            model.remove(model_iter)
    def _insert_row_acb(self, _action=None):
        model, paths = self.seln.get_selected_rows()
        if not paths:
            return
        model_iter = self.model.insert_before(model.get_iter(paths[0]), None)
        self.view.get_selection().select_iter(model_iter)
        return
    def get_selected_data(self, columns=None):
        store, selected_rows = self.seln.get_selected_rows()
        if not columns:
            columns = list(range(store.get_n_columns()))
        result = []
        for row in selected_rows:
            model_iter = store.get_iter(row)
            assert model_iter is not None
            result.append(store.get_values(model_iter, columns))
        return result
    def get_selected_data_by_label(self, labels):
        columns = self.model.get_cols(labels)
        return self.get_selected_data(columns)

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
        self.view = tlview.View(table_descr, self.model)
        self.seln = self.view.get_selection()
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
            columns = list(range(store.get_n_columns()))
        result = []
        for row in selected_rows:
            model_iter = store.get_iter(row)
            assert model_iter is not None
            result.append(store.get_values(model_iter, columns))
        return result
    def get_selected_keys(self, keycol=0):
        store, selected_rows = self.seln.get_selected_rows()
        keys = []
        for row in selected_rows:
            model_iter = store.get_iter(row)
            assert model_iter is not None
            keys.append(store.get_value(model_iter, keycol))
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
        model_iter = self.model.get_row_with_key_value(key_label, key_value)
        if not model_iter:
            return False
        self.seln.select_iter(model_iter)
        path = self.model.get_path(model_iter)
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
        self.add_conditional_actions(actions.IN_REPO,
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
    def refresh_contents_if_mapped(self, *_args):
        if self.is_mapped:
            self.refresh_contents()
        else:
            self._needs_refresh = True
    def _refresh_contents_acb(self, _action):
        self.show_busy()
        self.refresh_contents()
        self.unshow_busy()
    def update_for_chdir(self, _arg=None):
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
