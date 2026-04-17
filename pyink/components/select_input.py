"""SelectInput component — arrow-key selectable list.

Port of ink-select-input (https://github.com/vadimdemedes/ink-select-input).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pyink.component import component
from pyink.hooks.use_input import use_input
from pyink.hooks.use_state import use_state
from pyink.vnode import Box, Text


@dataclass
class SelectItem:
    """A single item in a SelectInput list.

    Attributes
    ----------
    label : str
        Text shown to the user.
    value : Any
        Value returned on selection.
    key : str or None
        Optional unique key (defaults to label).
    """

    label: str
    value: Any = None
    key: str | None = None


@component
def SelectInput(
    items: list = None,
    on_select: Callable | None = None,
    on_highlight: Callable | None = None,
    initial_index: int = 0,
    indicator: str = "\u276f",  # ❯
    limit: int | None = None,
    focus: bool = True,
):
    """Arrow-key selectable list.

    Parameters
    ----------
    items : list[SelectItem]
        Items to display.
    on_select : callable, optional
        Called as ``on_select(item)`` when Enter is pressed.
    on_highlight : callable, optional
        Called as ``on_highlight(item)`` when selection changes.
    initial_index : int
        Index of initially-selected item.
    indicator : str
        Character shown next to selected item.
    limit : int or None
        Max visible items (None = show all).
    focus : bool
        Whether arrow keys are active.
    """
    items = items or []
    n = len(items)

    selected, set_selected = use_state(
        min(initial_index, max(0, n - 1)),
    )
    scroll_top, set_scroll_top = use_state(0)

    viewport = limit if limit else n

    # Ensure selected is visible in viewport
    if selected < scroll_top:
        scroll_top = selected
    elif selected >= scroll_top + viewport:
        scroll_top = selected - viewport + 1

    def on_key(ch, key):
        if not focus or n == 0:
            return

        if key.up_arrow:
            new_idx = max(0, selected - 1)
            set_selected(new_idx)
            if new_idx < scroll_top:
                set_scroll_top(new_idx)
            if on_highlight:
                on_highlight(items[new_idx])
            return

        if key.down_arrow:
            new_idx = min(n - 1, selected + 1)
            set_selected(new_idx)
            if new_idx >= scroll_top + viewport:
                set_scroll_top(new_idx - viewport + 1)
            if on_highlight:
                on_highlight(items[new_idx])
            return

        if key.return_key:
            if on_select and 0 <= selected < n:
                on_select(items[selected])

    use_input(on_key, active=focus)

    # Render visible window
    rows = []
    end = min(n, scroll_top + viewport)
    for i in range(scroll_top, end):
        item = items[i]
        is_sel = i == selected
        prefix = indicator if is_sel else " "
        rows.append(Text(
            f" {prefix} {item.label}",
            color="cyan" if is_sel else None,
            bold=is_sel,
        ))

    return Box(*rows, flex_direction="column")
