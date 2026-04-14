"""Terminal utilities and log-update rendering.

1:1 port of Ink's ``src/log-update.ts``, ``src/cursor-helpers.ts``,
and ``src/write-synchronized.ts``.
"""
from __future__ import annotations

import os
import shutil

from pyink.cursor_helpers import (
    CursorPosition,
    build_cursor_only_sequence,
    build_cursor_suffix,
    build_return_to_bottom_prefix,
    cursor_position_changed,
)

# Re-export CursorPosition for backwards compatibility
__all__ = ["CursorPosition", "LogUpdate", "get_terminal_size"]


def get_terminal_size() -> tuple[int, int]:
    """Returns (columns, rows).

    Returns
    -------
    tuple[int, int]
        A ``(columns, rows)`` pair. Falls back to ``(80, 24)`` on error.
    """
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
CURSOR_NEXT_LINE = "\x1b[E"  # CSI E — cursor to next line col 1
CURSOR_TO_COL_0 = "\x1b[G"   # CSI G — cursor to column 1
ERASE_END_LINE = "\x1b[K"    # CSI K — erase to end of line


def erase_lines(count: int) -> str:
    """Port of ansi-escapes eraseLines().

    Parameters
    ----------
    count : int
        Number of lines to erase.

    Returns
    -------
    str
        The ANSI escape sequence that erases the requested lines.
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
    """Count visible lines — ignore trailing empty element from split.

    Port of log-update.ts ``visibleLineCount``.
    """
    return len(lines) - 1 if s.endswith("\n") else len(lines)


def should_synchronize(stream: object, interactive: bool = True) -> bool:
    """Check if synchronized output (BSU/ESU) should be used.

    Port of write-synchronized.ts ``shouldSynchronize``.

    Parameters
    ----------
    stream : object
        The output stream (e.g. ``sys.stdout``).
    interactive : bool
        Whether the app is in interactive mode.

    Returns
    -------
    bool
        True if the stream is a TTY and we're in interactive mode.
    """
    is_tty = hasattr(stream, "isatty") and stream.isatty()
    ci = os.environ.get("CI", "").lower() in ("true", "1", "yes")
    return is_tty and (interactive and not ci)


class LogUpdate:
    """Log-update renderer with cursor position support.

    Port of Ink's ``log-update.ts`` ``createStandard`` (lines 31–172).

    Parameters
    ----------
    stream : object
        A writable stream with ``.write()`` and ``.flush()`` methods.
    """

    def __init__(self, stream: object) -> None:
        self.stream = stream
        self.previous_line_count: int = 0
        self.previous_output: str = ""
        self.has_hidden_cursor: bool = False

        # Cursor state (port of log-update.ts lines 38-41)
        self._cursor_position: CursorPosition | None = None
        self._cursor_dirty: bool = False
        self._previous_cursor_position: CursorPosition | None = None
        self._cursor_was_shown: bool = False

    def _get_active_cursor(self) -> CursorPosition | None:
        return self._cursor_position if self._cursor_dirty else None

    def _has_changes(self, s: str, active_cursor: CursorPosition | None) -> bool:
        changed = cursor_position_changed(
            active_cursor, self._previous_cursor_position
        )
        return s != self.previous_output or changed

    def __call__(self, s: str) -> bool:
        """Render output. Port of log-update.ts lines 55–107.

        Parameters
        ----------
        s : str
            The full string to render to the terminal.

        Returns
        -------
        bool
            ``True`` if output was written, ``False`` if unchanged.
        """
        if not self.has_hidden_cursor:
            self._write(HIDE_CURSOR)
            self.has_hidden_cursor = True

        active_cursor = self._get_active_cursor()
        self._cursor_dirty = False
        cursor_changed = cursor_position_changed(
            active_cursor, self._previous_cursor_position
        )

        if not self._has_changes(s, active_cursor):
            return False

        lines = s.split("\n")
        vis_count = visible_line_count(lines, s)
        cursor_suffix = build_cursor_suffix(vis_count, active_cursor)

        if s == self.previous_output and cursor_changed:
            # Cursor-only update
            self._write(
                build_cursor_only_sequence(
                    self._cursor_was_shown,
                    self.previous_line_count,
                    self._previous_cursor_position,
                    vis_count,
                    active_cursor,
                )
            )
        else:
            self.previous_output = s
            return_prefix = build_return_to_bottom_prefix(
                self._cursor_was_shown,
                self.previous_line_count,
                self._previous_cursor_position,
            )
            self._write(
                return_prefix
                + erase_lines(self.previous_line_count)
                + s
                + cursor_suffix
            )
            self.previous_line_count = len(lines)

        self._previous_cursor_position = (
            CursorPosition(active_cursor.x, active_cursor.y)
            if active_cursor
            else None
        )
        self._cursor_was_shown = active_cursor is not None
        self._flush()
        return True

    def clear(self) -> None:
        """Port of log-update.ts lines 109–120."""
        prefix = build_return_to_bottom_prefix(
            self._cursor_was_shown,
            self.previous_line_count,
            self._previous_cursor_position,
        )
        self._write(prefix + erase_lines(self.previous_line_count))
        self._flush()
        self.previous_output = ""
        self.previous_line_count = 0
        self._previous_cursor_position = None
        self._cursor_was_shown = False

    def done(self) -> None:
        """Port of log-update.ts lines 122–132."""
        self.previous_output = ""
        self.previous_line_count = 0
        self._previous_cursor_position = None
        self._cursor_was_shown = False
        self._write(SHOW_CURSOR)
        self._flush()
        self.has_hidden_cursor = False

    def reset(self) -> None:
        """Port of log-update.ts lines 134–139."""
        self.previous_output = ""
        self.previous_line_count = 0
        self._previous_cursor_position = None
        self._cursor_was_shown = False

    def sync(self, s: str) -> None:
        """Update internal state without writing output.

        Port of log-update.ts lines 141–161.
        """
        active_cursor = self._get_active_cursor()
        self._cursor_dirty = False

        lines = s.split("\n")
        self.previous_output = s
        self.previous_line_count = len(lines)

        if not active_cursor and self._cursor_was_shown:
            self._write(HIDE_CURSOR)

        if active_cursor:
            self._write(
                build_cursor_suffix(
                    visible_line_count(lines, s), active_cursor
                )
            )

        self._previous_cursor_position = (
            CursorPosition(active_cursor.x, active_cursor.y)
            if active_cursor
            else None
        )
        self._cursor_was_shown = active_cursor is not None

    def set_cursor_position(self, position: CursorPosition | None) -> None:
        """Set cursor position for next render.

        Port of log-update.ts lines 163–166.
        """
        self._cursor_position = position
        self._cursor_dirty = True

    def is_cursor_dirty(self) -> bool:
        """Port of log-update.ts line 168."""
        return self._cursor_dirty

    def will_render(self, s: str) -> bool:
        """Port of log-update.ts line 169."""
        return self._has_changes(s, self._get_active_cursor())

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


class LogUpdateIncremental:
    """Incremental log-update — only rewrites changed lines.

    Port of Ink's ``log-update.ts`` ``createIncremental`` (lines 174–375).

    Parameters
    ----------
    stream : object
        A writable stream with ``.write()`` and ``.flush()`` methods.
    """

    def __init__(self, stream: object) -> None:
        self.stream = stream
        self._previous_lines: list[str] = []
        self.previous_output: str = ""
        self.has_hidden_cursor: bool = False
        self.previous_line_count: int = 0

        self._cursor_position: CursorPosition | None = None
        self._cursor_dirty: bool = False
        self._previous_cursor_position: CursorPosition | None = None
        self._cursor_was_shown: bool = False

    def _get_active_cursor(self) -> CursorPosition | None:
        return self._cursor_position if self._cursor_dirty else None

    def _has_changes(self, s: str, active_cursor: CursorPosition | None) -> bool:
        changed = cursor_position_changed(
            active_cursor, self._previous_cursor_position
        )
        return s != self.previous_output or changed

    def __call__(self, s: str) -> bool:
        """Render with incremental line updates."""
        if not self.has_hidden_cursor:
            self._write(HIDE_CURSOR)
            self.has_hidden_cursor = True

        active_cursor = self._get_active_cursor()
        self._cursor_dirty = False
        cursor_changed = cursor_position_changed(
            active_cursor, self._previous_cursor_position
        )

        if not self._has_changes(s, active_cursor):
            return False

        next_lines = s.split("\n")
        vis_count = visible_line_count(next_lines, s)
        previous_visible = visible_line_count(self._previous_lines, self.previous_output)

        if s == self.previous_output and cursor_changed:
            self._write(
                build_cursor_only_sequence(
                    self._cursor_was_shown,
                    len(self._previous_lines),
                    self._previous_cursor_position,
                    vis_count,
                    active_cursor,
                )
            )
            self._previous_cursor_position = (
                CursorPosition(active_cursor.x, active_cursor.y)
                if active_cursor
                else None
            )
            self._cursor_was_shown = active_cursor is not None
            self._flush()
            return True

        return_prefix = build_return_to_bottom_prefix(
            self._cursor_was_shown,
            len(self._previous_lines),
            self._previous_cursor_position,
        )

        if s == "\n" or not self.previous_output:
            cursor_suffix = build_cursor_suffix(vis_count, active_cursor)
            self._write(
                return_prefix
                + erase_lines(len(self._previous_lines))
                + s
                + cursor_suffix
            )
            self._cursor_was_shown = active_cursor is not None
            self._previous_cursor_position = (
                CursorPosition(active_cursor.x, active_cursor.y)
                if active_cursor
                else None
            )
            self.previous_output = s
            self._previous_lines = next_lines
            self.previous_line_count = len(next_lines)
            self._flush()
            return True

        has_trailing_newline = s.endswith("\n")
        buf: list[str] = [return_prefix]

        if vis_count < previous_visible:
            prev_had_trailing = self.previous_output.endswith("\n")
            extra_slot = 1 if prev_had_trailing else 0
            buf.append(
                erase_lines(previous_visible - vis_count + extra_slot)
                + f"\x1b[{vis_count}A"
            )
        else:
            buf.append(f"\x1b[{len(self._previous_lines) - 1}A")

        for i in range(vis_count):
            is_last = i == vis_count - 1

            if i < len(self._previous_lines) and next_lines[i] == self._previous_lines[i]:
                if not is_last or has_trailing_newline:
                    buf.append(CURSOR_NEXT_LINE)
                continue

            line_text = next_lines[i] if i < len(next_lines) else ""
            buf.append(
                CURSOR_TO_COL_0
                + line_text
                + ERASE_END_LINE
                + ("" if is_last and not has_trailing_newline else "\n")
            )

        cursor_suffix = build_cursor_suffix(vis_count, active_cursor)
        buf.append(cursor_suffix)

        self._write("".join(buf))

        self._cursor_was_shown = active_cursor is not None
        self._previous_cursor_position = (
            CursorPosition(active_cursor.x, active_cursor.y)
            if active_cursor
            else None
        )
        self.previous_output = s
        self._previous_lines = next_lines
        self.previous_line_count = len(next_lines)
        self._flush()
        return True

    def clear(self) -> None:
        prefix = build_return_to_bottom_prefix(
            self._cursor_was_shown,
            len(self._previous_lines),
            self._previous_cursor_position,
        )
        self._write(prefix + erase_lines(len(self._previous_lines)))
        self._flush()
        self.previous_output = ""
        self._previous_lines = []
        self._previous_cursor_position = None
        self._cursor_was_shown = False

    def done(self) -> None:
        self.previous_output = ""
        self._previous_lines = []
        self._previous_cursor_position = None
        self._cursor_was_shown = False
        self._write(SHOW_CURSOR)
        self._flush()
        self.has_hidden_cursor = False

    def reset(self) -> None:
        self.previous_output = ""
        self._previous_lines = []
        self._previous_cursor_position = None
        self._cursor_was_shown = False

    def sync(self, s: str) -> None:
        active_cursor = self._get_active_cursor()
        self._cursor_dirty = False

        lines = s.split("\n")
        self.previous_output = s
        self._previous_lines = lines
        self.previous_line_count = len(lines)

        if not active_cursor and self._cursor_was_shown:
            self._write(HIDE_CURSOR)

        if active_cursor:
            self._write(
                build_cursor_suffix(
                    visible_line_count(lines, s), active_cursor
                )
            )

        self._previous_cursor_position = (
            CursorPosition(active_cursor.x, active_cursor.y)
            if active_cursor
            else None
        )
        self._cursor_was_shown = active_cursor is not None

    def set_cursor_position(self, position: CursorPosition | None) -> None:
        self._cursor_position = position
        self._cursor_dirty = True

    def is_cursor_dirty(self) -> bool:
        return self._cursor_dirty

    def will_render(self, s: str) -> bool:
        return self._has_changes(s, self._get_active_cursor())

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


def create_log_update(
    stream: object, *, incremental: bool = False
) -> LogUpdate | LogUpdateIncremental:
    """Factory matching Ink's ``logUpdate.create``.

    Parameters
    ----------
    stream : object
        Output stream.
    incremental : bool
        Use incremental (line-diff) mode instead of full-redraw.

    Returns
    -------
    LogUpdate or LogUpdateIncremental
    """
    if incremental:
        return LogUpdateIncremental(stream)
    return LogUpdate(stream)
