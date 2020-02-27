# -*- coding: utf-8 -*-
from gi.repository import Gtk, GLib, Gdk

from .theme_model import THEME_MODEL, get_theme_options_by_key
from .palette_cache import PaletteCache
from .color import (
    convert_theme_color_to_gdk, convert_gdk_to_theme_color,
)
from .gtk_helpers import GObjectABCMeta, g_abstractproperty, ScaledImage
from .config import FALLBACK_COLOR
from .i18n import _


def check_value_filter(value_filter_data, colorscheme):
    filter_results = []
    for key, values in value_filter_data.items():
        if not isinstance(values, list):
            values = [values, ]
        value_found = False
        for value in values:
            if colorscheme.get(key) == value:
                value_found = True
                continue
        filter_results.append(value_found)
    all_filters_passed = min(filter_results) is not False
    return all_filters_passed


class OomoxListBoxRow(Gtk.ListBoxRow, metaclass=GObjectABCMeta):

    key = None
    value = None
    changed_signal = None
    callback = None
    value_widget = None
    hbox = None

    @g_abstractproperty
    def set_value(self, value):
        pass

    def __init__(self, display_name, key, callback, value_widget):
        super().__init__()

        self.callback = callback
        self.key = key

        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=50)
        self.add(self.hbox)
        label = Gtk.Label(label=display_name, xalign=0)
        self.hbox.pack_start(label, True, True, 0)

        self.value_widget = value_widget
        self.hbox.pack_start(self.value_widget, False, True, 0)

    def disconnect_changed_signal(self):
        if self.changed_signal:
            self.value_widget.disconnect(self.changed_signal)


class NumericListBoxRow(OomoxListBoxRow):

    @g_abstractproperty
    def on_value_changed(self, widget):
        pass

    def connect_changed_signal(self):
        self.changed_signal = self.value_widget.connect("value-changed", self.on_value_changed)

    def set_value(self, value):
        self.disconnect_changed_signal()
        self.value = value
        self.value_widget.set_value(value)
        self.connect_changed_signal()

    def __init__(  # pylint: disable=too-many-arguments
            self,
            display_name, key,
            callback,
            init_value,
            min_value, max_value,
            step_increment,
            page_increment,
            page_size
    ):

        adjustment = Gtk.Adjustment(
            value=init_value,
            lower=min_value,
            upper=max_value,
            step_increment=step_increment,
            page_increment=page_increment,
            page_size=page_size
        )
        spinbutton = Gtk.SpinButton(
            adjustment=adjustment,
        )
        spinbutton.set_numeric(True)
        spinbutton.set_update_policy(Gtk.SpinButtonUpdatePolicy.IF_VALID)

        super().__init__(
            display_name=display_name,
            key=key,
            callback=callback,
            value_widget=spinbutton
        )


class FloatListBoxRow(NumericListBoxRow):

    def on_value_changed(self, widget):
        raw_value = widget.get_value()
        self.value = int(raw_value*100)/100  # limit float to 2 digits
        GLib.idle_add(self.callback, self.key, self.value)

    def __init__(self, display_name, key, callback,  # pylint: disable=too-many-arguments
                 min_value=None, max_value=None):
        min_value = min_value or 0.0
        max_value = max_value or 10.0
        super().__init__(
            display_name=display_name,
            key=key,
            callback=callback,
            init_value=0.0,
            min_value=min_value,
            max_value=max_value,
            step_increment=0.01,
            page_increment=1.0,
            page_size=0.0
        )
        self.value_widget.set_digits(2)


class IntListBoxRow(NumericListBoxRow):

    def on_value_changed(self, widget):
        self.value = widget.get_value_as_int()
        GLib.idle_add(self.callback, self.key, self.value)

    def __init__(self, display_name, key, callback,  # pylint: disable=too-many-arguments
                 min_value=None, max_value=None):
        min_value = min_value or 0
        max_value = max_value or 20
        super().__init__(
            display_name=display_name,
            key=key,
            callback=callback,
            init_value=0,
            min_value=min_value,
            max_value=max_value,
            step_increment=1,
            page_increment=10,
            page_size=0
        )


class BoolListBoxRow(OomoxListBoxRow):

    def connect_changed_signal(self):
        self.changed_signal = self.value_widget.connect("notify::active", self.on_switch_activated)

    def set_value(self, value):
        self.disconnect_changed_signal()
        self.value = value
        self.value_widget.set_active(value)
        self.connect_changed_signal()

    def on_switch_activated(self, switch, _gparam):
        self.value = switch.get_active()
        GLib.idle_add(self.callback, self.key, self.value)

    def __init__(self, display_name, key, callback):
        super().__init__(
            display_name=display_name,
            key=key,
            callback=callback,
            value_widget=Gtk.Switch()
        )


class OptionsListBoxRow(OomoxListBoxRow):

    options = None
    vbox = None
    description_label = None
    _description_label_added = False

    def connect_changed_signal(self):
        self.changed_signal = self.value_widget.connect("changed", self.on_dropdown_changed)

    def on_dropdown_changed(self, combobox):
        value_id = combobox.get_active()
        self.value = self.options[value_id]['value']
        GLib.idle_add(self.callback, self.key, self.value)

    def set_value(self, value):
        self.disconnect_changed_signal()
        self.value = value
        for option_idx, option in enumerate(self.options):
            if value == option['value']:
                self.value_widget.set_active(option_idx)
                if 'description' in option:
                    self.show_description_label()
                    self.description_label.set_text(option['description'])
                break
        self.connect_changed_signal()

    def show_description_label(self):
        if not self._description_label_added:
            self.vbox.add(self.description_label)
            self.description_label.show()
            self._description_label_added = True

    def __init__(self, display_name, key, options, callback):
        self.options = options
        options_store = Gtk.ListStore(str)
        for option in self.options:
            options_store.append([option.get('display_name', option['value'])])
        dropdown = Gtk.ComboBox.new_with_model(options_store)
        renderer_text = Gtk.CellRendererText()
        dropdown.pack_start(renderer_text, True)
        dropdown.add_attribute(renderer_text, "text", 0)

        super().__init__(
            display_name=display_name,
            key=key,
            callback=callback,
            value_widget=dropdown
        )

        self.remove(self.hbox)
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(self.vbox)
        self.vbox.add(self.hbox)

        self.description_label = Gtk.Label(xalign=1)
        self.description_label.set_margin_top(3)
        self.description_label.set_margin_bottom(7)
        self.description_label.set_state_flags(Gtk.StateFlags.INSENSITIVE, False)


class OomoxColorSelectionDialog(Gtk.ColorSelectionDialog):

    gtk_color = None
    transient_for = None

    def _on_cancel(self, _button):
        self.gtk_color = None
        self.destroy()

    def _on_ok(self, _button):
        self.gtk_color = self.props.color_selection.get_current_rgba()
        PaletteCache.add_color(self.gtk_color)
        self.destroy()

    def _on_response(self, widget, result):
        if result == Gtk.ResponseType.DELETE_EVENT:
            self._on_cancel(widget)

    def __init__(self, transient_for, gtk_color):
        self.transient_for = transient_for
        self.gtk_color = gtk_color

        super().__init__(
            title=_("Choose a Color…"),
            transient_for=transient_for,
            flags=0
        )
        self.set_transient_for(transient_for)
        self.props.color_selection.set_has_palette(True)

        self.props.color_selection.set_current_rgba(self.gtk_color)

        Gtk.Settings.get_default().props.gtk_color_palette = PaletteCache.get_gtk()

        self.props.cancel_button.connect("clicked", self._on_cancel)
        self.props.ok_button.connect("clicked", self._on_ok)
        self.connect("response", self._on_response)

        self.show_all()


class OomoxColorButton(Gtk.Button):

    gtk_color = None
    callback = None
    transient_for = None
    gtk_color_button = None
    color_image = None

    def set_rgba(self, gtk_color):
        self.gtk_color = gtk_color
        self.gtk_color_button.set_rgba(gtk_color)

    def on_click(self, _widget):
        color_selection_dialog = OomoxColorSelectionDialog(
            self.transient_for, self.gtk_color
        )
        color_selection_dialog.run()
        new_color = color_selection_dialog.gtk_color
        if new_color:
            self.set_rgba(new_color)
            self.callback(new_color)

    def set_value(self, value):
        self.set_rgba(convert_theme_color_to_gdk(value or FALLBACK_COLOR))

    def __init__(self, transient_for, callback):
        self.transient_for = transient_for

        self.callback = callback
        Gtk.Button.__init__(self)
        self.gtk_color_button = Gtk.ColorButton.new()
        self.color_image = self.gtk_color_button.get_child()
        self.set_image(self.color_image)
        self.connect("clicked", self.on_click)


class OomoxLinkedDropdown(Gtk.MenuButton):

    drop_down = None

    def build_dropdown_menu(self):
        self.drop_down = Gtk.Menu()
        menu_items = []
        menu_items.append([Gtk.MenuItem(label=_("Replace all instances")), self.replace_all_instances])

        for item in menu_items:
            self.drop_down.append(item[0])
            item[0].connect("activate", item[1])

        self.drop_down.show_all()
        return self.drop_down

    def replace_all_instances(self, _menu_item):  # pylint:disable=unused-argument

        color_selection_dialog = OomoxColorSelectionDialog(
            self.transient_for, self.get_fuzzy_sibling(OomoxColorButton).gtk_color
        )
        color_selection_dialog.run()
        new_color = color_selection_dialog.gtk_color
        if new_color:
            new_color.string = convert_gdk_to_theme_color(new_color)
            old_color = self.get_fuzzy_sibling(OomoxColorButton).gtk_color
            old_color.string = convert_gdk_to_theme_color(old_color)

            cousins = self.get_fuzzy_ancestor(Gtk.ListBox).get_children()
            for lbr in cousins:
                if isinstance(lbr, ColorListBoxRow) and lbr.color_button.gtk_color is not None:
                    if convert_gdk_to_theme_color(lbr.color_button.gtk_color) == old_color.string:
                        lbr.set_value(new_color.string, connected=True)

    def get_fuzzy_ancestor(self, desired_class):
        potential_ancestor = self.get_parent()
        while not isinstance(potential_ancestor, desired_class):
            potential_ancestor = potential_ancestor.get_parent()
            if isinstance(potential_ancestor, Gtk.Application):
                break
        else:
            return potential_ancestor

    def get_fuzzy_sibling(self, desired_class):
        potential_siblings = self.get_parent().get_children()
        for potential_sibling in potential_siblings:
            if isinstance(potential_sibling, desired_class):
                return potential_sibling
        return None

    def __init__(self, transient_for):
        super().__init__()
        self.transient_for = transient_for
        self.set_popup(self.build_dropdown_menu())


class ColorListBoxRow(OomoxListBoxRow):

    color_button = None
    color_entry = None
    menu_button = None

    def connect_changed_signal(self):
        self.changed_signal = self.color_entry.connect("changed", self.on_color_input)

    def disconnect_changed_signal(self):
        if self.changed_signal:
            self.color_entry.disconnect(self.changed_signal)

    def on_color_input(self, widget, value=None):
        self.value = value or widget.get_text()
        if self.value == '':
            self.value = None
        if self.value:
            self.color_button.set_rgba(convert_theme_color_to_gdk(self.value))
        GLib.idle_add(self.callback, self.key, self.value)

    def on_color_set(self, gtk_value):
        self.value = convert_gdk_to_theme_color(gtk_value)
        self.color_entry.set_text(self.value)

    def set_value(self, value, connected=False):  # pylint: disable=arguments-differ
        if connected is False:
            self.disconnect_changed_signal()
        self.value = value
        if value:
            self.color_entry.set_text(self.value)
            self.color_button.set_rgba(convert_theme_color_to_gdk(value))
        else:
            self.color_entry.set_text(_('<N/A>'))
            self.color_button.set_rgba(convert_theme_color_to_gdk(FALLBACK_COLOR))
        if connected is False:
            self.connect_changed_signal()

    def __init__(self, display_name, key, callback, transient_for):
        self.color_button = OomoxColorButton(
            transient_for=transient_for,
            callback=self.on_color_set
        )
        self.color_entry = Gtk.Entry(
            text=_('<none>'), width_chars=6, max_length=6
        )
        self.menu_button = OomoxLinkedDropdown(transient_for)
        self.color_entry.get_style_context().add_class(Gtk.STYLE_CLASS_MONOSPACE)
        linked_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        Gtk.StyleContext.add_class(
            linked_box.get_style_context(), "linked"
        )
        linked_box.add(self.color_entry)
        linked_box.add(self.color_button)
        linked_box.add(self.menu_button)
        super().__init__(
            display_name=display_name,
            key=key,
            callback=callback,
            value_widget=linked_box
        )


class ImagePathListBoxRow(OomoxListBoxRow):

    def set_value(self, value):
        with open(value, 'rb') as image_file:
            img_bytes = image_file.read()
            self.value_widget.set_from_bytes(img_bytes)

    def __init__(self, display_name, key, callback):

        image = ScaledImage(width=120)

        super().__init__(
            display_name=display_name,
            key=key,
            callback=callback,
            value_widget=image
        )


class SeparatorListBoxRow(Gtk.ListBoxRow):

    def __init__(self, display_name):
        super().__init__(activatable=False, selectable=False)

        label = Gtk.Label(xalign=0)
        label.set_markup("<b>{}</b>".format(display_name))

        hbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbox.pack_start(Gtk.Label(), True, True, 2)
        hbox.pack_start(label, True, True, 4)

        self.add(hbox)


class ThemeColorsList(Gtk.ScrolledWindow):

    color_edited_callback = None
    theme_reload_callback = None
    transient_for = None
    theme = None

    listbox = None
    _all_rows = None
    _no_gui_row = None

    def color_edited(self, key, value):
        self.theme[key] = value
        self.color_edited_callback(self.theme)

    def build_theme_model_rows(self):
        self._no_gui_row = SeparatorListBoxRow(_("Can't Be Edited in GUI"))
        self.listbox.add(self._no_gui_row)
        self._all_rows = {}
        for option_idx, theme_value in enumerate(THEME_MODEL):
            key = theme_value.get('key')
            display_name = theme_value.get('display_name', key)
            row = None

            callbacks = [self.color_edited, ]
            if theme_value.get('reload_theme'):
                def _callback(key, value):
                    for theme_option in get_theme_options_by_key(key):
                        theme_option['fallback_value'] = value
                    self.theme = self.theme_reload_callback()
                callbacks = [_callback, ]
            elif theme_value.get('reload_options') or key in [
                    'ICONS_STYLE', 'THEME_STYLE',
                    'TERMINAL_BASE_TEMPLATE', 'TERMINAL_THEME_MODE',
                    'TERMINAL_THEME_AUTO_BGFG', 'TERMINAL_FG', 'TERMINAL_BG',
            ]:
                def _callback(key, value):  # pylint:disable=unused-argument
                    self.open_theme(self.theme)
                callbacks += [_callback, ]

            if key in [
                    'TERMINAL_THEME_MODE', 'TERMINAL_THEME_ACCURACY',
                    'TERMINAL_THEME_EXTEND_PALETTE', 'TERMINAL_BASE_TEMPLATE',
                    '_PIL_PALETTE_QUALITY', '_PIL_PALETTE_STYLE',
            ]:
                # @TODO: instead of wrapping them by key name create a signal
                # and emit it from each slow plugin
                def _wrap_slow_callbacks(slow_callbacks):
                    def _new_cb(key, value):
                        GLib.timeout_add(0, self.disable, priority=GLib.PRIORITY_HIGH)
                        for slow_cb in slow_callbacks:
                            Gdk.threads_add_idle(GLib.PRIORITY_LOW, slow_cb, key, value, )
                        GLib.idle_add(self.enable, priority=GLib.PRIORITY_LOW)
                    return _new_cb

                callbacks = [_wrap_slow_callbacks(callbacks), ]

            def create_callback(_callbacks):
                def _callback(key, value):
                    for each in _callbacks:
                        each(key, value)

                return _callback

            callback = create_callback(callbacks)

            if theme_value['type'] == 'color':
                row = ColorListBoxRow(
                    display_name, key,
                    callback=callback,
                    transient_for=self.transient_for
                )
            elif theme_value['type'] == 'bool':
                row = BoolListBoxRow(
                    display_name, key, callback=callback
                )
            elif theme_value['type'] == 'int':
                row = IntListBoxRow(
                    display_name, key, callback=callback,
                    min_value=theme_value.get('min_value'),
                    max_value=theme_value.get('max_value')
                )
            elif theme_value['type'] == 'float':
                row = FloatListBoxRow(
                    display_name, key, callback=callback,
                    min_value=theme_value.get('min_value'),
                    max_value=theme_value.get('max_value')
                )
            elif theme_value['type'] == 'separator':
                row = SeparatorListBoxRow(display_name)
            elif theme_value['type'] == 'image_path':
                row = ImagePathListBoxRow(display_name, key, callback)
            elif theme_value['type'] == 'options':
                row = OptionsListBoxRow(
                    key=key,
                    display_name=display_name,
                    options=theme_value['options'],
                    callback=callback
                )
            if row:
                self._all_rows[option_idx] = row
                self.listbox.add(row)

    def open_theme(self, theme):
        self.theme = theme
        if "NOGUI" in theme:
            self._no_gui_row.show()
        else:
            self._no_gui_row.hide()
        for option_idx, theme_value in enumerate(THEME_MODEL):
            key = theme_value.get('key')
            row = self._all_rows.get(option_idx)
            if not row:
                continue
            if "NOGUI" in theme:
                row.hide()
                continue
            if theme_value.get('filter'):
                if not theme_value['filter'](theme):
                    row.hide()
                    continue
            if theme_value.get('value_filter'):
                if not check_value_filter(theme_value['value_filter'], theme):
                    row.hide()
                    continue
            if theme_value['type'] in ['color', 'options', 'bool', 'int', 'float', 'image_path']:
                row.set_value(theme[key])
            row.show()

    def hide_all_rows(self):
        self._no_gui_row.hide()
        for option_idx, _theme_value in enumerate(THEME_MODEL):
            row = self._all_rows.get(option_idx)
            if not row:
                continue
            row.hide()

    def disable(self):
        # self.transient_for.disable()
        pass  # @TODO:

    def enable(self):
        # self.transient_for.enable()
        pass  # @TODO:

    def __init__(self, color_edited_callback, theme_reload_callback, transient_for):
        self.transient_for = transient_for
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.color_edited_callback = color_edited_callback
        self.theme_reload_callback = theme_reload_callback

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.build_theme_model_rows()
        self.add(self.listbox)
