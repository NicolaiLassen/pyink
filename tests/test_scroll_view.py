"""Tests for message rendering in column layouts.

Verifies that messages render correctly in a simple Box column layout
(no scroll component — just flex_grow=1 and natural clipping).
"""
from pyink import Box, Text, render_to_string_sync
from pyink.renderer.ansi import strip_ansi


def _render(vnode, columns=40):
    return strip_ansi(render_to_string_sync(vnode, columns=columns))


def test_messages_render():
    output = _render(Box(
        Text("Msg 0"), Text("Msg 1"), Text("Msg 2"),
        flex_direction="column",
    ))
    assert "Msg 0" in output
    assert "Msg 1" in output
    assert "Msg 2" in output


def test_conversation_layout():
    output = _render(Box(
        Text("Banner"),
        Box(Text("User: Hello"), Text("Bot: Hi!"),
            flex_direction="column", flex_grow=1),
        Text("> input"),
        flex_direction="column", height=12,
    ))
    assert "Banner" in output
    assert "User: Hello" in output
    assert "Bot: Hi!" in output
    assert "> input" in output


def test_streaming_then_history():
    # During streaming
    items = [Text("User: Hello"), Text("Bot is typing...")]
    output = _render(Box(
        Box(*items, flex_direction="column", flex_grow=1),
        Text("> input"),
        flex_direction="column", height=12,
    ))
    assert "User: Hello" in output
    assert "Bot is typing..." in output

    # After streaming
    items2 = [Text("User: Hello"), Text("Bot: Done")]
    output2 = _render(Box(
        Box(*items2, flex_direction="column", flex_grow=1),
        Text("> input"),
        flex_direction="column", height=12,
    ))
    assert "User: Hello" in output2
    assert "Bot: Done" in output2
