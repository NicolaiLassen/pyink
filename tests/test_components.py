"""Tests for high-level components (TextInput, SelectInput, etc.)."""
from pyink import (
    ConfirmInput,
    ProgressBar,
    SelectInput,
    SelectItem,
    Spinner,
    TextInput,
    render_to_string_sync,
)
from pyink.renderer.ansi import strip_ansi


def _render(vnode, columns=40):
    return strip_ansi(render_to_string_sync(vnode, columns=columns))


# ── TextInput ──


def test_text_input_empty_shows_placeholder():
    output = _render(TextInput(value="", placeholder="Type here..."))
    assert "Type here..." in output


def test_text_input_value():
    output = _render(TextInput(value="hello"))
    assert "hello" in output


def test_text_input_mask():
    output = _render(TextInput(value="secret", mask="*"))
    assert "******" in output
    assert "secret" not in output


# ── SelectInput ──


def test_select_input_renders_items():
    items = [
        SelectItem(label="Apple"),
        SelectItem(label="Banana"),
        SelectItem(label="Cherry"),
    ]
    output = _render(SelectInput(items=items))
    assert "Apple" in output
    assert "Banana" in output
    assert "Cherry" in output


def test_select_input_shows_indicator():
    items = [SelectItem(label="First"), SelectItem(label="Second")]
    output = _render(SelectInput(items=items, indicator=">>"))
    assert ">> First" in output


def test_select_input_limit():
    items = [SelectItem(label=f"Item {i}") for i in range(10)]
    output = _render(SelectInput(items=items, limit=3))
    assert "Item 0" in output
    assert "Item 9" not in output


def test_select_input_empty():
    output = _render(SelectInput(items=[]))
    assert output is not None


# ── Spinner ──


def test_spinner_renders():
    output = _render(Spinner(type="dots"))
    # Spinner renders some character from the dots frames
    assert len(output.strip()) > 0


def test_spinner_unknown_type_fallback():
    """Unknown spinner type should fall back to dots."""
    output = _render(Spinner(type="nonexistent"))
    assert output is not None


# ── ProgressBar ──


def test_progress_bar_empty():
    output = _render(ProgressBar(percent=0, width=10))
    # All empty characters (spaces)
    assert output.count(" ") >= 10


def test_progress_bar_half():
    output = render_to_string_sync(ProgressBar(percent=0.5, width=10), columns=40)
    # About half filled with the block character
    assert "\u2588" in output


def test_progress_bar_full():
    output = render_to_string_sync(
        ProgressBar(percent=1.0, width=10), columns=40,
    )
    # Fully filled
    assert output.count("\u2588") == 10


def test_progress_bar_clamps_overflow():
    output = render_to_string_sync(
        ProgressBar(percent=1.5, width=10), columns=40,
    )
    assert output.count("\u2588") == 10


# ── ConfirmInput ──


def test_confirm_input_renders_placeholder():
    output = _render(ConfirmInput(placeholder="[y/N]"))
    assert "[y/N]" in output
