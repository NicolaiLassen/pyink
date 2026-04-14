"""Virtual output class matching Ink's output.ts 1:1.

Uses a per-character grid (like Ink's StyledChar[][]) where each cell holds
a single visible character plus its ANSI style prefix. This is the key to
correct rendering - ANSI strings are decomposed into individual characters,
positioned on the grid, then reassembled.
"""
from __future__ import annotations

import re
from typing import Any

_ANSI_RE = re.compile(r"(\x1b\[[0-9;]*[a-zA-Z])")
_ANSI_STRIP_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
RESET = "\x1b[0m"


def _char_width(ch: str) -> int:
    """Width of a single character (2 for CJK wide chars)."""
    try:
        import unicodedata
        eaw = unicodedata.east_asian_width(ch)
        return 2 if eaw in ("W", "F") else 1
    except Exception:
        return 1


def _tokenize_styled(text: str) -> list[tuple[str, str]]:
    """Decompose a styled string into (styles_prefix, char) pairs.

    E.g. "\\x1b[31mAB\\x1b[0m" -> [("\\x1b[31m", "A"), ("\\x1b[31m", "B")]

    This matches Ink's styledCharsFromTokens(tokenize(line)).

    Parameters
    ----------
    text : str
        A string potentially containing ANSI escape sequences.

    Returns
    -------
    list[tuple[str, str]]
        Each tuple is ``(accumulated_style_prefix, character)``.
    """
    result: list[tuple[str, str]] = []
    parts = _ANSI_RE.split(text)

    current_styles: list[str] = []

    for part in parts:
        if not part:
            continue
        if _ANSI_RE.fullmatch(part):
            # This is an ANSI escape sequence
            if part == RESET:
                current_styles.clear()
            else:
                current_styles.append(part)
        else:
            # This is regular text - emit each character with current styles
            prefix = "".join(current_styles)
            for ch in part:
                result.append((prefix, ch))

    return result


def _string_width(text: str) -> int:
    """Visible width of a string, ignoring ANSI codes."""
    clean = _ANSI_STRIP_RE.sub("", text)
    w = 0
    for ch in clean:
        w += _char_width(ch)
    return w


class StyledChar:
    """A single character with its ANSI style prefix.

    Parameters
    ----------
    value : str, optional
        The visible character (default ``" "``).
    styles : str, optional
        Accumulated ANSI style prefix (default ``""``).
    full_width : bool, optional
        Whether this is a wide (CJK) character (default ``False``).
    """
    __slots__ = ("value", "styles", "full_width")

    def __init__(self, value: str = " ", styles: str = "", full_width: bool = False):
        self.value = value
        self.styles = styles
        self.full_width = full_width

    def to_string(self) -> str:
        if not self.styles:
            return self.value
        return f"{self.styles}{self.value}{RESET}"


class Output:
    """Virtual terminal buffer matching Ink's Output class exactly.

    Uses a StyledChar[][] grid. Each cell holds one character with its
    ANSI styles. Handles wide characters, clipping, and transformers.

    Parameters
    ----------
    width : int
        Buffer width in columns.
    height : int
        Buffer height in rows.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._operations: list[tuple[str, Any]] = []

    def write(self, x: int, y: int, text: str) -> None:
        """Write styled text at position (x, y).

        Parameters
        ----------
        x : int
            Column position.
        y : int
            Row position.
        text : str
            Styled text to write (may contain newlines).
        """
        if not text:
            return
        self._operations.append(("write", (x, y, text)))

    def clip(self, x1: int, x2: int, y1: int, y2: int) -> None:
        """Push a clipping region.

        Parameters
        ----------
        x1 : int
            Left boundary (inclusive).
        x2 : int
            Right boundary (exclusive).
        y1 : int
            Top boundary (inclusive).
        y2 : int
            Bottom boundary (exclusive).
        """
        self._operations.append(("clip", (x1, x2, y1, y2)))

    def unclip(self) -> None:
        """Pop the most recent clipping region."""
        self._operations.append(("unclip", None))

    def get(self) -> str:
        """Convert the buffer to final string output.

        Matches Ink's Output.get() - initializes a StyledChar grid,
        processes all operations, handles clipping and wide characters,
        then converts to string.

        Returns
        -------
        str
            The rendered output as a plain string with embedded ANSI codes.
        """
        # Initialize grid with spaces (matching Ink's initialization)
        grid: list[list[StyledChar]] = []
        for y in range(self.height):
            row: list[StyledChar] = []
            for x in range(self.width):
                row.append(StyledChar(" ", "", False))
            grid.append(row)

        clips: list[tuple[int, int, int, int]] = []

        for op_type, data in self._operations:
            if op_type == "clip":
                clips.append(data)
                continue
            if op_type == "unclip":
                if clips:
                    clips.pop()
                continue

            x, y, text = data
            lines = text.split("\n")

            clip = clips[-1] if clips else None

            if clip:
                cx1, cx2, cy1, cy2 = clip

                # Skip if entirely outside clip region
                width = _string_width(text)
                if x + width < cx1 or x > cx2:
                    continue
                height = len(lines)
                if y + height < cy1 or y > cy2:
                    continue

            offset_y = 0
            for line_idx, line in enumerate(lines):
                row_idx = y + offset_y
                if row_idx < 0 or row_idx >= self.height:
                    offset_y += 1
                    continue

                # Apply clip vertically
                if clip:
                    cx1, cx2, cy1, cy2 = clip
                    if row_idx < cy1 or row_idx >= cy2:
                        offset_y += 1
                        continue

                current_row = grid[row_idx]

                # Tokenize the line into styled characters
                characters = _tokenize_styled(line)
                if not characters:
                    offset_y += 1
                    continue

                offset_x = x

                # Apply horizontal clipping
                if clip:
                    cx1, cx2, cy1, cy2 = clip
                    # Skip characters before clip start
                    clipped_chars: list[tuple[str, str]] = []
                    pos = x
                    for styles, ch in characters:
                        cw = _char_width(ch)
                        if pos + cw <= cx1:
                            pos += cw
                            continue
                        if pos >= cx2:
                            break
                        clipped_chars.append((styles, ch))
                        pos += cw
                    characters = clipped_chars
                    offset_x = max(x, cx1)

                # Wide character boundary cleanup (matching Ink)
                if (
                    0 <= offset_x < self.width
                    and current_row[offset_x].value == ""
                    and offset_x > 0
                    and _char_width(current_row[offset_x - 1].value) > 1
                ):
                    current_row[offset_x - 1] = StyledChar(" ")

                # Write characters to the grid
                for styles, ch in characters:
                    if offset_x < 0 or offset_x >= self.width:
                        offset_x += _char_width(ch)
                        continue

                    cw = _char_width(ch)
                    current_row[offset_x] = StyledChar(ch, styles, cw > 1)

                    # For wide characters, clear following cells
                    if cw > 1:
                        for i in range(1, cw):
                            if offset_x + i < self.width:
                                current_row[offset_x + i] = StyledChar(
                                    "", styles, False
                                )

                    offset_x += cw

                # Wide character boundary cleanup at the end
                if (
                    0 <= offset_x < self.width
                    and current_row[offset_x].value == ""
                ):
                    current_row[offset_x] = StyledChar(" ")

                offset_y += 1

        # Convert grid to string (matching Ink's styledCharsToString + trimEnd)
        result_lines: list[str] = []
        for row in grid:
            line = _styled_row_to_string(row).rstrip()
            result_lines.append(line)

        # Remove trailing empty lines
        while result_lines and not result_lines[-1]:
            result_lines.pop()

        return "\n".join(result_lines)

    def get_height(self) -> int:
        """Return the number of output lines.

        Returns
        -------
        int
            Line count of the rendered output, or 0 if empty.
        """
        output = self.get()
        if not output:
            return 0
        return output.count("\n") + 1


def _styled_row_to_string(row: list[StyledChar]) -> str:
    """Convert a row of StyledChars to a string, coalescing adjacent same-style runs.

    Parameters
    ----------
    row : list[StyledChar]
        A single row of styled character cells.

    Returns
    -------
    str
        The row rendered as a string with ANSI style sequences.
    """
    if not row:
        return ""

    result: list[str] = []
    current_styles = ""

    for cell in row:
        if cell.value == "":
            # Placeholder for wide character - skip
            continue

        if cell.styles != current_styles:
            # Style changed - close old, open new
            if current_styles:
                result.append(RESET)
            if cell.styles:
                result.append(cell.styles)
            current_styles = cell.styles

        result.append(cell.value)

    # Close any open style
    if current_styles:
        result.append(RESET)

    return "".join(result)
