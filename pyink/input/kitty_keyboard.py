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


# ── Kitty query response detection (port of ink.tsx lines 37–116) ──

_ESC_BYTE = 0x1B
_OPEN_BRACKET_BYTE = 0x5B
_QUESTION_MARK_BYTE = 0x3F
_LETTER_U_BYTE = 0x75
_ZERO_BYTE = 0x30
_NINE_BYTE = 0x39


def _is_digit_byte(byte: int) -> bool:
    return _ZERO_BYTE <= byte <= _NINE_BYTE


def match_kitty_query_response(
    buffer: list[int], start_index: int
) -> dict | None:
    """Match a kitty query response in a byte buffer.

    Port of ink.tsx ``matchKittyQueryResponse`` (lines 51–82).

    Returns
    -------
    dict or None
        ``{'state': 'complete', 'end_index': int}`` or
        ``{'state': 'partial'}`` or ``None``.
    """
    if (
        start_index + 2 >= len(buffer)
        or buffer[start_index] != _ESC_BYTE
        or buffer[start_index + 1] != _OPEN_BRACKET_BYTE
        or buffer[start_index + 2] != _QUESTION_MARK_BYTE
    ):
        return None

    index = start_index + 3
    digits_start = index
    while index < len(buffer) and _is_digit_byte(buffer[index]):
        index += 1

    if index == digits_start:
        return None

    if index == len(buffer):
        return {"state": "partial"}

    if buffer[index] == _LETTER_U_BYTE:
        return {"state": "complete", "end_index": index}

    return None


def has_complete_kitty_query_response(buffer: list[int]) -> bool:
    """Check if buffer contains a complete kitty query response.

    Port of ink.tsx ``hasCompleteKittyQueryResponse`` (lines 84–93).
    """
    for index in range(len(buffer)):
        match = match_kitty_query_response(buffer, index)
        if match and match["state"] == "complete":
            return True
    return False


def strip_kitty_query_responses(buffer: list[int]) -> list[int]:
    """Strip kitty query responses and trailing partials from buffer.

    Port of ink.tsx ``stripKittyQueryResponsesAndTrailingPartial`` (lines 95–116).
    Returns the remaining non-response bytes.
    """
    kept: list[int] = []
    index = 0
    while index < len(buffer):
        match = match_kitty_query_response(buffer, index)
        if match and match["state"] == "complete":
            index = match["end_index"] + 1
            continue
        if match and match["state"] == "partial":
            break
        kept.append(buffer[index])
        index += 1
    return kept
