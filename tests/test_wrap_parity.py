"""Text wrap parity tests — measure must match render.

Without parity, yoga allocates N rows while the renderer produces
N+1 rows, and items overlap. These tests guard against that regression.
"""
from pyink import Box, Text, render_to_string_sync
from pyink.renderer.ansi import strip_ansi
from pyink.text_wrap import (
    truncate_end,
    truncate_middle,
    truncate_start,
    visible_width,
    wrap_text,
    wrap_text_hard,
    wrap_text_soft,
)

# ── visible_width ──


def test_visible_width_plain():
    assert visible_width("hello") == 5


def test_visible_width_ansi():
    assert visible_width("\x1b[31mhello\x1b[0m") == 5


def test_visible_width_cjk():
    # CJK wide chars count as 2 columns each
    assert visible_width("あいう") == 6


def test_visible_width_mixed():
    assert visible_width("a\x1b[1mb\x1b[0mc") == 3


# ── soft wrap (word boundary) ──


def test_wrap_soft_respects_words():
    lines = wrap_text_soft("hello world foo bar", 11)
    assert lines == ["hello world", "foo bar"]


def test_wrap_soft_trims_trailing_whitespace():
    # wrap-ansi with hardBreaks: true trims trailing ws per line
    lines = wrap_text_soft("aa   bb   cc   dd", 6)
    # Each wrapped line should be rstrip'd
    for line in lines[:-1]:
        assert line == line.rstrip(), f"line not trimmed: {line!r}"


def test_wrap_soft_preserves_ansi():
    text = "\x1b[31mhello\x1b[0m \x1b[32mworld\x1b[0m"
    lines = wrap_text_soft(text, 5)
    # ANSI codes preserved, width still respected
    assert visible_width(lines[0]) == 5
    assert "\x1b[31m" in lines[0]


# ── hard wrap ──


def test_wrap_hard_exact_width():
    lines = wrap_text_hard("abcdefghij", 3)
    assert lines == ["abc", "def", "ghi", "j"]


def test_wrap_hard_wide_chars():
    """Hard wrap must respect visible width, NOT character count.

    "あい" is 2 chars but 4 visible cols. With max_width=3, it should
    wrap after 1 char (2 cols). The buggy impl would slice at [0:3]
    giving "あい" which is 4 cols wide — layout corruption.
    """
    lines = wrap_text_hard("あいうえお", 3)
    # Each line should be ≤ 3 visible cols
    for line in lines:
        assert visible_width(line) <= 3, f"line exceeds width: {line!r}"


def test_wrap_hard_ansi_preserved():
    """Hard wrap must NOT split ANSI escape sequences."""
    text = "\x1b[31mabcdef\x1b[0m"
    lines = wrap_text_hard(text, 3)
    # Each line's visible width respected
    for line in lines:
        assert visible_width(line) <= 3
    # ANSI sequence not broken
    joined = "".join(lines)
    assert "\x1b[31m" in joined
    assert "\x1b[0m" in joined


# ── truncate ──


def test_truncate_end():
    assert truncate_end("hello world", 5) == "hello"


def test_truncate_start():
    # Keeps last N cols
    result = truncate_start("hello world", 5)
    assert visible_width(result) <= 5


def test_truncate_middle():
    result = truncate_middle("hello world", 7)
    assert "\u2026" in result  # ellipsis
    assert visible_width(result) <= 7


def test_truncate_ansi_preserved():
    text = "\x1b[31mhello world\x1b[0m"
    result = truncate_end(text, 5)
    assert visible_width(result) == 5
    assert "\x1b[31m" in result


# ── measure == render (the critical invariant) ──


def test_measure_matches_render_simple():
    """Yoga-measured height == actual rendered line count."""
    text = Text("word " * 20)
    output = strip_ansi(
        render_to_string_sync(Box(text, flex_direction="column"), columns=40),
    )
    rendered_lines = [ln for ln in output.split("\n") if ln.strip()]

    # Measure directly
    from pyink.text_wrap import wrap_text
    measured = wrap_text("word " * 20, 40, "wrap")
    measured_nonempty = [ln for ln in measured if ln.strip()]

    assert len(rendered_lines) == len(measured_nonempty), (
        f"render={len(rendered_lines)} measure={len(measured_nonempty)}"
    )


def test_measure_matches_render_ansi():
    """ANSI markdown content: measure == render lines."""
    text = (
        "\x1b[1mSure!\x1b[0m Here is a response that streams in word by word "
        "to test the rendering pipeline. Each word appears with a small delay "
        "to simulate real LLM token streaming."
    )
    for cols in [40, 80, 100, 133]:
        output = strip_ansi(
            render_to_string_sync(
                Box(Text(text), flex_direction="column"), columns=cols,
            ),
        )
        rendered_lines = [ln for ln in output.split("\n") if ln.strip()]
        measured = wrap_text(text, cols, "wrap")
        measured_nonempty = [ln for ln in measured if ln.strip()]

        assert len(rendered_lines) == len(measured_nonempty), (
            f"cols={cols} render={len(rendered_lines)} "
            f"measure={len(measured_nonempty)}"
        )


def test_no_item_overlap_with_long_text():
    """Two text items stacked — second must render AFTER first's wrapped lines."""
    tree = Box(
        Text("word " * 30),  # Long, will wrap
        Text("SENTINEL"),
        flex_direction="column",
    )
    output = strip_ansi(render_to_string_sync(tree, columns=40))
    # SENTINEL must appear on its own line (not overlapping long text)
    lines = output.split("\n")
    sentinel_line = next(
        (i for i, ln in enumerate(lines) if "SENTINEL" in ln), -1,
    )
    assert sentinel_line >= 0
    # The SENTINEL line must contain ONLY "SENTINEL" (no overlap chars)
    assert lines[sentinel_line].strip() == "SENTINEL", (
        f"overlap detected: {lines[sentinel_line]!r}"
    )


def test_wrap_with_trailing_spaces_no_overlap():
    """Trailing spaces in wrapped lines shouldn't push next item down wrong."""
    tree = Box(
        Text("hello   world   foo   bar   baz   qux"),
        Text("NEXT"),
        flex_direction="column",
    )
    output = strip_ansi(render_to_string_sync(tree, columns=15))
    assert "NEXT" in output
    # NEXT must NOT share a line with wrapped content
    lines = output.split("\n")
    for line in lines:
        if "NEXT" in line:
            assert line.strip() == "NEXT", (
                f"NEXT overlapped: {line!r}"
            )
