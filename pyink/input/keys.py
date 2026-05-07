from __future__ import annotations

from dataclasses import dataclass


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
    super_key: bool = False
    hyper: bool = False
    caps_lock: bool = False
    num_lock: bool = False
    event_type: str | None = None  # 'press' | 'repeat' | 'release' (Kitty protocol)
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
    # Mouse scroll (SGR mouse protocol)
    scroll_up: bool = False
    scroll_down: bool = False


def parse_keypress(data: bytes) -> tuple[str, Key]:
    """Parse raw terminal input bytes into (input_string, Key).

    Handles ANSI escape sequences for special keys.

    Parameters
    ----------
    data : bytes
        Raw bytes read from the terminal.

    Returns
    -------
    tuple[str, Key]
        A ``(input_string, key)`` tuple where *input_string* is the
        printable character (if any) and *key* carries modifier and
        special-key flags.
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

    # Modifier + arrow/home/end: \x1b[1;Nd where N encodes modifiers
    # and d is A/B/C/D/H/F. xterm modifier encoding:
    # flags = N-1 where bit 0 = Shift, bit 1 = Alt, bit 2 = Ctrl.
    #   2=Shift, 3=Alt, 4=Alt+Shift, 5=Ctrl, 6=Ctrl+Shift,
    #   7=Ctrl+Alt, 8=Ctrl+Alt+Shift
    if len(text) == 6 and text.startswith("\x1b[1;") and text[5] in "ABCDHF":
        try:
            mod = int(text[4])
        except ValueError:
            mod = 0
        if 2 <= mod <= 8:
            flags = mod - 1
            key.shift = bool(flags & 1)
            key.meta = bool(flags & 2)  # Alt = meta
            key.ctrl = bool(flags & 4)
            final = text[5]
            if final == "A":
                key.up_arrow = True
            elif final == "B":
                key.down_arrow = True
            elif final == "C":
                key.right_arrow = True
            elif final == "D":
                key.left_arrow = True
            elif final == "H":
                key.home = True
            elif final == "F":
                key.end = True
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

    # SGR mouse protocol: \x1b[<button;x;yM or \x1b[<button;x;ym
    # Button 64 = scroll up, 65 = scroll down
    if text.startswith("\x1b[<") and (text.endswith("M") or text.endswith("m")):
        try:
            params = text[3:-1].split(";")
            button = int(params[0])
            if button == 64:
                key.scroll_up = True
                return ("", key)
            if button == 65:
                key.scroll_down = True
                return ("", key)
        except (ValueError, IndexError):
            pass
        return ("", key)  # Other mouse events — consume but ignore

    # Meta (Alt) + key: ESC followed by a char
    if len(text) == 2 and text[0] == "\x1b" and text[1].isprintable():
        key.meta = True
        return (text[1], key)

    # Ctrl + letter (0x01-0x1a)
    if len(text) == 1 and 1 <= ord(text) <= 26:
        key.ctrl = True
        return (chr(ord("a") + ord(text) - 1), key)

    # Regular character(s)
    # Uppercase letter → shift detection (matching Ink's use-input.ts lines 240-242)
    if len(text) == 1 and text.isupper():
        key.shift = True

    return (text, key)
