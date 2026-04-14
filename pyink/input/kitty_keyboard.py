"""Kitty keyboard protocol support matching Ink's kitty-keyboard.ts 1:1.

See: https://sw.kovidgoyal.net/kitty/keyboard-protocol/
"""
from __future__ import annotations

from typing import Literal

# Protocol capability flags
kitty_flags = {
    "disambiguate_escape_codes": 1,
    "report_event_types": 2,
    "report_alternate_keys": 4,
    "report_all_keys_as_escape_codes": 8,
    "report_associated_text": 16,
}

KittyFlagName = Literal[
    "disambiguate_escape_codes",
    "report_event_types",
    "report_alternate_keys",
    "report_all_keys_as_escape_codes",
    "report_associated_text",
]

# Modifier bits (actual modifier value is modifiers - 1 per protocol spec)
kitty_modifiers = {
    "shift": 1,
    "alt": 2,
    "ctrl": 4,
    "super": 8,
    "hyper": 16,
    "meta": 32,
    "caps_lock": 64,
    "num_lock": 128,
}


def resolve_flags(flags: list[KittyFlagName]) -> int:
    """Convert an array of flag names to the corresponding bitmask.

    Parameters
    ----------
    flags : list[KittyFlagName]
        List of Kitty protocol capability flag names to combine.

    Returns
    -------
    int
        The combined bitmask value.
    """
    result = 0
    for flag in flags:
        result |= kitty_flags.get(flag, 0)
    return result


# Escape sequences for enabling/disabling kitty keyboard protocol
def enable_kitty_keyboard(flags: int = 1) -> str:
    """Generate escape sequence to enable kitty keyboard protocol.

    Parameters
    ----------
    flags : int, optional
        Bitmask of protocol capabilities to enable (default ``1``).

    Returns
    -------
    str
        The ANSI escape sequence.
    """
    return f"\x1b[>{flags}u"


def disable_kitty_keyboard() -> str:
    """Generate escape sequence to disable kitty keyboard protocol.

    Returns
    -------
    str
        The ANSI escape sequence.
    """
    return "\x1b[<u"


def query_kitty_keyboard() -> str:
    """Generate escape sequence to query kitty keyboard support.

    Returns
    -------
    str
        The ANSI escape sequence.
    """
    return "\x1b[?u"
