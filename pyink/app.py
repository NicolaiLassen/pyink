"""1:1 port of Ink's ink.tsx render cycle and render.ts entry point.

Source: /tmp/ink-reference/src/ink.tsx
Source: /tmp/ink-reference/src/render.ts

Ports: constructor, onRender, renderInteractiveFrame, resized,
shouldClearTerminalForFrame, calculateLayout, unmount.
"""
from __future__ import annotations

import asyncio
import atexit
import os
import signal
import sys
from collections.abc import Callable
from typing import Any

from pyink.dom import DOMElement
from pyink.focus import FocusManager
from pyink.hooks.use_cursor import CursorPosition
from pyink.input.keys import Key
from pyink.input.reader import InputManager
from pyink.reconciler import Reconciler
from pyink.renderer.render_node import renderer
from pyink.terminal import (
    BSU,
    ESU,
    get_terminal_size,
    should_synchronize,
)
from pyink.vnode import VNode

# ── Port of ink.tsx shouldClearTerminalForFrame (lines 118-152) ──

def _should_clear_terminal_for_frame(
    is_tty: bool,
    viewport_rows: int,
    previous_output_height: int,
    next_output_height: int,
    is_unmounting: bool,
) -> bool:
    if not is_tty:
        return False

    had_previous_frame = previous_output_height > 0
    was_fullscreen = previous_output_height >= viewport_rows
    was_overflowing = previous_output_height > viewport_rows
    is_overflowing = next_output_height > viewport_rows
    is_leaving_fullscreen = was_fullscreen and next_output_height < viewport_rows
    should_clear_on_unmount = is_unmounting and was_fullscreen

    return (
        was_overflowing
        or (is_overflowing and had_previous_frame)
        or is_leaving_fullscreen
        or should_clear_on_unmount
    )


class App:
    """1:1 port of Ink's Ink class from ink.tsx.

    Manages the event loop, reconciler, input handling, terminal rendering.

    Parameters
    ----------
    root_vnode : VNode
        The root virtual node to render.
    stdout : Any, optional
        Writable stream for output (default ``sys.stdout``).
    stderr : Any, optional
        Writable stream for errors (default ``sys.stderr``).
    stdin : Any, optional
        Readable stream for input (default ``sys.stdin``).
    exit_on_ctrl_c : bool, optional
        Whether Ctrl+C should trigger exit (default ``True``).
    use_alt_screen : bool, optional
        Whether to use the alternate terminal screen (default ``False``).
    max_fps : int, optional
        Maximum render frames per second (default ``30``).
    is_screen_reader_enabled : bool or None, optional
        Force screen-reader mode on/off, or auto-detect from
        ``INK_SCREEN_READER`` environment variable when ``None``.
    """

    def __init__(
        self,
        root_vnode: VNode,
        *,
        stdout: Any = None,
        stderr: Any = None,
        stdin: Any = None,
        exit_on_ctrl_c: bool = True,
        use_alt_screen: bool = False,
        max_fps: int = 30,
        is_screen_reader_enabled: bool | None = None,
        debug: bool = False,
        interactive: bool | None = None,
        on_render: Callable | None = None,
        incremental_rendering: bool = False,
        patch_console: bool = False,
        kitty_keyboard: dict | None = None,
    ) -> None:
        self._root_vnode = root_vnode
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.stdin = stdin or sys.stdin
        self._exit_on_ctrl_c = exit_on_ctrl_c
        self._debug = debug
        self._on_render_callback = on_render
        self._patch_console = patch_console

        self._is_screen_reader_enabled = (
            is_screen_reader_enabled
            if is_screen_reader_enabled is not None
            else os.environ.get("INK_SCREEN_READER", "").lower() == "true"
        )

        # Port of ink.tsx lines 330-334: interactive mode detection
        if interactive is not None:
            self._interactive = interactive
        else:
            ci = os.environ.get("CI", "").lower() in ("true", "1", "yes")
            is_tty = hasattr(self.stdout, "isatty") and self.stdout.isatty()
            self._interactive = not ci and is_tty

        # Port of ink.tsx lines 335, 957-985: alternate screen
        self._alternate_screen = (
            bool(use_alt_screen)
            and self._interactive
            and hasattr(self.stdout, "isatty")
            and self.stdout.isatty()
        )
        if self._alternate_screen:
            self._stdout_write("\x1b[?1049h")  # enter alternate screen
            self._stdout_write("\x1b[?25l")  # hide cursor

        # Port of ink.tsx constructor state (lines 390-401)
        self._is_unmounted = False
        self._is_unmounting = False
        self._last_output = ""
        self._last_output_to_render = ""
        self._last_output_height = 0
        self._last_terminal_width = get_terminal_size()[0]
        self._full_static_output = ""

        self._loop: asyncio.AbstractEventLoop | None = None
        self._exit_event: asyncio.Event | None = None
        self._exit_code: int = 0

        # Port of ink.tsx line 363: this.log = logUpdate.create(options.stdout)
        from pyink.terminal import create_log_update

        self._log = create_log_update(self.stdout, incremental=incremental_rendering)

        self.input_manager: InputManager | None = None
        self.focus_manager = FocusManager()

        self._reconciler = Reconciler(on_commit=self._on_commit)
        self._reconciler.set_app(self)

        # Timer support for animations
        self._timers: dict[int, asyncio.TimerHandle] = {}
        self._timer_counter = 0

        # Shared animation scheduler (port of App.tsx lines 80-191)
        self._animation_subscribers: dict[
            int, dict
        ] = {}  # id -> {callback, interval, start_time, next_due_time}
        self._animation_timer: asyncio.TimerHandle | None = None
        self._animation_counter = 0

        # Cursor
        self._cursor_position: CursorPosition | None = None

        # Exit callbacks
        self._exit_callbacks: list[Callable[[], None]] = []

        # Kitty keyboard protocol (port of ink.tsx lines 315-316, 1097-1185)
        self._kitty_keyboard_opts = kitty_keyboard
        self._kitty_protocol_enabled = False

        # Render throttle (port of ink.tsx lines 338-344)
        self._render_throttle_ms = max(1, 1000 // max_fps) if max_fps > 0 else 0
        self._render_pending = False
        self._render_handle: asyncio.TimerHandle | None = None

    # ── Port of ink.tsx onRender (lines 520-630) ──

    def _on_commit(self) -> None:
        """Called by reconciler after each commit.

        Port of Ink's resetAfterCommit (reconciler.ts lines 160–182):
        - Emit layout listeners
        - If static dirty → render immediately (bypass throttle)
        - Otherwise → schedule throttled render
        """
        # Emit layout listeners on the root DOM node
        dom = self._get_root_dom()
        if dom is not None:
            from pyink.dom import emit_layout_listeners

            emit_layout_listeners(dom)

            # Static output needs immediate render (Ink lines 170–177)
            if dom.is_static_dirty:
                dom.is_static_dirty = False
                self._on_render()
                return

        if self._loop and not self._render_pending:
            self._render_pending = True
            if self._render_handle:
                self._render_handle.cancel()
            # Throttle: schedule render after throttle interval
            if self._render_throttle_ms > 0:
                self._render_handle = self._loop.call_later(
                    self._render_throttle_ms / 1000.0, self._on_render
                )
            else:
                self._render_handle = self._loop.call_soon(self._on_render)

    def _get_root_dom(self) -> DOMElement | None:
        """Get the root DOM element from the reconciler."""
        if self._reconciler.root_fiber and isinstance(
            self._reconciler.root_fiber.dom_node, DOMElement
        ):
            return self._reconciler.root_fiber.dom_node
        return None

    def _on_render(self) -> None:
        """Port of ink.tsx onRender() lines 520-630."""
        self._render_pending = False
        self._render_handle = None

        if self._is_unmounted:
            return

        if self._reconciler.root_fiber is None:
            return

        dom = self._reconciler.root_fiber.dom_node
        if not isinstance(dom, DOMElement):
            return

        import time

        start_time = time.monotonic()

        width = get_terminal_size()[0]
        result = renderer(
            dom,
            width=width,
            is_screen_reader_enabled=self._is_screen_reader_enabled,
        )

        # on_render callback with metrics (ink.tsx line 538)
        if self._on_render_callback:
            render_time = (time.monotonic() - start_time) * 1000
            try:
                self._on_render_callback({"render_time": render_time})
            except Exception:
                pass

        # Static output check — matching Ink's onRender (ink.tsx line 541)
        is_static_write = bool(
            result.static_output and result.static_output != "\n"
        )

        # Debug mode: write each update as separate output (ink.tsx lines 543-553)
        if self._debug:
            if is_static_write:
                self._full_static_output += result.static_output
            self._last_output = result.output
            self._last_output_to_render = result.output
            self._last_output_height = result.output_height
            self._stdout_write(self._full_static_output + result.output)
            return

        # Non-interactive mode (ink.tsx lines 555-564)
        if not self._interactive:
            if is_static_write:
                self._stdout_write(result.static_output)
            self._last_output = result.output
            self._last_output_to_render = result.output + "\n"
            self._last_output_height = result.output_height
            return

        # Interactive mode: pass static output to frame renderer
        static_output = result.static_output if is_static_write else ""

        if is_static_write:
            self._full_static_output += static_output

        self._render_interactive_frame(
            result.output, result.output_height, static_output,
        )

    # ── Port of ink.tsx renderInteractiveFrame (lines 1030-1095) ──

    def _render_interactive_frame(
        self, output: str, output_height: int, static_output: str = ""
    ) -> None:
        """Render a frame, writing static output once and dynamic via log-update.

        Static output is written directly to stdout and accumulated in
        ``_full_static_output``. It becomes terminal scrollback and is
        never redrawn. Dynamic output is managed by log-update which
        erases and rewrites only the dynamic portion.

        Parameters
        ----------
        output : str
            The dynamic (re-drawable) portion of the frame.
        output_height : int
            Number of lines in *output*.
        static_output : str, optional
            One-shot static content that scrolls off (default ``""``).
        """
        # Port of ink.tsx renderInteractiveFrame (lines 1030-1095)
        has_static_output = static_output != ""
        is_tty = hasattr(self.stdout, "isatty") and self.stdout.isatty()
        viewport_rows = get_terminal_size()[1] if is_tty else 24
        is_fullscreen = is_tty and output_height >= viewport_rows
        output_to_render = output if is_fullscreen else output + "\n"

        should_clear = _should_clear_terminal_for_frame(
            is_tty,
            viewport_rows,
            self._last_output_height,
            output_height,
            self._is_unmounting,
        )

        sync = self._should_sync()

        if has_static_output:
            # Static output MUST be written first — before any clear.
            # Otherwise should_clear would drop it (the bug that caused
            # response text and stats to vanish after long streaming).
            if sync:
                self._stdout_write(BSU)
            self._log.clear()
            self._stdout_write(static_output)
            self._log(output_to_render)
            if sync:
                self._stdout_write(ESU)
        elif should_clear:
            # Viewport overflow: erase_lines() can't reach scrollback,
            # so use \x1b[2J\x1b[H (clear visible screen + cursor home)
            # and reset log state. This prevents cascading duplication
            # when dynamic content exceeds the terminal viewport.
            if sync:
                self._stdout_write(BSU)
            self._stdout_write("\x1b[2J\x1b[3J\x1b[H")  # clear screen + scrollback + cursor home
            self._stdout_write(self._full_static_output + output_to_render)
            self._log.reset()
            self._log.sync(output_to_render)
            self._last_output = output
            self._last_output_to_render = output_to_render
            self._last_output_height = output_height
            if sync:
                self._stdout_write(ESU)
            return
        elif output != self._last_output or self._log.is_cursor_dirty():
            # Port of ink.tsx throttledLog (lines 367-388):
            # Wrap normal log writes with BSU/ESU to prevent flicker
            should_write = self._log.will_render(output_to_render)
            if sync and should_write:
                self._stdout_write(BSU)
            self._log(output_to_render)
            if sync and should_write:
                self._stdout_write(ESU)

        self._last_output = output
        self._last_output_to_render = output_to_render
        self._last_output_height = output_height

    # ── Port of ink.tsx resized (lines 458-472) ──

    def _resized(self) -> None:
        """Port of ink.tsx resized() lines 458-472."""
        current_width = get_terminal_size()[0]

        if current_width < self._last_terminal_width:
            # Line 463-465: clear on width decrease
            self._log.clear()
            self._last_output = ""
            self._last_output_to_render = ""

        self._last_terminal_width = current_width

        # Notify registered resize handlers (used by useWindowSize, useBoxMetrics)
        for handler in getattr(self, "_resize_handlers", []):
            try:
                handler()
            except Exception:
                pass

        # Line 468-469: recalculate layout and re-render
        self._on_render()

    # ── Input handling ──

    def _handle_internal_input(self, input_str: str, key: Key) -> bool:
        """Internal handler -- runs before user useInput listeners.

        Matches Ink's Ctrl+C filtering: when exitOnCtrlC is true, Ctrl+C
        never reaches useInput handlers.

        Parameters
        ----------
        input_str : str
            The printable character(s) from the keypress.
        key : Key
            Parsed key with modifier flags.

        Returns
        -------
        bool
            ``True`` to suppress the event (prevent user handlers from
            seeing it), ``False`` to let it propagate.
        """
        # Ctrl+C: exit and suppress from user handlers
        if key.ctrl and input_str == "c" and self._exit_on_ctrl_c:
            self.request_exit(0)
            return True  # suppress

        # Tab focus navigation (NOT suppressed — user handlers still see it)
        if key.tab and not key.shift:
            self.focus_manager.focus_next()
        elif key.tab and key.shift:
            self.focus_manager.focus_previous()

        return False  # don't suppress

    # ── App lifecycle ──

    def request_exit(self, code: int = 0) -> None:
        """Request application exit with the given exit code.

        Parameters
        ----------
        code : int, optional
            Process exit code (default ``0``).
        """
        self._exit_code = code
        self._is_unmounting = True
        if self._exit_event:
            self._exit_event.set()

    def set_cursor_position(self, position: CursorPosition | None) -> None:
        """Set the logical cursor position for the current frame.

        Parameters
        ----------
        position : CursorPosition or None
            The cursor position, or ``None`` to hide the cursor.
        """
        self._cursor_position = position

    def add_timer(
        self, interval: float, callback: Callable, *, repeating: bool = False
    ) -> int:
        """Schedule a timer callback.

        Parameters
        ----------
        interval : float
            Delay in seconds before the callback fires.
        callback : Callable
            The function to call.
        repeating : bool, optional
            If ``True``, reschedule after each invocation (default ``False``).

        Returns
        -------
        int
            A timer ID that can be passed to ``remove_timer``.
        """
        timer_id = self._timer_counter
        self._timer_counter += 1
        if self._loop is None:
            return timer_id

        def _tick() -> None:
            try:
                callback()
            except Exception:
                pass
            if repeating and timer_id in self._timers and not self._is_unmounted:
                self._timers[timer_id] = self._loop.call_later(interval, _tick)  # type: ignore

        self._timers[timer_id] = self._loop.call_later(interval, _tick)
        return timer_id

    def remove_timer(self, timer_id: int) -> None:
        """Cancel a previously scheduled timer.

        Parameters
        ----------
        timer_id : int
            The ID returned by ``add_timer``.
        """
        handle = self._timers.pop(timer_id, None)
        if handle:
            handle.cancel()

    # ── Shared animation scheduler (port of App.tsx lines 120-191) ──

    def subscribe_animation(
        self, callback: Callable[[float], None], interval: int
    ) -> tuple[float, Callable[[], None]]:
        """Register an animation subscriber with the shared scheduler.

        Port of Ink's App.tsx animationSubscribe (lines 160–191).

        Parameters
        ----------
        callback : Callable[[float], None]
            Called with current_time (ms) on each tick.
        interval : int
            Tick interval in milliseconds.

        Returns
        -------
        tuple[float, Callable[[], None]]
            ``(start_time, unsubscribe)`` — start_time in ms, unsubscribe fn.
        """
        import time

        sub_id = self._animation_counter
        self._animation_counter += 1
        start_time = time.monotonic() * 1000

        self._animation_subscribers[sub_id] = {
            "callback": callback,
            "interval": interval,
            "start_time": start_time,
            "next_due_time": start_time + interval,
        }
        self._schedule_animation_tick()

        def unsubscribe() -> None:
            self._animation_subscribers.pop(sub_id, None)
            if not self._animation_subscribers:
                if self._animation_timer:
                    self._animation_timer.cancel()
                    self._animation_timer = None
            else:
                self._schedule_animation_tick()

        return (start_time, unsubscribe)

    def _schedule_animation_tick(self) -> None:
        """Schedule the next shared animation tick at the earliest deadline."""
        if self._animation_timer:
            self._animation_timer.cancel()
            self._animation_timer = None

        if not self._animation_subscribers or not self._loop:
            return

        import time

        now = time.monotonic() * 1000
        next_due = min(
            sub["next_due_time"] for sub in self._animation_subscribers.values()
        )
        delay = max(0, (next_due - now) / 1000.0)

        self._animation_timer = self._loop.call_later(
            delay, self._animation_tick
        )

    def _animation_tick(self) -> None:
        """Fire all due animation subscribers and reschedule."""
        import time

        self._animation_timer = None
        current_time = time.monotonic() * 1000

        for sub in list(self._animation_subscribers.values()):
            if current_time < sub["next_due_time"]:
                continue

            try:
                sub["callback"](current_time)
            except Exception:
                pass

            # Advance next_due_time based on elapsed frames
            elapsed = current_time - sub["start_time"]
            elapsed_frames = int(elapsed / sub["interval"]) + 1
            sub["next_due_time"] = sub["start_time"] + elapsed_frames * sub["interval"]

        if self._animation_subscribers:
            self._schedule_animation_tick()

    # ── Port of ink.tsx run cycle ──

    async def run(self) -> int:
        """Run the application event loop.

        Returns
        -------
        int
            The exit code set via ``request_exit``.
        """
        self._loop = asyncio.get_running_loop()
        self._exit_event = asyncio.Event()
        self._reconciler.set_loop(self._loop)

        # Setup input — internal handler runs before user useInput listeners
        self.input_manager = InputManager(self._loop)
        self.input_manager._internal_handler = self._handle_internal_input
        self.input_manager.start()

        # Port of ink.tsx line 439: stdout.on('resize', this.resized)
        self._setup_resize_handler()

        # Port of ink.tsx patchConsole (lines 434, 937-955)
        if self._patch_console and not self._debug:
            self._do_patch_console()

        # Port of ink.tsx initKittyKeyboard (line 446)
        self._init_kitty_keyboard()

        def cleanup():
            self._cleanup()

        atexit.register(cleanup)

        try:
            # Mount the root component
            self._reconciler.mount(self._root_vnode)
            await self._exit_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            self._cleanup()
            atexit.unregister(cleanup)

        for cb in self._exit_callbacks:
            try:
                cb()
            except Exception:
                pass

        return self._exit_code

    def _cleanup(self) -> None:
        """Port of ink.tsx unmount cleanup."""
        self._is_unmounted = True

        # Cancel timers
        for handle in self._timers.values():
            handle.cancel()
        self._timers.clear()

        # Cancel shared animation scheduler
        if self._animation_timer:
            self._animation_timer.cancel()
            self._animation_timer = None
        self._animation_subscribers.clear()

        # Disable kitty keyboard protocol before cleanup
        self._disable_kitty_protocol()

        # Restore console before React cleanup (matching Ink ink.tsx lines 767-773)
        self._do_restore_console()

        if self.input_manager:
            self.input_manager.stop()
        self._reconciler.unmount()
        self.focus_manager.reset()
        self._cleanup_resize_handler()

        # Port of ink.tsx lines 796-803: restore alternate screen on exit
        if self._alternate_screen:
            self._stdout_write("\x1b[?1049l")  # exit alternate screen
            self._stdout_write("\x1b[?25h")  # show cursor
            self._alternate_screen = False
        elif not self._debug:
            # Port of ink.tsx: log.done() restores cursor
            self._log.done()

        try:
            if not self._alternate_screen:
                self.stdout.write("\n")
            self.stdout.flush()
        except Exception:
            pass

    # ── Kitty keyboard protocol (port of ink.tsx lines 1097-1185) ──

    def _init_kitty_keyboard(self) -> None:
        """Initialize Kitty keyboard protocol if configured."""
        if not self._kitty_keyboard_opts:
            return

        opts = self._kitty_keyboard_opts
        mode = opts.get("mode", "auto")

        if mode == "disabled":
            return

        from pyink.input.kitty_keyboard import resolve_flags

        flags = opts.get("flags", ["disambiguate_escape_codes"])
        flag_bits = resolve_flags(flags)

        is_stdin_tty = hasattr(self.stdin, "isatty") and self.stdin.isatty()
        is_stdout_tty = hasattr(self.stdout, "isatty") and self.stdout.isatty()

        if mode == "enabled":
            if is_stdin_tty and is_stdout_tty:
                self._enable_kitty_protocol(flag_bits)
            return

        # Auto mode: require interactive + TTY
        if not self._interactive or not is_stdin_tty or not is_stdout_tty:
            return

        # Query terminal for kitty support (200ms timeout)
        self._stdout_write("\x1b[?u")
        # In auto mode, the response will be detected by the input manager.
        # For simplicity, we enable it optimistically if the terminal env
        # suggests support (TERM_PROGRAM=kitty, etc.)
        term = os.environ.get("TERM_PROGRAM", "").lower()
        if "kitty" in term or "wezterm" in term or "ghostty" in term:
            self._enable_kitty_protocol(flag_bits)

    def _enable_kitty_protocol(self, flags: int) -> None:
        """Enable kitty keyboard protocol with given flags."""
        self._stdout_write(f"\x1b[>{flags}u")
        self._kitty_protocol_enabled = True

    def _disable_kitty_protocol(self) -> None:
        """Disable kitty keyboard protocol if enabled."""
        if self._kitty_protocol_enabled:
            self._stdout_write("\x1b[<u")
            self._kitty_protocol_enabled = False

    def _do_patch_console(self) -> None:
        """Patch sys.stdout/stderr writes to route through Ink output.

        Port of Ink's patchConsole (ink.tsx lines 937–955).
        Preserves the rendered frame when print() or direct writes happen.
        """
        import builtins

        self._original_print = builtins.print
        self._original_stdout_write = sys.stdout.write
        self._original_stderr_write = sys.stderr.write

        app = self

        def patched_print(*args: Any, **kwargs: Any) -> None:
            import io

            buf = io.StringIO()
            kwargs_copy = dict(kwargs)
            kwargs_copy["file"] = buf
            self._original_print(*args, **kwargs_copy)
            text = buf.getvalue()

            file = kwargs.get("file")
            if file is None or file is sys.stdout:
                app.write_to_stdout(text)
            elif file is sys.stderr:
                app.write_to_stderr(text)
            else:
                # Write to custom file directly
                self._original_print(*args, **kwargs)

        builtins.print = patched_print  # type: ignore[assignment]

    def _do_restore_console(self) -> None:
        """Restore original print and write functions."""
        import builtins

        if hasattr(self, "_original_print"):
            builtins.print = self._original_print  # type: ignore[assignment]

    def _setup_resize_handler(self) -> None:
        try:
            signal.signal(signal.SIGWINCH, self._handle_sigwinch)
        except (AttributeError, ValueError):
            pass

    def _cleanup_resize_handler(self) -> None:
        try:
            signal.signal(signal.SIGWINCH, signal.SIG_DFL)
        except (AttributeError, ValueError):
            pass

    def _handle_sigwinch(self, signum: int, frame: object) -> None:
        self._resized()

    def _should_sync(self) -> bool:
        """Check if synchronized output should be used."""
        return should_synchronize(self.stdout)

    def _stdout_write(self, data: str) -> None:
        try:
            self.stdout.write(data)
            self.stdout.flush()
        except (BrokenPipeError, OSError):
            pass

    def write_to_stdout(self, data: str) -> None:
        """Write data to stdout while preserving Ink output.

        Port of Ink's writeToStdout (ink.tsx lines 665–692).
        """
        if self._is_unmounted:
            return

        sync = self._should_sync()
        if sync:
            self._stdout_write(BSU)

        self._log.clear()
        self._stdout_write(data)
        # Restore last output
        if self._last_output_to_render:
            self._log.set_cursor_position(self._cursor_position)
            self._log(self._last_output_to_render)

        if sync:
            self._stdout_write(ESU)

    def write_to_stderr(self, data: str) -> None:
        """Write data to stderr while preserving Ink output.

        Port of Ink's writeToStderr (ink.tsx lines 694–722).
        """
        if self._is_unmounted:
            return

        sync = self._should_sync()
        if sync:
            self._stdout_write(BSU)

        self._log.clear()
        try:
            self.stderr.write(data)
            self.stderr.flush()
        except (BrokenPipeError, OSError):
            pass
        # Restore last output
        if self._last_output_to_render:
            self._log.set_cursor_position(self._cursor_position)
            self._log(self._last_output_to_render)

        if sync:
            self._stdout_write(ESU)

    async def wait_until_render_flush(self) -> None:
        """Wait until pending render output is flushed to stdout.

        Port of Ink's waitUntilRenderFlush (ink.tsx lines 880–926).
        Flushes any pending throttled render, then awaits stdout drain.
        """
        if self._is_unmounted or self._is_unmounting:
            return

        # Flush pending throttled render
        if self._render_pending and self._render_handle:
            self._render_handle.cancel()
            self._on_render()

        # Yield to let any scheduled callbacks fire
        if self._loop:
            await asyncio.sleep(0)

    def rerender(self, vnode: VNode) -> None:
        """Re-render the application with a new root VNode.

        Parameters
        ----------
        vnode : VNode
            The new root virtual node.
        """
        self._root_vnode = vnode
        if self._reconciler.root_fiber:
            self._reconciler.root_fiber.children_vnodes = [vnode]
            self._reconciler.schedule_update(self._reconciler.root_fiber)

    def unmount(self) -> None:
        self.request_exit(0)

    def wait_until_exit(self) -> asyncio.Future:
        """Return a future that resolves with the exit code when the app exits.

        Returns
        -------
        asyncio.Future
            Resolves to the integer exit code.
        """
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        def on_exit():
            if not future.done():
                future.set_result(self._exit_code)

        self._exit_callbacks.append(on_exit)
        return future

    # ── Needed by hooks that reference app.terminal ──

    @property
    def terminal(self) -> Any:
        """Shim for hooks that call app.terminal.on_resize()."""
        return self

    def on_resize(self, handler: Callable[[], None]) -> Callable[[], None]:
        """Register a resize callback.

        Parameters
        ----------
        handler : Callable[[], None]
            Callback invoked on terminal resize.

        Returns
        -------
        Callable[[], None]
            A removal function that unregisters the handler.
        """
        self._resize_handlers = getattr(self, "_resize_handlers", [])
        self._resize_handlers.append(handler)

        def remove():
            try:
                self._resize_handlers.remove(handler)
            except (ValueError, AttributeError):
                pass

        return remove


# ── Port of render.ts (public API) ──

class Instance:
    """Port of Ink's Instance type from render.ts.

    Parameters
    ----------
    app : App
        The underlying application instance to wrap.
    """

    def __init__(self, app: App) -> None:
        self._app = app

    def rerender(self, vnode: VNode) -> None:
        """Re-render with a new root VNode.

        Parameters
        ----------
        vnode : VNode
            The new root virtual node.
        """
        self._app.rerender(vnode)

    def unmount(self) -> None:
        """Unmount the application."""
        self._app.unmount()

    def clear(self) -> None:
        """Clear the current log-update output."""
        self._app._log.clear()

    def cleanup(self) -> None:
        """Run full cleanup (terminal restore, timers, etc.)."""
        self._app._cleanup()

    async def wait_until_exit(self) -> int:
        """Wait for the application to exit.

        Returns
        -------
        int
            The exit code.
        """
        return await self._app.wait_until_exit()


def render(
    element: VNode,
    *,
    stdout: Any = None,
    stderr: Any = None,
    stdin: Any = None,
    exit_on_ctrl_c: bool = True,
    use_alt_screen: bool = False,
    max_fps: int = 30,
    is_screen_reader_enabled: bool | None = None,
    debug: bool = False,
    interactive: bool | None = None,
    on_render: Callable | None = None,
    incremental_rendering: bool = False,
    patch_console: bool = False,
    kitty_keyboard: dict | None = None,
) -> Instance | None:
    """Port of Ink's render() from render.ts.

    Parameters
    ----------
    element : VNode
        The root virtual node to render.
    stdout : Any, optional
        Writable stream for output.
    stderr : Any, optional
        Writable stream for errors.
    stdin : Any, optional
        Readable stream for input.
    exit_on_ctrl_c : bool, optional
        Exit on Ctrl+C (default ``True``).
    use_alt_screen : bool, optional
        Use alternate terminal screen (default ``False``).
    max_fps : int, optional
        Maximum render frames per second (default ``30``).
    is_screen_reader_enabled : bool or None, optional
        Force screen-reader mode on/off or auto-detect.
    debug : bool, optional
        Write each update as separate output without erasing (default ``False``).
    interactive : bool or None, optional
        Override interactive mode detection. ``None`` auto-detects.
    on_render : Callable or None, optional
        Callback after each render with ``{"render_time": float}`` metrics.
    incremental_rendering : bool, optional
        Only update changed lines (default ``False``).
    patch_console : bool, optional
        Patch ``builtins.print`` to route through Ink output (default ``False``).

    Returns
    -------
    Instance or None
        An ``Instance`` handle when called inside a running event loop,
        or ``None`` when the app runs synchronously to completion.
    """
    app = App(
        element,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        exit_on_ctrl_c=exit_on_ctrl_c,
        use_alt_screen=use_alt_screen,
        max_fps=max_fps,
        is_screen_reader_enabled=is_screen_reader_enabled,
        debug=debug,
        interactive=interactive,
        on_render=on_render,
        incremental_rendering=incremental_rendering,
        patch_console=patch_console,
        kitty_keyboard=kitty_keyboard,
    )

    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    if loop is not None and loop.is_running():
        instance = Instance(app)
        loop.create_task(app.run())
        return instance

    try:
        asyncio.run(app.run())
    except (KeyboardInterrupt, SystemExit):
        app._cleanup()
    except Exception:
        app._cleanup()
    return None


async def render_async(
    element: VNode,
    *,
    stdout: Any = None,
    exit_on_ctrl_c: bool = True,
    max_fps: int = 30,
) -> Instance:
    """Async version of render.

    Parameters
    ----------
    element : VNode
        The root virtual node to render.
    stdout : Any, optional
        Writable stream for output.
    exit_on_ctrl_c : bool, optional
        Exit on Ctrl+C (default ``True``).
    max_fps : int, optional
        Maximum render frames per second (default ``30``).

    Returns
    -------
    Instance
        A handle for re-rendering, unmounting, or waiting for exit.
    """
    app = App(
        element,
        stdout=stdout,
        exit_on_ctrl_c=exit_on_ctrl_c,
        max_fps=max_fps,
    )
    instance = Instance(app)
    asyncio.get_running_loop().create_task(app.run())
    return instance


def render_to_string_sync(
    element: VNode,
    *,
    columns: int = 80,
) -> str:
    """Port of Ink's renderToString() from render-to-string.ts.

    Parameters
    ----------
    element : VNode
        The root virtual node to render.
    columns : int, optional
        Simulated terminal width (default ``80``).

    Returns
    -------
    str
        The rendered output as a plain string with ANSI codes.
    """
    from pyink.reconciler import Reconciler
    from pyink.renderer.render_node import renderer as _renderer

    # Capture static output during commit (like Ink's onImmediateRender)
    captured_static: list[str] = []

    def on_commit():
        rn = reconciler._root_node
        if rn and rn.is_static_dirty:
            rn.is_static_dirty = False
            result = _renderer(rn, width=columns)
            if result.static_output and result.static_output != "\n":
                captured_static.append(result.static_output)

    reconciler = Reconciler(on_commit=on_commit)

    class _NoopInputManager:
        """No-op input manager for render_to_string_sync (no terminal)."""
        def add_listener(self, fn): pass
        def remove_listener(self, fn): pass
        def add_paste_listener(self, fn): pass
        def remove_paste_listener(self, fn): pass
        def enable_bracketed_paste(self): pass
        def disable_bracketed_paste(self): pass
        is_raw_mode_supported = False
        def enable_raw_mode(self): pass
        def disable_raw_mode(self): pass

    class FakeApp:
        input_manager = _NoopInputManager()
        focus_manager = FocusManager()
        stdout = sys.stdout
        stderr = sys.stderr
        _is_screen_reader_enabled = False
        _exit_code = 0

        def request_exit(self, code=0):
            pass

        def set_cursor_position(self, pos):
            pass

        def add_timer(self, *a, **kw):
            return 0

        def remove_timer(self, *a):
            pass

        @property
        def terminal(self):
            return self

        def on_resize(self, handler):
            return lambda: None

    fake_app = FakeApp()
    reconciler.set_app(fake_app)

    root_fiber = reconciler.mount(element)
    dom = root_fiber.dom_node if root_fiber else None

    if isinstance(dom, DOMElement):
        # Static output was captured by on_commit during mount.
        # Now render the dynamic (non-static) output.
        result = _renderer(dom, width=columns)
        output = result.output

        # Combine captured static with dynamic output
        static_output = "".join(captured_static)
        if static_output.endswith("\n"):
            static_output = static_output[:-1]

        reconciler.unmount()

        if static_output and output:
            return static_output + "\n" + output
        return static_output or output

    reconciler.unmount()
    return ""
