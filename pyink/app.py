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
    CLEAR_TERMINAL,
    LogUpdate,
    get_terminal_size,
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
    ) -> None:
        self._root_vnode = root_vnode
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.stdin = stdin or sys.stdin
        self._exit_on_ctrl_c = exit_on_ctrl_c

        self._is_screen_reader_enabled = (
            is_screen_reader_enabled
            if is_screen_reader_enabled is not None
            else os.environ.get("INK_SCREEN_READER", "").lower() == "true"
        )

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
        self._log = LogUpdate(self.stdout)

        self.input_manager: InputManager | None = None
        self.focus_manager = FocusManager()

        self._reconciler = Reconciler(on_commit=self._on_commit)
        self._reconciler.set_app(self)

        # Timer support for animations
        self._timers: dict[int, asyncio.TimerHandle] = {}
        self._timer_counter = 0

        # Cursor
        self._cursor_position: CursorPosition | None = None

        # Exit callbacks
        self._exit_callbacks: list[Callable[[], None]] = []

        # Render throttle (port of ink.tsx lines 338-344)
        self._render_throttle_ms = max(1, 1000 // max_fps) if max_fps > 0 else 0
        self._render_pending = False
        self._render_handle: asyncio.TimerHandle | None = None

    # ── Port of ink.tsx onRender (lines 520-630) ──

    def _on_commit(self) -> None:
        """Called by reconciler after each commit. Schedules throttled render."""
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

        width = get_terminal_size()[0]
        result = renderer(dom, width=width)

        self._render_interactive_frame(
            result.output, result.output_height, result.static_output,
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
        has_static = static_output and static_output.strip()
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

        if has_static:
            # Write static output once — it scrolls off naturally.
            self._log.clear()
            self._stdout_write(static_output + "\n")
            self._full_static_output += static_output + "\n"
            self._log(output_to_render)
        elif should_clear:
            self._stdout_write(
                CLEAR_TERMINAL + self._full_static_output + output,
            )
            self._log.sync(output_to_render)
        elif output != self._last_output:
            self._log(output_to_render)

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

        if self.input_manager:
            self.input_manager.stop()
        self._reconciler.unmount()
        self.focus_manager.reset()
        self._cleanup_resize_handler()

        # Port of ink.tsx: log.done() restores cursor
        self._log.done()

        try:
            self.stdout.write("\n")
            self.stdout.flush()
        except Exception:
            pass

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

    def _stdout_write(self, data: str) -> None:
        try:
            self.stdout.write(data)
            self.stdout.flush()
        except (BrokenPipeError, OSError):
            pass

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
    )

    try:
        loop = asyncio.get_running_loop()
        instance = Instance(app)
        loop.create_task(app.run())
        return instance
    except RuntimeError:
        try:
            asyncio.run(app.run())
        except KeyboardInterrupt:
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
    from pyink.renderer.render_node import render_to_string as _render

    def on_commit():
        pass

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
        output = _render(dom, width=columns)
        reconciler.unmount()
        return output

    reconciler.unmount()
    return ""
