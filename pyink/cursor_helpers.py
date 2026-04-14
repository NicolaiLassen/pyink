"""Cursor positioning helpers.

1:1 port of Ink's ``src/cursor-helpers.ts``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CursorPosition:
    """A cursor position in the terminal."""
    x: int
    y: int


SHOW_CURSOR = "\x1b[?25h"
HIDE_CURSOR = "\x1b[?25l"


def cursor_position_changed(
    a: CursorPosition | None, b: CursorPosition | None
) -> bool:
    """Compare two cursor positions. Returns True if they differ.

    Port of cursor-helpers.ts ``cursorPositionChanged``.
    """
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    return a.x != b.x or a.y != b.y


def build_cursor_suffix(
    visible_line_count: int, cursor_position: CursorPosition | None
) -> str:
    """Build escape sequence to move cursor from bottom of output to target position.

    Port of cursor-helpers.ts ``buildCursorSuffix``.
    Assumes cursor is at (col 0, line visible_line_count).
    """
    if cursor_position is None:
        return ""

    move_up = visible_line_count - cursor_position.y
    result = ""
    if move_up > 0:
        result += f"\x1b[{move_up}A"  # cursor up
    # cursor to column (Ink's ansiEscapes.cursorTo)
    result += f"\x1b[{cursor_position.x}G"
    result += SHOW_CURSOR
    return result


def build_return_to_bottom(
    previous_line_count: int,
    previous_cursor_position: CursorPosition | None,
) -> str:
    """Build escape sequence to return cursor from previous position to bottom.

    Port of cursor-helpers.ts ``buildReturnToBottom``.
    """
    if previous_cursor_position is None:
        return ""

    down = previous_line_count - 1 - previous_cursor_position.y
    result = ""
    if down > 0:
        result += f"\x1b[{down}B"  # cursor down
    result += "\x1b[G"  # cursor to column 1
    return result


def build_cursor_only_sequence(
    cursor_was_shown: bool,
    previous_line_count: int,
    previous_cursor_position: CursorPosition | None,
    visible_line_count: int,
    cursor_position: CursorPosition | None,
) -> str:
    """Build escape sequence for cursor-only updates (output unchanged).

    Port of cursor-helpers.ts ``buildCursorOnlySequence``.
    """
    hide_prefix = HIDE_CURSOR if cursor_was_shown else ""
    return_to_bottom = build_return_to_bottom(
        previous_line_count, previous_cursor_position
    )
    cursor_suffix = build_cursor_suffix(visible_line_count, cursor_position)
    return hide_prefix + return_to_bottom + cursor_suffix


def build_return_to_bottom_prefix(
    cursor_was_shown: bool,
    previous_line_count: int,
    previous_cursor_position: CursorPosition | None,
) -> str:
    """Build prefix that hides cursor and returns to bottom before erasing.

    Port of cursor-helpers.ts ``buildReturnToBottomPrefix``.
    """
    if not cursor_was_shown:
        return ""

    return HIDE_CURSOR + build_return_to_bottom(
        previous_line_count, previous_cursor_position
    )
