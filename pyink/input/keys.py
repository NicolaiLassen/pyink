from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Key:
    """Parsed key information from a keypress event.

    Mirrors Ink's Key interface exactly.
    """

    up_arrow: bool = False
    down_arrow: bool = False
    left_arrow: bool = False
    right_arrow: bool = False
    page_up: bool = False
    page_down: bool = False
    home: bool = False
    end: bool = False
    return_key: bool = False
    escape: bool = False
    ctrl: bool = False
    shift: bool = False
    tab: bool = False
    backspace: bool = False
    delete: bool = False
    meta: bool = False
    f1: bool = False
    f2: bool = False
    f3: bool = False
    f4: bool = False
    f5: bool = False
    f6: bool = False
    f7: bool = False
    f8: bool = False
    f9: bool = False
    f10: bool = False
    f11: bool = False
    f12: bool = False


def parse_keypress(data: bytes) -> tuple[str, Key]:
    """Parse raw terminal input bytes into (input_string, Key).

    Handles ANSI escape sequences for special keys.
    """
    key = Key()

    if not data:
        return ("", key)

    # Try to decode as utf-8
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ("", key)

    # Ctrl+C
    if text == "\x03":
        key.ctrl = True
        return ("c", key)

    # Ctrl+D
    if text == "\x04":
        key.ctrl = True
        return ("d", key)

    # Tab
    if text == "\t":
        key.tab = True
        return ("", key)

    # Shift+Tab (reverse tab)
    if text == "\x1b[Z":
        key.tab = True
        key.shift = True
        return ("", key)

    # Return/Enter
    if text == "\r" or text == "\n":
        key.return_key = True
        return ("", key)

    # Backspace
    if text == "\x7f" or text == "\x08":
        key.backspace = True
        return ("", key)

    # Escape key (standalone)
    if text == "\x1b":
        key.escape = True
        return ("", key)

    # Delete
    if text == "\x1b[3~":
        key.delete = True
        return ("", key)

    # Arrow keys
    if text == "\x1b[A" or text == "\x1bOA":
        key.up_arrow = True
        return ("", key)
    if text == "\x1b[B" or text == "\x1bOB":
        key.down_arrow = True
        return ("", key)
    if text == "\x1b[C" or text == "\x1bOC":
        key.right_arrow = True
        return ("", key)
    if text == "\x1b[D" or text == "\x1bOD":
        key.left_arrow = True
        return ("", key)

    # Shift+arrow keys
    if text == "\x1b[1;2A":
        key.up_arrow = True
        key.shift = True
        return ("", key)
    if text == "\x1b[1;2B":
        key.down_arrow = True
        key.shift = True
        return ("", key)
    if text == "\x1b[1;2C":
        key.right_arrow = True
        key.shift = True
        return ("", key)
    if text == "\x1b[1;2D":
        key.left_arrow = True
        key.shift = True
        return ("", key)

    # Ctrl+arrow keys
    if text == "\x1b[1;5A":
        key.up_arrow = True
        key.ctrl = True
        return ("", key)
    if text == "\x1b[1;5B":
        key.down_arrow = True
        key.ctrl = True
        return ("", key)
    if text == "\x1b[1;5C":
        key.right_arrow = True
        key.ctrl = True
        return ("", key)
    if text == "\x1b[1;5D":
        key.left_arrow = True
        key.ctrl = True
        return ("", key)

    # Page Up/Down
    if text == "\x1b[5~":
        key.page_up = True
        return ("", key)
    if text == "\x1b[6~":
        key.page_down = True
        return ("", key)

    # Home/End
    if text == "\x1b[H" or text == "\x1b[1~" or text == "\x1bOH":
        key.home = True
        return ("", key)
    if text == "\x1b[F" or text == "\x1b[4~" or text == "\x1bOF":
        key.end = True
        return ("", key)

    # Function keys
    _FKEY_MAP = {
        "\x1bOP": "f1", "\x1b[11~": "f1",
        "\x1bOQ": "f2", "\x1b[12~": "f2",
        "\x1bOR": "f3", "\x1b[13~": "f3",
        "\x1bOS": "f4", "\x1b[14~": "f4",
        "\x1b[15~": "f5",
        "\x1b[17~": "f6",
        "\x1b[18~": "f7",
        "\x1b[19~": "f8",
        "\x1b[20~": "f9",
        "\x1b[21~": "f10",
        "\x1b[23~": "f11",
        "\x1b[24~": "f12",
    }
    if text in _FKEY_MAP:
        setattr(key, _FKEY_MAP[text], True)
        return ("", key)

    # Meta (Alt) + key: ESC followed by a char
    if len(text) == 2 and text[0] == "\x1b" and text[1].isprintable():
        key.meta = True
        return (text[1], key)

    # Ctrl + letter (0x01-0x1a)
    if len(text) == 1 and 1 <= ord(text) <= 26:
        key.ctrl = True
        return (chr(ord("a") + ord(text) - 1), key)

    # Regular character(s)
    return (text, key)
