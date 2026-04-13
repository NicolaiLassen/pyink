from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyink.hooks.context import get_current_app


@dataclass
class StdoutHandle:
    _app: Any

    def write(self, data: str) -> None:
        self._app.stdout.write(data)
        self._app.stdout.flush()

    @property
    def columns(self) -> int:
        import shutil
        return shutil.get_terminal_size().columns

    @property
    def rows(self) -> int:
        import shutil
        return shutil.get_terminal_size().lines


@dataclass
class StderrHandle:
    _app: Any

    def write(self, data: str) -> None:
        import sys
        sys.stderr.write(data)
        sys.stderr.flush()


@dataclass
class StdinHandle:
    _app: Any

    @property
    def is_raw_mode_supported(self) -> bool:
        return self._app.input_manager.is_raw_mode_supported

    def set_raw_mode(self, enabled: bool) -> None:
        if enabled:
            self._app.input_manager.enable_raw_mode()
        else:
            self._app.input_manager.disable_raw_mode()


def use_stdout() -> StdoutHandle:
    return StdoutHandle(_app=get_current_app())


def use_stderr() -> StderrHandle:
    return StderrHandle(_app=get_current_app())


def use_stdin() -> StdinHandle:
    return StdinHandle(_app=get_current_app())
