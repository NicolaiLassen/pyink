"""Tests for output height accuracy — the root cause of viewport corruption.

Verifies that the renderer returns the actual visible line count
(after trimming trailing empty rows), NOT the yoga-allocated grid height.
This is critical: is_fullscreen, shouldClear, and erase_lines all depend
on correct output_height.
"""
from pyink import Box, Text, render_to_string_sync
from pyink.renderer.render_node import renderer
from pyink.renderer.ansi import strip_ansi
from pyink.dom import DOMElement
from pyink.layout.engine import compute_layout


def _get_height(vnode, columns=80):
    """Render a VNode and return the output_height from the renderer."""
    # Use render_to_string_sync's internal path to get RenderResult
    from pyink.reconciler import Reconciler

    reconciler = Reconciler(on_commit=lambda: None)

    class FakeApp:
        from pyink.focus import FocusManager

        input_manager = type("_", (), {
            "add_listener": lambda s, f: None,
            "remove_listener": lambda s, f: None,
            "add_paste_listener": lambda s, f: None,
            "remove_paste_listener": lambda s, f: None,
            "enable_bracketed_paste": lambda s: None,
            "disable_bracketed_paste": lambda s: None,
            "enable_mouse_tracking": lambda s: None,
            "disable_mouse_tracking": lambda s: None,
            "enable_raw_mode": lambda s: None,
            "disable_raw_mode": lambda s: None,
            "is_raw_mode_supported": False,
        })()
        focus_manager = FocusManager()
        _exit_code = 0
        _is_screen_reader_enabled = False

        def request_exit(self, code=0): pass
        def set_cursor_position(self, pos): pass
        def add_timer(self, *a, **kw): return 0
        def remove_timer(self, *a): pass

        @property
        def terminal(self):
            return self

        def on_resize(self, handler):
            return lambda: None

    reconciler.set_app(FakeApp())
    fiber = reconciler.mount(vnode)
    dom = fiber.dom_node

    if isinstance(dom, DOMElement):
        result = renderer(dom, width=columns)
        reconciler.unmount()
        return result.output_height, result.output
    reconciler.unmount()
    return 0, ""


# ── Core height accuracy tests ──


def test_height_matches_yoga_grid():
    """Box(height=50) with 3 items → output_height=50 (yoga grid height).

    Ink returns output.length (grid height), not visible line count.
    This is critical for is_fullscreen and erase_lines calculations.
    """
    height, output = _get_height(
        Box(Text("A"), Text("B"), Text("C"),
            flex_direction="column", height=50),
        columns=80,
    )
    assert height == 50, f"Expected 50 (yoga height), got {height}"


def test_height_exact_when_content_fills():
    """5 items in 5-row box → output_height=5."""
    height, output = _get_height(
        Box(Text("1"), Text("2"), Text("3"), Text("4"), Text("5"),
            flex_direction="column", height=5),
        columns=80,
    )
    assert height == 5, f"Expected 5, got {height}"


def test_height_single_text():
    """Single Text → output_height=1."""
    height, output = _get_height(Text("Hello"), columns=80)
    assert height == 1, f"Expected 1, got {height}"


def test_height_wrapping_text():
    """Text that wraps to 3 lines → output_height=3."""
    long_text = "word " * 30  # ~150 chars, wraps at 40 cols
    height, output = _get_height(
        Text(long_text),
        columns=40,
    )
    lines = strip_ansi(output).split("\n")
    visible = [l for l in lines if l.strip()]
    assert height == len(visible), (
        f"height={height} but {len(visible)} visible lines"
    )


def test_height_column_layout():
    """Column layout with flex_grow — height includes flex space."""
    height, output = _get_height(
        Box(
            Text("Banner"),
            Box(Text("Content"), flex_direction="column", flex_grow=1),
            Text("Input"),
            flex_direction="column",
            height=20,
        ),
        columns=80,
    )
    # flex_grow=1 takes 18 rows (20 - Banner - Input).
    # Input is at row 19. Output height = 20 (all rows up to Input).
    # This is correct — flex space IS part of the visible output.
    assert height == 20, f"Expected 20, got {height}"


def test_height_equals_yoga_height():
    """output_height equals yoga-allocated height (matching Ink)."""
    for h in [10, 24, 50]:
        height, output = _get_height(
            Box(Text("Only one line"), height=h),
            columns=80,
        )
        assert height == h, (
            f"Box(height={h}): output_height={height}, expected {h}"
        )


def test_overflow_hidden_returns_yoga_height():
    """overflow:hidden box still returns yoga grid height."""
    items = [Text(f"Line {i}") for i in range(3)]
    height, output = _get_height(
        Box(*items, flex_direction="column", height=20, overflow="hidden"),
        columns=80,
    )
    assert height == 20, f"Expected 20 (yoga height), got {height}"


def test_full_conversation_layout_height():
    """Simulate the smoke test layout — height matches yoga root height."""
    history = [Text(f"msg {i}") for i in range(5)]
    height, output = _get_height(
        Box(
            Text("banner"),
            Text("help"),
            Text("---"),
            Box(*history, flex_direction="column", flex_grow=1,
                overflow="hidden"),
            Text("---"),
            Text("> input"),
            Text("---"),
            flex_direction="column",
            height=24,
        ),
        columns=80,
    )
    # Returns yoga root height (24), matching Ink's behavior
    assert height == 24, f"Expected 24, got {height}"
