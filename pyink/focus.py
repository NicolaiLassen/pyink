from __future__ import annotations

from collections.abc import Callable


class FocusManager:
    """Manages Tab-based focus navigation between components."""

    def __init__(self) -> None:
        self._items: list[FocusItem] = []
        self._focused_id: str | None = None
        self.enabled: bool = True

    def register(
        self,
        focus_id: str,
        set_is_focused: Callable[[bool], None],
        *,
        auto_focus: bool = False,
        is_active: bool = True,
    ) -> None:
        item = FocusItem(
            id=focus_id,
            set_is_focused=set_is_focused,
            is_active=is_active,
        )
        self._items.append(item)

        if auto_focus and self._focused_id is None:
            self.focus(focus_id)

    def unregister(self, focus_id: str) -> None:
        self._items = [i for i in self._items if i.id != focus_id]
        if self._focused_id == focus_id:
            self._focused_id = None
            # Focus next available
            active = [i for i in self._items if i.is_active]
            if active:
                self.focus(active[0].id)

    def focus(self, focus_id: str) -> None:
        if not self.enabled:
            return

        # Unfocus current
        if self._focused_id:
            for item in self._items:
                if item.id == self._focused_id:
                    item.set_is_focused(False)

        self._focused_id = focus_id

        # Focus new
        for item in self._items:
            if item.id == focus_id:
                item.set_is_focused(True)
                break

    def focus_next(self) -> None:
        if not self.enabled:
            return

        active = [i for i in self._items if i.is_active]
        if not active:
            return

        if self._focused_id is None:
            self.focus(active[0].id)
            return

        ids = [i.id for i in active]
        try:
            idx = ids.index(self._focused_id)
            next_idx = (idx + 1) % len(ids)
            self.focus(ids[next_idx])
        except ValueError:
            self.focus(ids[0])

    def focus_previous(self) -> None:
        if not self.enabled:
            return

        active = [i for i in self._items if i.is_active]
        if not active:
            return

        if self._focused_id is None:
            self.focus(active[-1].id)
            return

        ids = [i.id for i in active]
        try:
            idx = ids.index(self._focused_id)
            prev_idx = (idx - 1) % len(ids)
            self.focus(ids[prev_idx])
        except ValueError:
            self.focus(ids[-1])

    def reset(self) -> None:
        """Clear all focus state."""
        for item in self._items:
            item.set_is_focused(False)
        self._focused_id = None
        self._items.clear()


class FocusItem:
    def __init__(
        self,
        id: str,
        set_is_focused: Callable[[bool], None],
        is_active: bool = True,
    ) -> None:
        self.id = id
        self.set_is_focused = set_is_focused
        self.is_active = is_active
