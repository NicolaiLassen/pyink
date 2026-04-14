"""useFocus / useFocusManager hooks — tab-based focus navigation.

Port of Ink's ``src/hooks/use-focus.ts`` and ``src/hooks/use-focus-manager.ts``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyink.hooks.context import get_current_app
from pyink.hooks.use_effect import use_effect
from pyink.hooks.use_ref import use_ref
from pyink.hooks.use_state import use_state


@dataclass
class FocusHandle:
    is_focused: bool
    focus: Any  # callable


def use_focus(
    *, auto_focus: bool = False, is_active: bool = True, id: str | None = None
) -> FocusHandle:
    """Make a component focusable via Tab navigation.

    Port of Ink's useFocus (use-focus.ts lines 38–85).
    Enables raw mode when the component is active so Tab key is captured.

    Parameters
    ----------
    auto_focus : bool, optional
        Whether to automatically focus this component on mount.
    is_active : bool, optional
        Whether the component participates in focus navigation.
    id : str or None, optional
        An explicit focus identifier. If ``None``, a random id is generated.

    Returns
    -------
    FocusHandle
        A handle with ``is_focused`` state and a ``focus()`` method to
        programmatically focus the component.
    """
    app = get_current_app()
    import random

    focus_id_ref = use_ref(id or str(random.random())[2:7])
    is_focused, set_is_focused = use_state(False)

    # Effect 1: register/unregister with focus manager
    def register_effect():
        fid = focus_id_ref.current
        app.focus_manager.register(
            fid, set_is_focused, auto_focus=auto_focus, is_active=is_active
        )

        def cleanup():
            app.focus_manager.unregister(fid)

        return cleanup

    use_effect(register_effect, (is_active, auto_focus))

    # Effect 2: enable raw mode when active (use-focus.ts lines 67–77)
    def raw_mode_effect():
        if not is_active or not app.input_manager.is_raw_mode_supported:
            return None

        app.input_manager.enable_raw_mode()

        def cleanup():
            app.input_manager.disable_raw_mode()

        return cleanup

    use_effect(raw_mode_effect, (is_active,))

    def focus_self():
        app.focus_manager.focus(focus_id_ref.current)

    return FocusHandle(is_focused=is_focused, focus=focus_self)


@dataclass
class FocusManagerHandle:
    """Handle for programmatic focus control."""

    _app: Any

    def focus_next(self) -> None:
        """Move focus to the next focusable component."""
        self._app.focus_manager.focus_next()

    def focus_previous(self) -> None:
        """Move focus to the previous focusable component."""
        self._app.focus_manager.focus_previous()

    def focus(self, id: str) -> None:
        """Focus a specific component by id."""
        self._app.focus_manager.focus(id)

    def disable_focus(self) -> None:
        """Disable the focus management system."""
        self._app.focus_manager.enabled = False

    def enable_focus(self) -> None:
        """Enable the focus management system."""
        self._app.focus_manager.enabled = True


def use_focus_manager() -> FocusManagerHandle:
    """Programmatic focus control.

    Returns
    -------
    FocusManagerHandle
        A handle providing methods to navigate and control focus.
    """
    app = get_current_app()
    return FocusManagerHandle(_app=app)
