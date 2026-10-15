"""Design tokens for EZ Bulk Rename.

Teal (hue 182) is the working colour; the logo's orange swoosh is reserved
for one place only. Every colour is a (light, dark) pair, so dark mode works
everywhere. Run  python check_palette.py ezrename/theme.py  after any change.
"""

from __future__ import annotations

import sys
import tkinter.font as tkfont
from functools import lru_cache

import customtkinter as ctk
from PIL import Image

from .system import resource_path

# ---------------------------------------------------------------- colours
BG = ("#EEF7F7", "#121C1C")
SURFACE = ("#FFFFFF", "#1A2828")
SURFACE_2 = ("#F6FBFB", "#1F2F30")
BORDER = ("#DCEBEC", "#2A3E3F")
TEXT = ("#1B2F30", "#E6F1F1")
TEXT_2 = ("#4D6768", "#A3BBBC")
TEXT_3 = ("#87A2A3", "#6F898A")

PRIMARY = ("#357D80", "#357F82")
PRIMARY_HOVER = ("#2A686A", "#418F92")
PRIMARY_TEXT = ("#2E7073", "#8DD7DA")   # links, active labels, selected borders, new names
PRIMARY_SOFT = ("#E6F6F7", "#1E393A")
PRIMARY_DISABLED = ("#B8D8D9", "#2A4546")
ON_PRIMARY = ("#FFFFFF", "#FFFFFF")

ACCENT = ("#F05A28", "#F26B3A")         # logo swoosh; used once, on purpose

DANGER = ("#C33737", "#E26E6E")
DANGER_HOVER = ("#B03535", "#EB7B7B")
DANGER_SOFT = ("#FBEAEA", "#3A2326")
DANGER_FILL = ("#C33737", "#B03535")    # Stop / Undo: white text needs a darker red in dark mode
DANGER_FILL_HOVER = ("#B03535", "#C33737")
SUCCESS = ("#297B4D", "#56B784")
SUCCESS_SOFT = ("#E8F5EE", "#1B3326")

HOVER = ("#F0F8F8", "#243637")

# Light mode is not all white: the header bar and the table's column titles are deep
# teal, which frames the work area (Boss, 2026-10-15). In dark mode they stay dark.
HEADER_BG = ("#1C3F41", "#1A2828")
HEADER_TEXT = ("#FFFFFF", "#E6F1F1")
HEADER_TEXT_2 = ("#B5D2D3", "#A3BBBC")   # "by EZKerja", header icons
HEADER_LINK = ("#9FE3E6", "#8DD7DA")     # "More EZKerja tools"
HEADER_HOVER = ("#29575A", "#243637")
TABLE_HEAD = ("#2A4E50", "#1F2F30")
TABLE_HEAD_TEXT = ("#FFFFFF", "#A3BBBC")

# The preview table: a row that will be renamed is tinted, a row that is blocked
# (duplicate name, illegal character...) is red, a row with no change is quiet.
CHANGE_ROW = PRIMARY_SOFT
BLOCKED_ROW = DANGER_SOFT
UNCHANGED_TEXT = TEXT_2

# ---------------------------------------------------------------- type
IS_WINDOWS = sys.platform == "win32"
_FAMILY = "Segoe UI" if IS_WINDOWS else "DejaVu Sans"
_FAMILY_SEMIBOLD = "Segoe UI Semibold" if IS_WINDOWS else "DejaVu Sans"
_FAMILY_MONO = "Consolas" if IS_WINDOWS else "DejaVu Sans Mono"

# Type scale (px): 22 display, 16 title, 13 body, 12 small, 11 caption
_font_cache: dict = {}


def font(size: int = 13, semibold: bool = False) -> ctk.CTkFont:
    key = (size, semibold)
    if key not in _font_cache:
        if semibold and IS_WINDOWS:
            _font_cache[key] = ctk.CTkFont(family=_FAMILY_SEMIBOLD, size=size)
        else:
            _font_cache[key] = ctk.CTkFont(family=_FAMILY, size=size,
                                           weight="bold" if semibold else "normal")
    return _font_cache[key]


_tk_font_cache: dict = {}


def tk_font(size: int, scale: float, semibold: bool = False, mono: bool = False) -> tkfont.Font:
    """A plain Tk font for widgets CustomTkinter doesn't scale (the preview table).

    Negative sizes are pixels, so ``size`` matches the px type scale above.
    """
    px = max(8, round(size * scale))
    key = (px, semibold, mono)
    if key not in _tk_font_cache:
        if mono:
            family, weight = _FAMILY_MONO, "normal"
        elif semibold and IS_WINDOWS:
            family, weight = _FAMILY_SEMIBOLD, "normal"
        else:
            family, weight = _FAMILY, "bold" if semibold else "normal"
        _tk_font_cache[key] = tkfont.Font(family=family, size=-px, weight=weight)
    return _tk_font_cache[key]


def pick(token: tuple[str, str]) -> str:
    """The colour of a token for the current appearance mode (for plain Tk widgets)."""
    return token[1] if ctk.get_appearance_mode() == "Dark" else token[0]


# ---------------------------------------------------------------- spacing
SPACE_1, SPACE_2, SPACE_3, SPACE_4 = 4, 8, 16, 24
RADIUS_S, RADIUS_M, RADIUS_L = 6, 10, 16
SIDEBAR_W = 300
CONTENT_W = SIDEBAR_W - 2 * SPACE_4 - 16  # usable width inside the sidebar scroll area


# ---------------------------------------------------------------- icons
@lru_cache(maxsize=None)
def _mask(name: str) -> Image.Image:
    return Image.open(resource_path("assets", "icons", f"{name}.png")).convert("RGBA")


def _tint(name: str, hex_color: str) -> Image.Image:
    m = _mask(name)
    solid = Image.new("RGBA", m.size, hex_color)
    solid.putalpha(m.getchannel("A"))
    return solid


@lru_cache(maxsize=None)
def icon(name: str, size: int = 18, color: tuple[str, str] = TEXT_2) -> ctk.CTkImage:
    """A Lucide icon tinted for light and dark mode."""
    return ctk.CTkImage(light_image=_tint(name, color[0]), dark_image=_tint(name, color[1]),
                        size=(size, size))


@lru_cache(maxsize=None)
def blank(size: int = 16) -> ctk.CTkImage:
    """Transparent placeholder: CTkLabel can't reliably remove an image once set."""
    img = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    return ctk.CTkImage(img, img, size=(size, size))


@lru_cache(maxsize=None)
def asset_image(file: str, size: int) -> ctk.CTkImage:
    img = Image.open(resource_path("assets", file)).convert("RGBA")
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
