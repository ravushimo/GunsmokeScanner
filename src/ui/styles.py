"""CustomTkinter / ttk theming aligned with `.docs/DESIGN.md`.

`setup_theme()` configures global CTk appearance plus the ttk.Style entries
we still need (Treeview, Combobox, Scrollbar). `create_button()` returns a
preconfigured CTkButton in one of four variants from DESIGN.md. Use
`attach_hover_flash` to give non-button widgets the orange-on-hover signal.
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk

from src.constants import THEME

ButtonVariant = str  # "primary" | "secondary" | "featured" | "ghost"


def _theme_path() -> str:
    """Locate the bundled CTk theme JSON in dev and PyInstaller layouts."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[2]
    return str(base / "assets" / "ctk_theme.json")


def _patch_dropdown_menu_borders():
    """Remove the bright Windows frame CTk paints around OptionMenu popups.

    CTk's DropdownMenu uses tk.Menu with borderwidth=4 on Windows, which shows
    as a light gray outline. Force a flat, borderless dark menu instead.
    """
    try:
        from customtkinter.windows.widgets.core_widget_classes.dropdown_menu import (
            DropdownMenu,
        )
    except ImportError:
        return

    _orig = DropdownMenu._configure_menu_for_platforms

    def _configure_menu_for_platforms(self):
        _orig(self)
        if sys.platform.startswith("win"):
            try:
                tk.Menu.configure(
                    self,
                    relief="flat",
                    borderwidth=0,
                    activeborderwidth=0,
                    bd=0,
                )
            except tk.TclError:
                pass

    DropdownMenu._configure_menu_for_platforms = _configure_menu_for_platforms


def apply_ctk_theme():
    """Set CTk appearance + color theme. Must run before creating the CTk root."""
    # Match gunsmoke.app default (dark :root)
    ctk.set_appearance_mode("dark")
    try:
        ctk.set_default_color_theme(_theme_path())
    except (FileNotFoundError, ValueError):
        # Fallback to a built-in theme if the JSON is missing/invalid.
        ctk.set_default_color_theme("blue")
    _patch_dropdown_menu_borders()


def setup_ttk_styles(fonts):
    """Configure ttk styles for the widgets we still use (Treeview, Combobox).

    Must be called after the CTk root window exists so the style talks to
    the right interpreter.
    """
    style = ttk.Style()
    style.theme_use("clam")

    # Treeview — dark surfaces; clam theme needs lightcolor/darkcolor or it
    # paints bright 3D borders around the table and header separator.
    body = (fonts.body.cget("family"), fonts.body.cget("size"))
    head = (fonts.ui.cget("family"), fonts.ui.cget("size"), "bold")
    border = THEME["border"]
    canvas = THEME["bg_canvas"]
    surface = THEME["bg_surface"]

    style.configure(
        "Custom.Treeview",
        background=canvas,
        foreground=THEME["text_primary"],
        fieldbackground=canvas,
        bordercolor=border,
        lightcolor=canvas,
        darkcolor=canvas,
        borderwidth=0,
        relief="flat",
        rowheight=24,
        font=body,
    )
    style.configure(
        "Custom.Treeview.Heading",
        background=surface,
        foreground=THEME["text_strong"],
        bordercolor=border,
        lightcolor=surface,
        darkcolor=surface,
        borderwidth=0,
        relief="flat",
        font=head,
    )
    style.map(
        "Custom.Treeview",
        background=[("selected", THEME["bg_hover"])],
        foreground=[("selected", THEME["accent_orange"])],
        bordercolor=[("focus", border), ("!focus", border)],
        lightcolor=[("focus", canvas), ("!focus", canvas)],
        darkcolor=[("focus", canvas), ("!focus", canvas)],
    )
    style.map(
        "Custom.Treeview.Heading",
        background=[("active", THEME["bg_raised"])],
        foreground=[("active", THEME["accent_orange"])],
        bordercolor=[("active", border)],
        lightcolor=[("active", THEME["bg_raised"])],
        darkcolor=[("active", THEME["bg_raised"])],
    )
    # Drop clam's outer border element so no light frame remains
    style.layout(
        "Custom.Treeview",
        [("Treeview.treearea", {"sticky": "nswe"})],
    )

    # Combobox - used on the Upload tab for the API environment selector.
    style.configure(
        "Custom.TCombobox",
        fieldbackground=THEME["bg_surface"],
        background=THEME["bg_surface"],
        foreground=THEME["text_input"],
        bordercolor=THEME["border_strong"],
        arrowcolor=THEME["text_muted"],
        lightcolor=THEME["bg_surface"],
        darkcolor=THEME["bg_surface"],
        selectbackground=THEME["bg_hover"],
        selectforeground=THEME["accent_orange"],
        padding=4,
    )
    style.map(
        "Custom.TCombobox",
        fieldbackground=[("readonly", THEME["bg_surface"])],
        foreground=[("readonly", THEME["text_input"])],
    )

    # Scrollbar - kept on tk.Scrollbar instances that pair with Treeview.
    style.configure(
        "Custom.Vertical.TScrollbar",
        background=THEME["bg_raised"],
        troughcolor=THEME["bg_surface"],
        bordercolor=THEME["border"],
        arrowcolor=THEME["text_muted"],
        lightcolor=THEME["bg_raised"],
        darkcolor=THEME["bg_raised"],
    )


# CTkButton variant presets per DESIGN.md "Buttons" section. Each maps a
# variant name to the kwargs used when constructing the button.
_BUTTON_VARIANTS = {
    "primary": {
        "fg_color": THEME["cta_dark"],
        "hover_color": "#d94400",
        "text_color": THEME["cta_dark_text"],
        "corner_radius": 6,
        "border_width": 0,
    },
    "secondary": {
        "fg_color": THEME["bg_raised"],
        "hover_color": THEME["bg_hover"],
        "text_color": THEME["text_primary"],
        "corner_radius": 4,
        "border_width": 0,
    },
    "featured": {
        "fg_color": THEME["bg_featured"],
        "hover_color": THEME["bg_hover"],
        "text_color": THEME["text_strong"],
        "corner_radius": 6,
        "border_width": 1,
        "border_color": "#b17816",
    },
    "ghost": {
        "fg_color": "transparent",
        "hover_color": THEME["bg_hover"],
        "text_color": THEME["text_primary"],
        "corner_radius": 4,
        "border_width": 1,
        "border_color": THEME["border"],
    },
}


def create_button(
    parent, text, command, variant: ButtonVariant = "primary", font=None, **overrides
) -> ctk.CTkButton:
    """Build a CTkButton in one of the DESIGN.md variants.

    The "orange/amber on hover" text-color flash is added via Tk binds
    because CTk 5.2 does not support `text_color_hover` natively.
    """
    preset = dict(_BUTTON_VARIANTS.get(variant, _BUTTON_VARIANTS["primary"]))
    preset.update(overrides)

    btn = ctk.CTkButton(
        parent,
        text=text,
        command=command,
        font=font,
        cursor="hand2",
        **preset,
    )

    idle = preset["text_color"]
    hover = THEME["accent_amber"] if variant == "primary" else THEME["accent_orange"]
    attach_hover_flash(btn, idle, hover)
    return btn


def attach_hover_flash(widget, idle_color, hover_color=None):
    """Bind orange/amber text-color flash on hover to a CTk widget or Label."""
    if hover_color is None:
        hover_color = THEME["accent_orange"]

    def _enter(_event, w=widget, c=hover_color):
        try:
            w.configure(text_color=c)
        except (tk.TclError, ValueError):
            pass

    def _leave(_event, w=widget, c=idle_color):
        try:
            w.configure(text_color=c)
        except (tk.TclError, ValueError):
            pass

    widget.bind("<Enter>", _enter)
    widget.bind("<Leave>", _leave)
