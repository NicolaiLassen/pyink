from __future__ import annotations

import re
from typing import Any

# Reset
RESET = "\033[0m"

# Style codes
STYLE_CODES: dict[str, str] = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "italic": "\033[3m",
    "underline": "\033[4m",
    "inverse": "\033[7m",
    "hidden": "\033[8m",
    "strikethrough": "\033[9m",
    "overline": "\033[53m",
}

# Standard foreground colors
FG_COLORS: dict[str, int] = {
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    "gray": 90,
    "grey": 90,
    "bright_red": 91,
    "bright_green": 92,
    "bright_yellow": 93,
    "bright_blue": 94,
    "bright_magenta": 95,
    "bright_cyan": 96,
    "bright_white": 97,
    "red_bright": 91,
    "green_bright": 92,
    "yellow_bright": 93,
    "blue_bright": 94,
    "magenta_bright": 95,
    "cyan_bright": 96,
    "white_bright": 97,
}

# Standard background colors
BG_COLORS: dict[str, int] = {
    "black": 40,
    "red": 41,
    "green": 42,
    "yellow": 43,
    "blue": 44,
    "magenta": 45,
    "cyan": 46,
    "white": 47,
    "gray": 100,
    "grey": 100,
    "bright_red": 101,
    "bright_green": 102,
    "bright_yellow": 103,
    "bright_blue": 104,
    "bright_magenta": 105,
    "bright_cyan": 106,
    "bright_white": 107,
}

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape codes from a string.

    Parameters
    ----------
    text : str
        Text potentially containing ANSI escape sequences.

    Returns
    -------
    str
        The text with all ANSI escape sequences removed.
    """
    return _ANSI_RE.sub("", text)


def _parse_hex_color(color: str) -> tuple[int, int, int] | None:
    m = _HEX_RE.match(color)
    if not m:
        return None
    hex_str = m.group(1)
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


def _color_code(color: str | None, is_bg: bool = False) -> str:
    if color is None:
        return ""

    # Named color
    lookup = BG_COLORS if is_bg else FG_COLORS
    if color in lookup:
        return f"\033[{lookup[color]}m"

    # Hex color -> true color (24-bit)
    rgb = _parse_hex_color(color)
    if rgb:
        prefix = 48 if is_bg else 38
        return f"\033[{prefix};2;{rgb[0]};{rgb[1]};{rgb[2]}m"

    # ANSI 256 color (number as string)
    try:
        num = int(color)
        if 0 <= num <= 255:
            prefix = 48 if is_bg else 38
            return f"\033[{prefix};5;{num}m"
    except ValueError:
        pass

    # rgb(r,g,b) format
    if color.startswith("rgb("):
        inner = color[4:-1]
        parts = inner.split(",")
        if len(parts) == 3:
            try:
                r, g, b = int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip())
                prefix = 48 if is_bg else 38
                return f"\033[{prefix};2;{r};{g};{b}m"
            except ValueError:
                pass

    return ""


def style_text(
    text: str,
    *,
    color: str | None = None,
    background_color: str | None = None,
    bg_color: str | None = None,
    background: str | None = None,
    bold: bool = False,
    dim: bool = False,
    dim_color: bool = False,
    italic: bool = False,
    underline: bool = False,
    strikethrough: bool = False,
    inverse: bool = False,
    overline: bool = False,
    wrap: str | None = None,
    text_wrap: str | None = None,
    **_extra: Any,
) -> str:
    """Apply ANSI styles to text based on Ink-style props.

    Parameters
    ----------
    text : str
        The text to style.
    color : str or None, optional
        Foreground color name, hex, ``rgb()``, or ANSI-256 number.
    background_color : str or None, optional
        Background color (same formats as *color*).
    bg_color : str or None, optional
        Alias for *background_color*.
    background : str or None, optional
        Alias for *background_color*.
    bold : bool, optional
        Enable bold.
    dim : bool, optional
        Enable dim / faint.
    dim_color : bool, optional
        Apply dim specifically to the foreground color.
    italic : bool, optional
        Enable italic.
    underline : bool, optional
        Enable underline.
    strikethrough : bool, optional
        Enable strikethrough.
    inverse : bool, optional
        Enable inverse / reverse video.
    overline : bool, optional
        Enable overline.
    wrap : str or None, optional
        Text wrap mode (unused here, consumed by layout).
    text_wrap : str or None, optional
        Alias for *wrap*.
    **_extra : Any
        Extra keyword arguments are silently ignored.

    Returns
    -------
    str
        The text wrapped in the appropriate ANSI escape sequences.
    """
    if not text:
        return text

    prefix = ""

    # Foreground color
    actual_color = color
    if dim_color and actual_color:
        prefix += STYLE_CODES["dim"]
    elif dim_color:
        prefix += STYLE_CODES["dim"]

    prefix += _color_code(actual_color)

    # Background color
    bg = background_color or bg_color or background
    prefix += _color_code(bg, is_bg=True)

    # Style attributes
    if bold:
        prefix += STYLE_CODES["bold"]
    if dim and not dim_color:
        prefix += STYLE_CODES["dim"]
    if italic:
        prefix += STYLE_CODES["italic"]
    if underline:
        prefix += STYLE_CODES["underline"]
    if strikethrough:
        prefix += STYLE_CODES["strikethrough"]
    if inverse:
        prefix += STYLE_CODES["inverse"]
    if overline:
        prefix += STYLE_CODES["overline"]

    if prefix:
        return f"{prefix}{text}{RESET}"
    return text


# Cursor and screen control
CURSOR_HIDE = "\033[?25l"
CURSOR_SHOW = "\033[?25h"
CLEAR_SCREEN = "\033[2J"
CURSOR_HOME = "\033[H"
CLEAR_TO_END = "\033[J"
ERASE_LINE = "\033[2K"
ALT_SCREEN_ON = "\033[?1049h"
ALT_SCREEN_OFF = "\033[?1049l"


def cursor_to(x: int, y: int) -> str:
    """Move cursor to (x, y) position (1-indexed).

    Parameters
    ----------
    x : int
        Zero-based column.
    y : int
        Zero-based row.

    Returns
    -------
    str
        The ANSI escape sequence for the cursor movement.
    """
    return f"\033[{y + 1};{x + 1}H"


def cursor_up(n: int = 1) -> str:
    return f"\033[{n}A"


def cursor_down(n: int = 1) -> str:
    return f"\033[{n}B"


def erase_lines(count: int) -> str:
    """Erase `count` lines from current position upward.

    Parameters
    ----------
    count : int
        Number of lines to erase.

    Returns
    -------
    str
        The combined ANSI escape sequence.
    """
    result = ""
    for i in range(count):
        result += ERASE_LINE
        if i < count - 1:
            result += cursor_up(1)
    return result
