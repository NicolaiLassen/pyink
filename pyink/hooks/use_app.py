"""useApp hook — control the application lifecycle.

Port of Ink's ``src/hooks/use-app.ts``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyink.hooks.context import get_current_app


@dataclass
class AppHandle:
    """Public handle returned by use_app() for controlling the application lifecycle."""

    _app: Any

    def exit(self, code: int = 0) -> None:
        """Request the application to exit.

        Parameters
        ----------
        code : int, optional
            The exit code to use. Defaults to 0.
        """
        self._app.request_exit(code)

    @property
    def exit_code(self) -> int:
        """The current exit code of the application."""
        return self._app._exit_code

    async def wait_until_render_flush(self) -> None:
        """Wait until pending render output is flushed to stdout.

        Port of Ink's AppContext.waitUntilRenderFlush.
        """
        if hasattr(self._app, "wait_until_render_flush"):
            await self._app.wait_until_render_flush()


def use_app() -> AppHandle:
    """Returns an AppHandle for controlling the application lifecycle.

    Returns
    -------
    AppHandle
        A handle providing methods to control the app (e.g. exit,
        wait_until_render_flush).
    """
    app = get_current_app()
    return AppHandle(_app=app)
