"""TextInput component — single-line text input with cursor.

Port of ink-text-input (https://github.com/vadimdemedes/ink-text-input).
Controlled component: parent provides ``value`` and ``on_change``.
"""
from __future__ import annotations

from collections.abc import Callable

from pyink.component import component
from pyink.hooks.use_input import use_input
from pyink.hooks.use_state import use_state
from pyink.vnode import Box, Text


@component
def TextInput(
    value: str = "",
    on_change: Callable[[str], None] | None = None,
    on_submit: Callable[[str], None] | None = None,
    placeholder: str = "",
    focus: bool = True,
    mask: str | None = None,
    show_cursor: bool = True,
    highlight_pasted_text: bool = False,
):
    """Single-line text input with cursor.

    Parameters
    ----------
    value : str
        Current text value (controlled by parent).
    on_change : callable, optional
        Called as ``on_change(new_value)`` on every edit.
    on_submit : callable, optional
        Called as ``on_submit(value)`` on Enter.
    placeholder : str
        Shown when value is empty.
    focus : bool
        Whether input is active (listens to keys).
    mask : str or None
        If set, display each char as this (e.g. ``"*"`` for passwords).
    show_cursor : bool
        Show the inverse-colored cursor.
    highlight_pasted_text : bool
        Visually highlight the last-pasted text (not yet implemented).
    """
    cursor, set_cursor = use_state(len(value))

    def on_key(ch, key):
        if not focus:
            return

        if key.return_key:
            if on_submit:
                on_submit(value)
            return

        if key.left_arrow:
            set_cursor(lambda c: max(0, c - 1))
            return

        if key.right_arrow:
            set_cursor(lambda c: min(len(value), c + 1))
            return

        if key.home:
            set_cursor(0)
            return

        if key.end:
            set_cursor(len(value))
            return

        if key.backspace or key.delete:
            pos = cursor
            if pos > 0 and on_change:
                on_change(value[: pos - 1] + value[pos:])
                set_cursor(lambda c: max(0, c - 1))
            return

        if ch and not key.ctrl and not key.meta and not key.escape:
            pos = cursor
            if on_change:
                on_change(value[:pos] + ch + value[pos:])
                set_cursor(lambda c: c + len(ch))

    use_input(on_key, active=focus)

    # Display
    display_value = value if mask is None else mask * len(value)

    if not display_value and placeholder:
        # Show placeholder, cursor on first char of placeholder
        if show_cursor and focus:
            return Box(
                Text(placeholder[0], inverse=True),
                Text(placeholder[1:], dim=True),
                flex_direction="row",
            )
        return Text(placeholder, dim=True)

    if not show_cursor or not focus:
        return Text(display_value)

    # With cursor
    before = display_value[:cursor]
    char_at = display_value[cursor] if cursor < len(display_value) else " "
    after = display_value[cursor + 1:] if cursor < len(display_value) else ""

    return Box(
        Text(before),
        Text(char_at, inverse=True),
        Text(after),
        flex_direction="row",
    )
