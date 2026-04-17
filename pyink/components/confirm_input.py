"""ConfirmInput component — y/n prompt.

Port of ink-confirm-input (https://github.com/kevva/ink-confirm-input).
"""
from __future__ import annotations

from collections.abc import Callable

from pyink.component import component
from pyink.hooks.use_input import use_input
from pyink.vnode import Box, Text


@component
def ConfirmInput(
    on_submit: Callable[[bool], None] | None = None,
    is_checked: bool = False,
    focus: bool = True,
    placeholder: str = "[y/n]",
):
    """Yes/no confirmation prompt.

    Answers: Y/y/Enter → True. N/n → False. ``is_checked`` controls
    whether Enter defaults to true.

    Parameters
    ----------
    on_submit : callable, optional
        Called as ``on_submit(confirmed: bool)``.
    is_checked : bool
        If True, Enter submits True. Otherwise Enter submits False.
    focus : bool
        Whether the prompt is active.
    placeholder : str
        Text shown next to the prompt.
    """
    def on_key(ch, key):
        if not focus:
            return

        if key.return_key:
            if on_submit:
                on_submit(is_checked)
            return

        if ch in ("y", "Y"):
            if on_submit:
                on_submit(True)
            return

        if ch in ("n", "N"):
            if on_submit:
                on_submit(False)
            return

    use_input(on_key, active=focus)

    return Box(
        Text(placeholder, dim=True),
        flex_direction="row",
    )
