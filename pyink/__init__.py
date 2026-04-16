"""PyInk - Build terminal UIs with Python using React-like components and flexbox layout.

A 1:1 Python port of Ink (https://github.com/vadimdemedes/ink).

Example:
    from pyink import component, render, Box, Text
    from pyink.hooks import use_state, use_input, use_app

    @component
    def counter():
        count, set_count = use_state(0)
        app = use_app()

        def handle_input(input_str, key):
            if key.return_key:
                set_count(lambda c: c + 1)
            if input_str == "q":
                app.exit()

        use_input(handle_input)

        return Box(
            Text(f"Count: {count}", color="green", bold=True),
            Text("Press Enter to increment, q to quit", dim_color=True),
            flex_direction="column",
        )

    render(counter())
"""

# Render functions
from pyink.app import Instance, render, render_async, render_to_string_sync

# Core component decorator
from pyink.component import component

# Cursor types
from pyink.cursor_helpers import CursorPosition

# DOM types
from pyink.dom import DOMElement

# Hooks (re-exported for convenience)
from pyink.hooks import (
    AnimationResult,
    BoxMetrics,
    # Types
    WindowSize,
    use_animation,
    use_app,
    use_box_metrics,
    use_callback,
    use_cursor,
    use_effect,
    use_focus,
    use_focus_manager,
    use_input,
    use_is_screen_reader_enabled,
    use_memo,
    use_mouse,
    use_paste,
    use_ref,
    use_state,
    use_stderr,
    use_stdin,
    use_stdout,
    use_window_size,
)

# Input types
from pyink.input.keys import Key

# Kitty keyboard protocol
from pyink.input.kitty_keyboard import KittyFlagName, kitty_flags, kitty_modifiers

# Utilities
from pyink.measure_element import measure_element

# Components (matching Ink's exports)
from pyink.vnode import Box, Newline, Spacer, Static, Text, Transform, VNode

__all__ = [
    # Render functions
    "render",
    "render_async",
    "render_to_string_sync",
    "Instance",
    # Component decorator
    "component",
    # Components
    "Box",
    "Text",
    "Static",
    "Transform",
    "Spacer",
    "Newline",
    "VNode",
    # Hooks
    "use_state",
    "use_effect",
    "use_ref",
    "use_memo",
    "use_callback",
    "use_input",
    "use_mouse",
    "use_paste",
    "use_app",
    "use_focus",
    "use_focus_manager",
    "use_stdin",
    "use_stdout",
    "use_stderr",
    "use_window_size",
    "use_box_metrics",
    "use_cursor",
    "use_animation",
    "use_is_screen_reader_enabled",
    # Types
    "Key",
    "WindowSize",
    "BoxMetrics",
    "CursorPosition",
    "AnimationResult",
    "DOMElement",
    # Utilities
    "measure_element",
    # Kitty keyboard
    "kitty_flags",
    "kitty_modifiers",
    "KittyFlagName",
]
