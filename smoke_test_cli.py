#!/usr/bin/env python3
"""Smoke test that mirrors the exact orxhestra CLI pattern.

Run with: python smoke_test_cli.py

This reproduces the orx REPL structure:
- Static history (banner + help + separator)
- Spinner area
- Streaming area
- Flex-grow spacer
- Input area with cursor

Press Ctrl+D to exit, type text + Enter to add to history.
"""
from __future__ import annotations

import shutil

from pyink import Box, Static, Text, component, render
from pyink.fiber import Ref
from pyink.hooks import (
    use_animation,
    use_app,
    use_input,
    use_ref,
    use_state,
    use_window_size,
)

_ACCENT = "#6C8EBF"
_MUTED = "#6c6c6c"
_SEPARATOR = "\u2500" * (shutil.get_terminal_size().columns - 1)

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _history_item(item, _index=0):
    """Render a single history item — mirrors orx's _history_item."""
    t = item.get("type", "")
    ansi = item.get("ansi", "")
    if t == "user":
        return Box(
            Text("\u276f ", color=_ACCENT),
            Text(item["text"], bold=True),
            flex_direction="row",
            margin_top=1,
            margin_bottom=1,
        )
    if t == "response":
        return Box(
            Text("\u25cf ", color=_ACCENT),
            Text(ansi),
            flex_direction="row",
        )
    if t == "rich":
        return Text(ansi)
    if t == "plain":
        return Text(
            ansi, color=item.get("color"), dim=item.get("dim", False),
        )
    if t == "separator":
        return Text(_SEPARATOR, color=_MUTED, dim=True)
    return Text(str(item))


@component
def smoke_repl(initial_history):
    win = use_window_size()
    history, set_history = use_state(initial_history)
    buf, set_buf = use_state("")
    cursor, set_cursor = use_state(0)
    phase, set_phase = use_state("idle")
    spinner_text, set_spinner_text = use_state("")

    cmd_hist = use_ref([])
    hist_idx = use_ref(-1)

    app = use_app()

    # Spinner animation
    anim = use_animation(interval=200, is_active=(phase == "spinning"))
    fi = anim.frame % len(SPINNER_FRAMES)
    frame_char = SPINNER_FRAMES[fi]

    def on_key(ch, key):
        if key.ctrl and ch == "d":
            app.exit()
            return

        if key.ctrl and ch == "c":
            set_phase("idle")
            set_spinner_text("")
            return

        # Enter
        if key.return_key:
            msg = buf.strip()
            if not msg:
                return
            set_buf("")
            set_cursor(0)
            cmd_hist.current = [*cmd_hist.current, msg]
            hist_idx.current = -1

            # Echo as user message
            set_history(lambda h: [*h, {"type": "user", "text": msg}])

            # Fake a response after a moment
            if msg == "/spin":
                set_phase("spinning")
                set_spinner_text("Thinking...")
            elif msg == "/stop":
                set_phase("idle")
                set_spinner_text("")
            else:
                set_history(lambda h: [
                    *h,
                    {"type": "response", "ansi": f"Echo: {msg}"},
                    {"type": "separator"},
                ])
            return

        # History navigation
        if key.up_arrow:
            h = cmd_hist.current
            if h:
                i = hist_idx.current
                i = len(h) - 1 if i == -1 else max(0, i - 1)
                hist_idx.current = i
                set_buf(h[i])
                set_cursor(len(h[i]))
            return
        if key.down_arrow:
            i = hist_idx.current
            h = cmd_hist.current
            if i >= 0:
                if i < len(h) - 1:
                    hist_idx.current = i + 1
                    set_buf(h[i + 1])
                    set_cursor(len(h[i + 1]))
                else:
                    hist_idx.current = -1
                    set_buf("")
                    set_cursor(0)
            return

        # Cursor movement
        if key.left_arrow:
            set_cursor(lambda c: max(0, c - 1))
            return
        if key.right_arrow:
            set_cursor(lambda c: min(len(buf), c + 1))
            return

        # Backspace
        if key.backspace or key.delete:
            if cursor > 0:
                pos = cursor
                set_buf(lambda t: t[:pos - 1] + t[pos:])
                set_cursor(lambda c: max(0, c - 1))
            return

        # Regular character
        if ch and not key.ctrl and not key.meta and not key.escape:
            text = ch
            set_cursor(lambda c: c + len(text))
            set_buf(lambda t: t + text if cursor >= len(t) else t[:cursor] + text + t[cursor:])

    use_input(on_key)

    # ── Build component tree (mirrors orx_repl exactly) ──
    children = [Static(items=history, render_item=_history_item)]

    # Spinner
    if phase == "spinning" and spinner_text:
        children.append(
            Text(f"{frame_char} {spinner_text}", color=_ACCENT),
        )

    # Flex-grow spacer pushes input to bottom
    children.append(Box(flex_grow=1))

    # Input area
    before = buf[:cursor]
    char_at = buf[cursor] if cursor < len(buf) else " "
    after = buf[cursor + 1:] if cursor < len(buf) else ""

    input_children = [
        Text(_SEPARATOR, color=_MUTED, dim=True),
        Box(
            Text("  \u276f ", color=_ACCENT, bold=True),
            Text(before, bold=True),
            Text(char_at, bold=True, inverse=True),
            Text(after, bold=True),
            flex_direction="row",
        ),
        Text(_SEPARATOR, color=_MUTED, dim=True),
    ]
    children.append(Box(*input_children, flex_direction="column"))

    return Box(*children, flex_direction="column", min_height=win.rows)


def main():
    initial_history = [
        {"type": "rich", "ansi": "\x1b[1;34msmoke-test\x1b[0m v0.1"},
        {"type": "plain",
         "ansi": "  type text + Enter to echo, /spin to test spinner, Ctrl+D to exit",
         "color": _MUTED, "dim": True},
        {"type": "separator"},
    ]

    vnode = smoke_repl(initial_history=initial_history)
    render(vnode, max_fps=15)


if __name__ == "__main__":
    main()
