"""Input manager matching Ink's stdin handling.

Supports raw mode, bracketed paste mode, and dispatches keypresses
and paste events to listeners via the input parser.
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable

from pyink.input.input_parser import PasteEvent, create_input_parser
from pyink.input.keys import Key, parse_keypress

# Bracketed paste mode escape sequences
BRACKETED_PASTE_ON = "\x1b[?2004h"
BRACKETED_PASTE_OFF = "\x1b[?2004l"


class InputManager:
    """Manages raw mode terminal input and dispatches keypresses to listeners.

    Matches Ink's input handling with:
    - Raw mode management with reference counting
    - Bracketed paste mode support
    - Input parser for CSI/SS3/paste sequence handling
    - Escape sequence timeout for standalone ESC key

    Parameters
    ----------
    loop : asyncio.AbstractEventLoop
        The event loop used for scheduling reads and timers.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._listeners: list[Callable[[str, Key], None]] = []
        self._paste_listeners: list[Callable[[str], None]] = []
        # Internal handler runs BEFORE user listeners.
        # If it returns True, the event is suppressed (not dispatched to user listeners).
        # Used by App to intercept Ctrl+C before useInput handlers see it.
        self._internal_handler: Callable[[str, Key], bool] | None = None
        self._old_settings: list | None = None
        self._reading = False
        self._raw_mode_count = 0
        self._bracketed_paste_count = 0
        self._parser = create_input_parser()
        self._escape_timer: asyncio.TimerHandle | None = None
        self._escape_timeout = 0.1  # 100ms timeout for standalone ESC

    @property
    def is_raw_mode_supported(self) -> bool:
        try:
            return os.isatty(sys.stdin.fileno())
        except (AttributeError, ValueError):
            return False

    def start(self) -> None:
        """Enable raw mode and start reading stdin."""
        if self._reading:
            return
        if not self.is_raw_mode_supported:
            return
        self.enable_raw_mode()
        self._loop.add_reader(sys.stdin.fileno(), self._on_data)
        self._reading = True

    def stop(self) -> None:
        """Restore terminal and stop reading."""
        if not self._reading:
            return
        try:
            self._loop.remove_reader(sys.stdin.fileno())
        except Exception:
            pass
        if self._escape_timer:
            self._escape_timer.cancel()
            self._escape_timer = None
        self.disable_bracketed_paste()
        self.disable_raw_mode()
        self._reading = False
        self._parser.reset()

    def enable_raw_mode(self) -> None:
        if not self.is_raw_mode_supported:
            return
        self._raw_mode_count += 1
        if self._raw_mode_count > 1:
            return
        try:
            import termios
            import tty

            fd = sys.stdin.fileno()
            self._old_settings = termios.tcgetattr(fd)
            # Use setcbreak instead of setraw.
            # In Node.js, stdin.setRawMode(true) only affects input.
            # In Python, tty.setraw() also disables OPOST (output processing),
            # which breaks \n → \r\n translation and causes ANSI escape
            # sequences to malfunction. setcbreak() disables echo and
            # canonical mode (what we need for keypresses) but preserves
            # output processing.
            tty.setcbreak(fd)
        except Exception:
            pass

    def disable_raw_mode(self) -> None:
        self._raw_mode_count = max(0, self._raw_mode_count - 1)
        if self._raw_mode_count > 0:
            return
        if self._old_settings is not None:
            try:
                import termios

                termios.tcsetattr(
                    sys.stdin.fileno(), termios.TCSADRAIN, self._old_settings
                )
            except Exception:
                pass
            self._old_settings = None

    def enable_bracketed_paste(self) -> None:
        """Enable bracketed paste mode."""
        self._bracketed_paste_count += 1
        if self._bracketed_paste_count == 1:
            try:
                sys.stdout.write(BRACKETED_PASTE_ON)
                sys.stdout.flush()
            except Exception:
                pass

    def disable_bracketed_paste(self) -> None:
        """Disable bracketed paste mode."""
        self._bracketed_paste_count = max(0, self._bracketed_paste_count - 1)
        if self._bracketed_paste_count == 0:
            try:
                sys.stdout.write(BRACKETED_PASTE_OFF)
                sys.stdout.flush()
            except Exception:
                pass

    def _on_data(self) -> None:
        try:
            data = sys.stdin.buffer.read1(1024)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            try:
                data = os.read(sys.stdin.fileno(), 1024)
            except OSError:
                return

        if not data:
            return

        try:
            chunk = data.decode("utf-8")
        except UnicodeDecodeError:
            return

        # Cancel pending escape timer
        if self._escape_timer:
            self._escape_timer.cancel()
            self._escape_timer = None

        events = self._parser.push(chunk)

        for event in events:
            if isinstance(event, PasteEvent):
                for listener in list(self._paste_listeners):
                    try:
                        listener(event.paste)
                    except Exception:
                        pass
            else:
                raw = event.encode("utf-8") if isinstance(event, str) else event
                input_str, key = parse_keypress(raw)
                # Internal handler can suppress (e.g. Ctrl+C with exitOnCtrlC)
                if self._internal_handler and self._internal_handler(input_str, key):
                    continue
                for listener in list(self._listeners):
                    try:
                        listener(input_str, key)
                    except Exception:
                        pass

        # Set up escape timeout for pending escape sequences
        if self._parser.has_pending_escape():
            self._escape_timer = self._loop.call_later(
                self._escape_timeout, self._flush_escape
            )

    def _flush_escape(self) -> None:
        """Flush pending escape sequence after timeout (standalone ESC key)."""
        self._escape_timer = None
        pending = self._parser.flush_pending_escape()
        if pending:
            input_str, key = parse_keypress(pending.encode("utf-8"))
            for listener in list(self._listeners):
                try:
                    listener(input_str, key)
                except Exception:
                    pass

    def add_listener(self, fn: Callable[[str, Key], None]) -> None:
        """Register a keypress listener.

        Parameters
        ----------
        fn : Callable[[str, Key], None]
            Callback receiving ``(input_string, key)`` for each keypress.
        """
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[str, Key], None]) -> None:
        """Remove a previously registered keypress listener.

        Parameters
        ----------
        fn : Callable[[str, Key], None]
            The listener to remove.
        """
        try:
            self._listeners.remove(fn)
        except ValueError:
            pass

    def add_paste_listener(self, fn: Callable[[str], None]) -> None:
        """Register a paste event listener.

        Parameters
        ----------
        fn : Callable[[str], None]
            Callback receiving the pasted text.
        """
        self._paste_listeners.append(fn)

    def remove_paste_listener(self, fn: Callable[[str], None]) -> None:
        """Remove a previously registered paste listener.

        Parameters
        ----------
        fn : Callable[[str], None]
            The listener to remove.
        """
        try:
            self._paste_listeners.remove(fn)
        except ValueError:
            pass
