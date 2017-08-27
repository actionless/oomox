import os
from gi.repository import Gtk, GLib, GdkPixbuf, Gio

from .theme_model import theme_model
from .helpers import (
    convert_theme_color_to_gdk, mix_theme_colors, script_dir
)


class ThemePreview(Gtk.Grid):

    BG = 'bg'
    FG = 'fg'

    current_theme = None
    _need_size_update = False

    def override_color(self, widget, value, color, state=Gtk.StateType.NORMAL):
        if value == self.BG:
            return widget.override_background_color(state, color)
        elif value == self.FG:
            return widget.override_color(state, color)

    def update_preview_carets(self, colorscheme):
        css_provider_caret = Gtk.CssProvider()
        css_provider_caret.load_from_data((
            (Gtk.get_minor_version() >= 20 and """
            * {{
                caret-color: #{primary_caret_color};
                -gtk-secondary-caret-color: #{secondary_caret_color};
                -GtkWidget-cursor-aspect-ratio: {caret_aspect_ratio};
            }}
            """ or """
            * {{
                -GtkWidget-cursor-color: #{primary_caret_color};
                -GtkWidget-secondary-cursor-color: #{secondary_caret_color};
                -GtkWidget-cursor-aspect-ratio: {caret_aspect_ratio};
            }}
            """).format(
                primary_caret_color=colorscheme['CARET1_FG'],
                secondary_caret_color=colorscheme['CARET2_FG'],
                caret_aspect_ratio=colorscheme['CARET_SIZE']
            )
        ).encode('ascii'))
        Gtk.StyleContext.add_provider(
            self.entry.get_style_context(),
            css_provider_caret,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def update_preview_gradients(self, colorscheme):
        gradient = colorscheme['GRADIENT']
        for widget, color in zip(
            [self.button, self.headerbar_button, self.entry],
            [
                colorscheme["BTN_BG"],
                colorscheme["HDR_BTN_BG"],
                colorscheme["TXT_BG"]
            ]
        ):
            css_provider_gradient = Gtk.CssProvider()
            css_provider_gradient.load_from_data((
                 """
                * {{
                    background-image: linear-gradient(to bottom,
                        shade(#{color}, {amount1}),
                        shade(#{color}, {amount2})
                    );
                }}
                """.format(
                    color=color,
                    amount1=1 - gradient / 2,
                    amount2=1 + gradient * 2
                    ) if (gradient > 0) else """
                * {
                    background-image: none;
                }
                """
            ).encode('ascii'))
            Gtk.StyleContext.add_provider(
                widget.get_style_context(),
                css_provider_gradient,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def update_preview_borders(self, colorscheme):
        for widget, fg, bg, ratio in (
            (
                self.button,
                colorscheme['BTN_FG'],
                colorscheme['BTN_BG'],
                0.22
            ), (
                self.headerbar_button,
                colorscheme['HDR_BTN_FG'],
                colorscheme['HDR_BTN_BG'],
                0.22
            ), (
                self.entry,
                mix_theme_colors(
                    colorscheme['TXT_FG'], colorscheme['TXT_BG'], 0.20
                ),
                colorscheme['BG'],
                0.69
            ),
        ):
            border_color = mix_theme_colors(fg, bg, ratio)
            css_provider_border_color = Gtk.CssProvider()
            css_provider_border_color.load_from_data(''.join([
                "* {",
                "border-color: #{border_color};" .format(
                    border_color=border_color,
                ),
                "border-radius: {roundness}px;" .format(
                    roundness=colorscheme["ROUNDNESS"],
                ) if self.current_theme == "oomox" else '',
                "}"
            ]).encode('ascii'))
            Gtk.StyleContext.add_provider(
                widget.get_style_context(),
                css_provider_border_color,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def update_preview_icons(self, colorscheme):
        self.load_icon_templates(colorscheme['ICONS_STYLE'])
        for source_image, target_imagebox in (
            (self.icon_source_user_home, self.icon_user_home),
            (self.icon_source_user_desktop, self.icon_user_desktop),
            (self.icon_source_system_file_manager,
             self.icon_system_file_manager),
        ):
            new_svg_image = source_image.replace(
                "LightFolderBase", colorscheme["ICONS_LIGHT_FOLDER"]
            ).replace(
                "LightBase", colorscheme["ICONS_LIGHT"]
            ).replace(
                "MediumBase", colorscheme["ICONS_MEDIUM"]
            ).replace(
                "DarkStroke", colorscheme["ICONS_DARK"]
            ).replace(
                "%ICONS_ARCHDROID%", colorscheme["ICONS_ARCHDROID"]
            ).encode('ascii')
            stream = Gio.MemoryInputStream.new_from_bytes(
                GLib.Bytes.new(new_svg_image)
            )

            # @TODO: is it possible to make it faster?
            pixbuf = GdkPixbuf.Pixbuf.new_from_stream(stream, None)

            target_imagebox.set_from_pixbuf(pixbuf)

    def update_preview_colors(self, colorscheme):
        def mix(a, b, amount):
            return convert_theme_color_to_gdk(mix_theme_colors(colorscheme[b],
                                                               colorscheme[a],
                                                               amount))

        converted = {
            theme_value['key']: convert_theme_color_to_gdk(
                colorscheme[theme_value['key']]
            )
            for theme_value in theme_model if theme_value['type'] == 'color'
        }
        self.override_color(self.bg, self.BG, converted["BG"])
        self.override_color(self.label, self.FG, converted["FG"])
        self.override_color(self.sel_label, self.FG, converted["SEL_FG"])
        self.override_color(self.sel_label, self.BG, converted["SEL_BG"])
        self.override_color(self.entry, self.FG, converted["TXT_FG"])
        self.override_color(self.entry, self.BG, converted["TXT_BG"])
        self.override_color(self.entry, self.FG, converted["SEL_FG"],
                            state=Gtk.StateFlags.SELECTED)
        self.override_color(self.entry, self.BG, converted["SEL_BG"],
                            state=Gtk.StateFlags.SELECTED)
        self.override_color(self.button, self.FG, converted["BTN_FG"])
        self.override_color(self.button, self.BG, converted["BTN_BG"])
        for item in self.menubar:
            self.override_color(item, self.FG, converted["MENU_FG"])
            self.override_color(item, self.BG, mix("MENU_BG", "MENU_FG", 0.21),
                                state=Gtk.StateFlags.PRELIGHT)
            # FIXME: :hover { color: shade("MENU_FG", 1.08); }
            for widget in self.get_menu_widgets(item.get_submenu()):
                if isinstance(widget, Gtk.MenuShell):
                    self.override_color(widget, self.BG, converted["MENU_BG"])
                    self.override_color(widget, self.FG, converted["MENU_FG"])
                else:
                    if not widget.get_sensitive():  # :disabled
                        color = mix("MENU_FG", "MENU_BG", 0.5)
                    else:
                        color = converted["MENU_FG"]
                    self.override_color(widget, self.FG, color)
                self.override_color(widget, self.BG, converted["SEL_BG"],
                                    state=Gtk.StateFlags.PRELIGHT)
                self.override_color(widget, self.FG, converted["SEL_FG"],
                                    state=Gtk.StateFlags.PRELIGHT)
        self.override_color(self.menubar, self.BG, converted["MENU_BG"])
        self.override_color(self.headerbar, self.BG, converted["MENU_BG"])
        self.override_color(self.headerbar, self.FG, converted["MENU_FG"])
        self.override_color(self.headerbar_button, self.FG,
                            converted["HDR_BTN_FG"])
        self.override_color(self.headerbar_button, self.BG,
                            converted["HDR_BTN_BG"])

        self.override_color(self.icon_preview_listbox, self.BG,
                            converted["TXT_BG"])

        if self.current_theme == "oomox":
            css_provider_wm_border_color = Gtk.CssProvider()
            css_provider_wm_border_color.load_from_data("""
                * {{
                    border-color: #{border_color};
                    /*border-radius: {roundness}px;*/
                    border-width: 2px;
                    border-style: solid;
                }}
            """.format(
                border_color=colorscheme['WM_BORDER_FOCUS'],
                roundness=colorscheme['ROUNDNESS']
            ).encode('ascii'))
            Gtk.StyleContext.add_provider(
                self.bg.get_style_context(),
                css_provider_wm_border_color,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def update_preview(self, colorscheme):
        self.override_css_style(colorscheme)
        self.update_preview_colors(colorscheme)
        self.update_preview_borders(colorscheme)
        if self.current_theme == "oomox":
            self.update_preview_gradients(colorscheme)
            self.update_preview_carets(colorscheme)
        self.update_preview_icons(colorscheme)

    def __init__(self):
        super().__init__(row_spacing=6, column_spacing=6)
        self._init_widgets()

    def load_icon_templates(self, prefix):
        for template_path, attr_name in (
            ("user-home.svg.template", "icon_source_user_home"),
            ("user-desktop.svg.template", "icon_source_user_desktop"),
            ("system-file-manager.svg.template",
             "icon_source_system_file_manager"),
        ):
            with open(
                os.path.join(
                    script_dir, 'icon_previews', prefix, template_path
                ), "rb"
            ) as f:
                setattr(self, attr_name, f.read().decode('utf-8'))

    def create_menu(self, n_items, has_submenus=False):
        menu = Gtk.Menu()
        for i in range(0, n_items):
            sensitive = (i + 1) % 3 != 0
            label = _('Item {id}') if sensitive else _('Insensitive Item {id}')
            item = Gtk.MenuItem(label=label.format(id=i + 1),
                                sensitive=sensitive)
            menu.append(item)
            if has_submenus and (i + 1) % 2 == 0:
                item.set_submenu(self.create_menu(2))
        return menu

    def _init_widgets(self):
        preview_label = Gtk.Label(_("Preview:"))
        self.bg = Gtk.Grid(row_spacing=6, column_spacing=6)
        self.attach(preview_label, 1, 1, 3, 1)
        self.attach_next_to(self.bg, preview_label,
                            Gtk.PositionType.BOTTOM, 1, 1)

        self.headerbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.headerbar = Gtk.HeaderBar()
        self.headerbar.set_show_close_button(True)
        self.headerbar.props.title = _("Headerbar")
        self.headerbar_button = Gtk.Button(label="   %s   " % _("Button"))
        self.headerbar.pack_end(self.headerbar_button)

        self.menubar = Gtk.MenuBar()
        self.menuitem1 = Gtk.MenuItem(label=_('File'))
        self.menuitem1.set_submenu(self.create_menu(3, True))
        self.menubar.append(self.menuitem1)
        self.menuitem2 = Gtk.MenuItem(label=_('Edit'))
        self.menuitem2.set_submenu(self.create_menu(6, True))
        self.menubar.append(self.menuitem2)

        self.headerbox.pack_start(self.headerbar, True, True, 0)
        self.headerbox.pack_start(self.menubar, True, True, 0)

        self.label = Gtk.Label(_("This is a label."))
        self.sel_label = Gtk.Label(_("Selected item."))
        self.entry = Gtk.Entry(text=_("Text entry."))

        self.button = Gtk.Button(label=_("Click-click"))
        self.button.connect("style-updated", self._queue_resize)

        self.icon_preview_listbox = Gtk.ListBox()
        self.icon_preview_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.add(hbox)
        for attr_name in (
            "icon_user_home",
            "icon_user_desktop",
            "icon_system_file_manager"
        ):
            setattr(self, attr_name, Gtk.Image())
            hbox.pack_start(getattr(self, attr_name), True, True, 0)
        self.icon_preview_listbox.add(row)
        self.icon_preview_listbox.show_all()

        self.bg.attach(self.headerbox, 1, 1, 5, 2)
        self.bg.attach(self.label, 3, 3, 1, 1)
        self.bg.attach_next_to(self.sel_label, self.label,
                               Gtk.PositionType.BOTTOM, 1, 1)
        self.bg.attach_next_to(self.entry, self.sel_label,
                               Gtk.PositionType.BOTTOM, 1, 1)
        self.bg.attach_next_to(self.button, self.entry,
                               Gtk.PositionType.BOTTOM, 1, 1)
        # hack to have margin inside children box instead of the parent one:
        self.bottom_margin = Gtk.Label()
        self.bg.attach_next_to(self.bottom_margin, self.button,
                               Gtk.PositionType.BOTTOM, 1, 1)
        self.bg.attach_next_to(self.icon_preview_listbox, self.bottom_margin,
                               Gtk.PositionType.BOTTOM, 1, 1)
        self.bottom_margin2 = Gtk.Label()
        self.bg.attach_next_to(self.bottom_margin2, self.icon_preview_listbox,
                               Gtk.PositionType.BOTTOM, 1, 1)

    def get_menu_widgets(self, shell):
        """ gets a menu shell (menu or menubar) and all its children """

        children = [shell]
        for child in shell:
            children.append(child)
            submenu = child.get_submenu()
            if submenu:
                children.extend(self.get_menu_widgets(submenu))
        return children

    def override_css_style(self, colorscheme):
        css_provider = Gtk.CssProvider()
        new_theme_style = colorscheme["THEME_STYLE"]
        if new_theme_style == self.current_theme:
            return
        if self.current_theme:
            for child in self.get_children():
                child.destroy()
                self.remove(child)
            self._init_widgets()
        self.current_theme = new_theme_style
        css_postfix = '_flatplat' if self.current_theme == 'flatplat' else ''
        try:
            if Gtk.get_minor_version() >= 20:
                css_provider.load_from_path(
                    os.path.join(
                        script_dir, "theme{}20.css".format(css_postfix)
                    )
                )
            else:
                css_provider.load_from_path(
                    os.path.join(
                        script_dir, "theme{}.css".format(css_postfix)
                    )
                )
        except GLib.Error as e:
            print(e)

        for widget in [
            self,
            self.label,
            self.sel_label,
            self.entry,
            self.button,
            self.headerbar,
            self.headerbar_button
        ] + self.get_menu_widgets(self.menubar):
            Gtk.StyleContext.add_provider(
                widget.get_style_context(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        css_provider_border = Gtk.CssProvider()
        css_provider_border.load_from_data((
            """
            headerbar {
                border: none;
            }
            """
        ).encode('ascii'))
        Gtk.StyleContext.add_provider(
            self.headerbar.get_style_context(),
            css_provider_border,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.show_all()

    def _queue_resize(self, *args):
        # print(args)
        self.queue_resize()
