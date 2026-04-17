"""Shared text wrapping / truncation helpers.

ANSI-aware implementations used by BOTH the measure path (``dom.py``)
and the render path (``renderer/render_node.py``). Using the same
functions for measure and render prevents yoga-renderer height
mismatch — the exact class of bug that causes item overlap.

Port of Ink's behavior:
- ``wrap``: soft wrap at word boundaries (ANSI preserved)
- ``hard``: wrap at exact visible-width boundary
- ``truncate*``: truncate with ANSI preservation
"""
from __future__ import annotations

import re
import unicodedata

# Comprehensive ANSI regex — matches CSI (with colons for 38:2:R:G:B),
# private CSI (?25h), OSC sequences, SS2/SS3/DCS/RIS, and 8-bit CSI.
_ANSI_TOKEN_RE = re.compile(
    r"(\x1b\[[0-9;:]*[a-zA-Z]"
    r"|\x1b\[\?[0-9;]*[a-zA-Z]"
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|\x1b[NOPc]"
    r"|\x9b[0-9;:]*[a-zA-Z])"
)


def visible_char_width(ch: str) -> int:
    """Width of a single visible character (1 or 2 for CJK)."""
    try:
        eaw = unicodedata.east_asian_width(ch)
        return 2 if eaw in ("W", "F") else 1
    except Exception:
        return 1


def ansi_tokenize(text: str) -> list[tuple[str, int]]:
    """Split text into ``(chunk, visible_width)`` pairs.

    ANSI escape sequences get width 0. Visible characters get their
    display width (2 for CJK wide chars, 1 otherwise).
    """
    result: list[tuple[str, int]] = []
    last = 0
    for m in _ANSI_TOKEN_RE.finditer(text):
        start, end = m.start(), m.end()
        if start > last:
            for ch in text[last:start]:
                result.append((ch, visible_char_width(ch)))
        result.append((m.group(0), 0))
        last = end
    if last < len(text):
        for ch in text[last:]:
            result.append((ch, visible_char_width(ch)))
    return result


def visible_width(text: str) -> int:
    """Visible width of a string, ignoring ANSI codes + handling wide chars."""
    w = 0
    for _, cw in ansi_tokenize(text):
        w += cw
    return w


def wrap_text_soft(text: str, max_width: int) -> list[str]:
    """Word-boundary wrap, ANSI-aware. Port of Ink's wrapAnsi(hardBreaks: true).

    - Respects existing newlines
    - Breaks at word boundaries (spaces)
    - Trims trailing whitespace from wrapped lines (except the last)
    """
    if max_width <= 0:
        return [text]

    lines: list[str] = []
    for raw_line in text.split("\n"):
        if not raw_line:
            lines.append("")
            continue

        words = raw_line.split(" ")
        current = ""
        for word in words:
            if not current:
                current = word
            elif visible_width(current + " " + word) <= max_width:
                current += " " + word
            else:
                lines.append(current.rstrip())
                current = word

        if current:
            lines.append(current)

    return lines if lines else [""]


def wrap_text_hard(text: str, max_width: int) -> list[str]:
    """Hard wrap at exact visible-width boundary, ANSI-aware.

    Breaks at the character position where cumulative visible width
    reaches ``max_width``, preserving ANSI escape sequences and
    correctly handling wide (CJK) characters.
    """
    if max_width <= 0:
        return [text]

    lines: list[str] = []
    for raw_line in text.split("\n"):
        if not raw_line:
            lines.append("")
            continue

        tokens = ansi_tokenize(raw_line)
        current: list[str] = []
        w = 0
        for chunk, cw in tokens:
            if cw == 0:
                # ANSI sequence — always include, no width impact
                current.append(chunk)
            elif w + cw > max_width:
                lines.append("".join(current))
                current = [chunk]
                w = cw
            else:
                current.append(chunk)
                w += cw
        if current:
            lines.append("".join(current))
    return lines if lines else [""]


def truncate_end(text: str, max_width: int) -> str:
    """Truncate from the end (keep first max_width cols), ANSI-aware."""
    if max_width <= 0:
        return ""
    result: list[str] = []
    w = 0
    for chunk, cw in ansi_tokenize(text):
        if cw == 0:
            result.append(chunk)
        elif w + cw > max_width:
            break
        else:
            result.append(chunk)
            w += cw
    return "".join(result)


def truncate_start(text: str, max_width: int) -> str:
    """Truncate from the start (keep last max_width cols), ANSI-aware."""
    if max_width <= 0:
        return ""
    result: list[str] = []
    w = 0
    for chunk, cw in reversed(ansi_tokenize(text)):
        if cw == 0:
            result.append(chunk)
        elif w + cw > max_width:
            break
        else:
            result.append(chunk)
            w += cw
    result.reverse()
    return "".join(result)


def truncate_middle(text: str, max_width: int) -> str:
    """Truncate the middle with ellipsis, ANSI-aware."""
    if max_width <= 3:
        return truncate_end(text, max_width)
    half = (max_width - 1) // 2
    start = truncate_end(text, half)
    end = truncate_start(text, max_width - half - 1)
    return start + "\u2026" + end


def wrap_text(text: str, max_width: int, wrap_mode: str = "wrap") -> list[str]:
    """Apply the requested wrap/truncate mode. Returns list of lines.

    Modes: ``wrap`` (soft), ``hard``, ``truncate``/``truncate-end``,
    ``truncate-start``, ``truncate-middle``.
    """
    if wrap_mode in ("truncate", "truncate-end", "truncate_end"):
        return [
            truncate_end(line, max_width) if visible_width(line) > max_width else line
            for line in text.split("\n")
        ]
    if wrap_mode in ("truncate-start", "truncate_start"):
        return [
            truncate_start(line, max_width) if visible_width(line) > max_width else line
            for line in text.split("\n")
        ]
    if wrap_mode in ("truncate-middle", "truncate_middle"):
        return [
            truncate_middle(line, max_width) if visible_width(line) > max_width else line
            for line in text.split("\n")
        ]
    if wrap_mode == "hard":
        return wrap_text_hard(text, max_width)
    return wrap_text_soft(text, max_width)
