from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyink.hooks.context import get_current_app


@dataclass
class StdoutHandle:
    """Handle for writing to stdout and querying terminal dimensions.

    Parameters
    ----------
    _app : Any
        The internal application instance (private).
    """

    _app: Any

    def write(self, data: str) -> None:
        """Write data to stdout and flush.

        Parameters
        ----------
        data : str
            The string to write to stdout.
        """
        self._app.stdout.write(data)
        self._app.stdout.flush()

    @property
    def columns(self) -> int:
        """The number of terminal columns.

        Returns
        -------
        int
            Terminal width in columns.
        """
        import shutil
        return shutil.get_terminal_size().columns

    @property
    def rows(self) -> int:
        """The number of terminal rows.

        Returns
        -------
        int
            Terminal height in rows.
        """
        import shutil
        return shutil.get_terminal_size().lines


@dataclass
class StderrHandle:
    """Handle for writing to stderr.

    Parameters
    ----------
    _app : Any
        The internal application instance (private).
    """

    _app: Any

    def write(self, data: str) -> None:
        """Write data to stderr and flush.

        Parameters
        ----------
        data : str
            The string to write to stderr.
        """
        import sys
        sys.stderr.write(data)
        sys.stderr.flush()


@dataclass
class StdinHandle:
    """Handle for stdin raw mode control.

    Parameters
    ----------
    _app : Any
        The internal application instance (private).
    """

    _app: Any

    @property
    def is_raw_mode_supported(self) -> bool:
        """Whether raw mode is supported by the terminal.

        Returns
        -------
        bool
            True if raw mode is supported.
        """
        return self._app.input_manager.is_raw_mode_supported

    def set_raw_mode(self, enabled: bool) -> None:
        """Enable or disable raw mode on stdin.

        Parameters
        ----------
        enabled : bool
            If ``True``, enable raw mode; if ``False``, disable it.
        """
        if enabled:
            self._app.input_manager.enable_raw_mode()
        else:
            self._app.input_manager.disable_raw_mode()


def use_stdout() -> StdoutHandle:
    """Get a handle for writing to stdout.

    Returns
    -------
    StdoutHandle
        A handle with ``write()``, ``columns``, and ``rows``.
    """
    return StdoutHandle(_app=get_current_app())


def use_stderr() -> StderrHandle:
    """Get a handle for writing to stderr.

    Returns
    -------
    StderrHandle
        A handle with a ``write()`` method.
    """
    return StderrHandle(_app=get_current_app())


def use_stdin() -> StdinHandle:
    """Get a handle for stdin raw mode control.

    Returns
    -------
    StdinHandle
        A handle with ``is_raw_mode_supported`` and ``set_raw_mode()``.
    """
    return StdinHandle(_app=get_current_app())
