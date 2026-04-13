"""1:1 port of Ink's log-update.ts (createStandard) and terminal utilities.

Source: /tmp/ink-reference/src/log-update.ts lines 31-172
Source: /tmp/ink-reference/src/cursor-helpers.ts
Source: /tmp/ink-reference/src/write-synchronized.ts
"""
from __future__ import annotations

import shutil


def get_terminal_size() -> tuple[int, int]:
    """Returns (columns, rows)."""
    try:
        size = shutil.get_terminal_size()
        return (size.columns, size.lines)
    except Exception:
        return (80, 24)


# ── ANSI escapes (matching ansi-escapes npm package) ──

HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
ERASE_LINE = "\x1b[2K"       # CSI 2 K — erase entire line
CURSOR_UP = "\x1b[A"         # CSI A — cursor up 1
CURSOR_LEFT = "\x1b[G"       # CSI G — cursor to column 1
CLEAR_TERMINAL = "\x1bc"     # RIS — full reset
BSU = "\x1b[?2026h"          # Begin Synchronized Update
ESU = "\x1b[?2026l"          # End Synchronized Update


def erase_lines(count: int) -> str:
    """Port of ansi-escapes eraseLines().

    Source: ansi-escapes npm package
    For each line: erase it, then cursor up (except last).
    Finally cursor to column 1.
    """
    if count == 0:
        return ""

    clear = ""
    for i in range(count):
        clear += ERASE_LINE
        if i < count - 1:
            clear += CURSOR_UP

    clear += CURSOR_LEFT
    return clear


def visible_line_count(lines: list[str], s: str) -> int:
    """Port of log-update.ts visibleLineCount (lines 28-29).

    Count visible lines — ignore trailing empty element from split('\\n')
    when string ends with '\\n'.
    """
    return len(lines) - 1 if s.endswith("\n") else len(lines)


class LogUpdate:
    """1:1 port of Ink's log-update createStandard().

    Source: /tmp/ink-reference/src/log-update.ts lines 31-172
    """

    def __init__(self, stream: object) -> None:
        self.stream = stream
        self.previous_line_count: int = 0
        self.previous_output: str = ""
        self.has_hidden_cursor: bool = False

    def __call__(self, s: str) -> bool:
        """render() — port of log-update.ts lines 55-107.

        Hides cursor, erases previous output, writes new output.
        Returns True if output was written.
        """
        # Line 56-59: hide cursor on first render
        if not self.has_hidden_cursor:
            self._write(HIDE_CURSOR)
            self.has_hidden_cursor = True

        # Line 70-72: skip if unchanged
        if s == self.previous_output:
            return False

        # Line 74: split into lines
        lines = s.split("\n")

        # Lines 89-101: erase previous + write new
        self.previous_output = s
        self._write(
            erase_lines(self.previous_line_count) + s
        )
        self._flush()
        # Line 101: track line count for next erase
        self.previous_line_count = len(lines)

        return True

    def clear(self) -> None:
        """Port of log-update.ts lines 109-120."""
        self._write(erase_lines(self.previous_line_count))
        self._flush()
        self.previous_output = ""
        self.previous_line_count = 0

    def done(self) -> None:
        """Port of log-update.ts lines 122-132."""
        self.previous_output = ""
        self.previous_line_count = 0
        self._write(SHOW_CURSOR)
        self._flush()
        self.has_hidden_cursor = False

    def reset(self) -> None:
        """Port of log-update.ts lines 134-139."""
        self.previous_output = ""
        self.previous_line_count = 0

    def sync(self, s: str) -> None:
        """Port of log-update.ts lines 141-161.

        Update internal state without writing output (used after clearTerminal).
        """
        lines = s.split("\n")
        self.previous_output = s
        self.previous_line_count = len(lines)

    def will_render(self, s: str) -> bool:
        """Port of log-update.ts line 169."""
        return s != self.previous_output

    def _write(self, data: str) -> None:
        try:
            self.stream.write(data)  # type: ignore
        except (BrokenPipeError, OSError):
            pass

    def _flush(self) -> None:
        try:
            self.stream.flush()  # type: ignore
        except (BrokenPipeError, OSError):
            pass
