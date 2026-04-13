"""Tests for input parsing matching Ink's input system."""
from pyink.input.keys import Key, parse_keypress
from pyink.input.input_parser import InputParser, PasteEvent, create_input_parser


# Key parsing tests

def test_parse_regular_char():
    input_str, key = parse_keypress(b"a")
    assert input_str == "a"
    assert not key.ctrl
    assert not key.meta


def test_parse_return():
    input_str, key = parse_keypress(b"\r")
    assert key.return_key is True


def test_parse_escape():
    input_str, key = parse_keypress(b"\x1b")
    assert key.escape is True


def test_parse_tab():
    input_str, key = parse_keypress(b"\t")
    assert key.tab is True


def test_parse_backspace():
    input_str, key = parse_keypress(b"\x7f")
    assert key.backspace is True


def test_parse_ctrl_c():
    input_str, key = parse_keypress(b"\x03")
    assert key.ctrl is True
    assert input_str == "c"


def test_parse_ctrl_d():
    input_str, key = parse_keypress(b"\x04")
    assert key.ctrl is True
    assert input_str == "d"


def test_parse_up_arrow():
    input_str, key = parse_keypress(b"\x1b[A")
    assert key.up_arrow is True


def test_parse_down_arrow():
    input_str, key = parse_keypress(b"\x1b[B")
    assert key.down_arrow is True


def test_parse_right_arrow():
    input_str, key = parse_keypress(b"\x1b[C")
    assert key.right_arrow is True


def test_parse_left_arrow():
    input_str, key = parse_keypress(b"\x1b[D")
    assert key.left_arrow is True


def test_parse_page_up():
    input_str, key = parse_keypress(b"\x1b[5~")
    assert key.page_up is True


def test_parse_page_down():
    input_str, key = parse_keypress(b"\x1b[6~")
    assert key.page_down is True


def test_parse_delete():
    input_str, key = parse_keypress(b"\x1b[3~")
    assert key.delete is True


def test_parse_meta_key():
    input_str, key = parse_keypress(b"\x1ba")
    assert key.meta is True
    assert input_str == "a"


def test_parse_shift_tab():
    input_str, key = parse_keypress(b"\x1b[Z")
    assert key.tab is True
    assert key.shift is True


def test_parse_f1():
    input_str, key = parse_keypress(b"\x1bOP")
    assert key.f1 is True


# Input parser tests

def test_parser_simple_chars():
    parser = create_input_parser()
    events = parser.push("abc")
    assert events == ["abc"]


def test_parser_escape_sequence():
    parser = create_input_parser()
    events = parser.push("\x1b[A")
    assert events == ["\x1b[A"]


def test_parser_paste():
    parser = create_input_parser()
    events = parser.push("\x1b[200~hello world\x1b[201~")
    assert len(events) == 1
    assert isinstance(events[0], PasteEvent)
    assert events[0].paste == "hello world"


def test_parser_incomplete_sequence():
    parser = create_input_parser()
    events = parser.push("\x1b[")
    assert events == []
    assert parser.has_pending_escape()

    events = parser.push("A")
    assert events == ["\x1b[A"]


def test_parser_backspace_splitting():
    parser = create_input_parser()
    events = parser.push("\x7f\x7f\x7f")
    assert events == ["\x7f", "\x7f", "\x7f"]


def test_parser_mixed_input():
    parser = create_input_parser()
    events = parser.push("ab\x1b[Acd")
    assert events == ["ab", "\x1b[A", "cd"]


def test_parser_reset():
    parser = create_input_parser()
    parser.push("\x1b")
    assert parser.has_pending_escape()
    parser.reset()
    assert not parser.has_pending_escape()


def test_parser_flush_pending():
    parser = create_input_parser()
    parser.push("\x1b")
    pending = parser.flush_pending_escape()
    assert pending == "\x1b"
    assert not parser.has_pending_escape()
