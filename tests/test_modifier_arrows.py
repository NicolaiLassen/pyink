"""Tests for modifier + arrow/home/end key combinations.

Verifies xterm CSI 1;Nd encoding (where N = 2..8 encodes modifier
combinations) is parsed correctly for all 7 modifier combos * 6 keys.
"""
from pyink.input.keys import parse_keypress


# (modifier_num, expected_shift, expected_alt, expected_ctrl)
MODIFIERS = [
    (2, True, False, False),   # Shift
    (3, False, True, False),   # Alt
    (4, True, True, False),    # Alt+Shift
    (5, False, False, True),   # Ctrl
    (6, True, False, True),    # Ctrl+Shift
    (7, False, True, True),    # Ctrl+Alt
    (8, True, True, True),     # Ctrl+Alt+Shift
]

ARROW_KEYS = [
    ("A", "up_arrow"),
    ("B", "down_arrow"),
    ("C", "right_arrow"),
    ("D", "left_arrow"),
    ("H", "home"),
    ("F", "end"),
]


def test_shift_up():
    _, key = parse_keypress(b"\x1b[1;2A")
    assert key.up_arrow is True
    assert key.shift is True
    assert key.ctrl is False
    assert key.meta is False


def test_alt_right():
    """Alt+Right — word-forward navigation in text inputs."""
    _, key = parse_keypress(b"\x1b[1;3C")
    assert key.right_arrow is True
    assert key.meta is True
    assert key.shift is False
    assert key.ctrl is False


def test_alt_left():
    """Alt+Left — word-back navigation in text inputs."""
    _, key = parse_keypress(b"\x1b[1;3D")
    assert key.left_arrow is True
    assert key.meta is True


def test_ctrl_right():
    _, key = parse_keypress(b"\x1b[1;5C")
    assert key.right_arrow is True
    assert key.ctrl is True
    assert key.shift is False
    assert key.meta is False


def test_ctrl_shift_up():
    _, key = parse_keypress(b"\x1b[1;6A")
    assert key.up_arrow is True
    assert key.ctrl is True
    assert key.shift is True


def test_ctrl_alt_down():
    _, key = parse_keypress(b"\x1b[1;7B")
    assert key.down_arrow is True
    assert key.ctrl is True
    assert key.meta is True
    assert key.shift is False


def test_ctrl_alt_shift_left():
    _, key = parse_keypress(b"\x1b[1;8D")
    assert key.left_arrow is True
    assert key.ctrl is True
    assert key.meta is True
    assert key.shift is True


def test_ctrl_home():
    """Ctrl+Home — jump to top (Claude Code uses this)."""
    _, key = parse_keypress(b"\x1b[1;5H")
    assert key.home is True
    assert key.ctrl is True


def test_ctrl_end():
    """Ctrl+End — jump to bottom."""
    _, key = parse_keypress(b"\x1b[1;5F")
    assert key.end is True
    assert key.ctrl is True


def test_all_modifier_arrow_combos():
    """Exhaustive check: all 7 modifier combos * 6 keys (42 total)."""
    for mod_num, want_shift, want_alt, want_ctrl in MODIFIERS:
        for final_char, attr in ARROW_KEYS:
            seq = f"\x1b[1;{mod_num}{final_char}".encode()
            _, key = parse_keypress(seq)
            assert getattr(key, attr) is True, (
                f"seq={seq!r} expected {attr}=True"
            )
            assert key.shift == want_shift, f"seq={seq!r} shift wrong"
            assert key.meta == want_alt, f"seq={seq!r} meta wrong"
            assert key.ctrl == want_ctrl, f"seq={seq!r} ctrl wrong"


def test_plain_arrow_no_modifier():
    """Plain arrow keys (no CSI 1;N) should still work."""
    _, key = parse_keypress(b"\x1b[A")
    assert key.up_arrow is True
    assert not key.shift
    assert not key.ctrl
    assert not key.meta
