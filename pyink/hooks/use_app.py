from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyink.hooks.context import get_current_app


@dataclass
class AppHandle:
    """Public handle returned by use_app()."""

    _app: Any

    def exit(self, code: int = 0) -> None:
        self._app.request_exit(code)

    @property
    def exit_code(self) -> int:
        return self._app._exit_code


def use_app() -> AppHandle:
    """Returns an AppHandle for controlling the application lifecycle."""
    app = get_current_app()
    return AppHandle(_app=app)
