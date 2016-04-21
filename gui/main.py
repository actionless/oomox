#!/bin/env python3
import os
import gi
gi.require_version('Gtk', '3.0')  # noqa
from gi.repository import Gtk, Gdk, GObject, GLib

from .helpers import (
    mkdir_p,
    read_colorscheme_from_path, save_colorscheme,
    script_dir, user_theme_dir,
    ImageButton, CenterLabel
)
from .presets_list import ThemePresetsList
from .colors_list import ThemeColorsList
from .preview import ThemePreview
from .export import export_theme


class NewDialog(Gtk.Dialog):

    entry = None
    input_data = ''

    def on_cancel(self, button):
        self.destroy()

    def on_ok(self, button):
        self.input_data = self.entry.get_text()
        self.destroy()

    def __init__(self, parent):
        Gtk.Dialog.__init__(self, "New theme", parent, 0)

        self.set_default_size(150, 100)

        label = Gtk.Label("Please input new theme name:")
        self.entry = Gtk.Entry()

        box = self.get_content_area()
        box.add(label)
        box.add(self.entry)

        cancel_button = self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        cancel_button.connect("clicked", self.on_cancel)
        ok_button = self.add_button("OK", Gtk.ResponseType.OK)
        ok_button.connect("clicked", self.on_ok)

        self.show_all()


class UnsavedDialog(Gtk.Dialog):

    def on_choose(self, button):
        self.destroy()

    def __init__(self, parent):
        Gtk.Dialog.__init__(self, "Unsaved changes", parent, 0)
        self.set_default_size(150, 100)

        label = CenterLabel("There are unsaved changes.\nSave them?")
        box = self.get_content_area()
        box.add(label)

        cancel_button = self.add_button("No", Gtk.ResponseType.CANCEL)
        cancel_button.connect("clicked", self.on_choose)
        ok_button = self.add_button("Yes", Gtk.ResponseType.OK)
        ok_button.connect("clicked", self.on_choose)

        self.show_all()


class MainWindow(Gtk.Window):

    colorscheme_name = None
    colorscheme_path = None
    colorscheme = None
    theme_edited = False
    # widgets:
    headerbar = None
    theme_edit = None
    presets_list = None
    preview = None

    def save(self, name=None):
        if not name:
            name = self.colorscheme_name
        new_path = save_colorscheme(name, self.colorscheme)
        self.presets_list.update_current_preset_path(new_path)
        self.theme_edited = False
        self.headerbar.props.title = self.colorscheme_name

    def check_unsaved_changes(self):
        if self.theme_edited:
            if UnsavedDialog(self).run() == Gtk.ResponseType.OK:
                self.save()

    def on_clone(self, button):
        dialog = NewDialog(self)
        dialog.run()
        new_theme_name = dialog.input_data
        self.save(new_theme_name)
        self.presets_list.add_preset(
            new_theme_name, os.path.join(user_theme_dir, new_theme_name)
        )

    def on_save(self, button):
        self.save()

    def on_export(self, button):
        self.check_unsaved_changes()
        export_theme(window=self, theme_path=self.colorscheme_path)

    def on_preset_selected(self, selected_preset, selected_preset_path):
        self.check_unsaved_changes()
        self.colorscheme_name = selected_preset
        self.colorscheme_path = selected_preset_path
        self.colorscheme = read_colorscheme_from_path(selected_preset_path)
        self.theme_edit.open_theme(self.colorscheme)
        self.preview.update_preview_colors(self.colorscheme)
        self.theme_edited = False
        self.headerbar.props.title = selected_preset

    def on_color_edited(self, colorscheme):
        self.colorscheme = colorscheme
        self.preview.update_preview_colors(self.colorscheme)
        if not self.theme_edited:
            self.headerbar.props.title = "*" + self.headerbar.props.title
        self.theme_edited = True

    def on_quit(self, arg1, arg2):
        self.check_unsaved_changes()
        Gtk.main_quit(arg1, arg2)

    def _init_headerbar(self):
        self.headerbar = Gtk.HeaderBar()
        self.headerbar.set_show_close_button(True)
        self.headerbar.props.title = "Oo-mox GUI"

        # @TODO:
        # new_button = ImageButton("text-x-generic-symbolic", "Create new theme")  # noqa
        # self.headerbar.pack_start(new_button)

        clone_button = ImageButton("edit-copy-symbolic", "Clone current theme")
        clone_button.connect("clicked", self.on_clone)
        self.headerbar.pack_start(clone_button)

        save_button = ImageButton("media-floppy-symbolic", "Save theme")
        save_button.connect("clicked", self.on_save)
        self.headerbar.pack_start(save_button)

        export_button = Gtk.Button(label="Export theme")
        export_button.connect("clicked", self.on_export)
        self.headerbar.pack_end(export_button)

        self.set_titlebar(self.headerbar)

    def _init_window(self):
        Gtk.Window.__init__(self, title="Oo-mox GUI")
        self.set_default_size(500, 300)
        self.set_border_width(6)

        win_style_context = self.get_style_context()
        css_provider = Gtk.CssProvider()
        try:
            if Gtk.get_minor_version() == 20:
                css_provider.load_from_path(
                    os.path.join(script_dir, "theme20.css")
                )
            else:
                css_provider.load_from_path(
                    os.path.join(script_dir, "theme.css")
                )
        except GLib.Error as e:
            print(e)
        screen = Gdk.Screen.get_default()
        win_style_context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self._init_headerbar()

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.add(self.box)

    def __init__(self):
        self.colorscheme = {}
        mkdir_p(user_theme_dir)

        self._init_window()

        self.presets_list = ThemePresetsList(
            preset_select_callback=self.on_preset_selected
        )
        self.box.pack_start(self.presets_list, True, True, 0)

        self.theme_edit = ThemeColorsList(
            color_edited_callback=self.on_color_edited
        )
        self.box.pack_start(self.theme_edit, True, True, 0)

        self.preview = ThemePreview()
        self.box.pack_start(self.preview, True, True, 0)


def main():
    GObject.threads_init()
    win = MainWindow()
    win.connect("delete-event", win.on_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
