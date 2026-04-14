"""Virtual output class matching Ink's output.ts 1:1.

Uses a per-character grid (like Ink's StyledChar[][]) where each cell holds
a single visible character plus its ANSI style prefix. Supports transformers,
clipping, and wide characters.
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

    Port of Ink's ``styledCharsFromTokens(tokenize(line))``.
    """
    result: list[tuple[str, str]] = []
    parts = _ANSI_RE.split(text)

    current_styles: list[str] = []

    for part in parts:
        if not part:
            continue
        if _ANSI_RE.fullmatch(part):
            if part == RESET:
                current_styles.clear()
            else:
                current_styles.append(part)
        else:
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


class _OutputCaches:
    """Cache for string widths and styled chars. Port of Ink's OutputCaches."""

    def __init__(self) -> None:
        self._widths: dict[str, int] = {}
        self._block_widths: dict[str, int] = {}
        self._styled_chars: dict[str, list[tuple[str, str]]] = {}

    def get_styled_chars(self, line: str) -> list[tuple[str, str]]:
        cached = self._styled_chars.get(line)
        if cached is None:
            cached = _tokenize_styled(line)
            self._styled_chars[line] = cached
        return cached

    def get_string_width(self, text: str) -> int:
        cached = self._widths.get(text)
        if cached is None:
            cached = _string_width(text)
            self._widths[text] = cached
        return cached

    def get_widest_line(self, text: str) -> int:
        cached = self._block_widths.get(text)
        if cached is None:
            line_width = 0
            for line in text.split("\n"):
                line_width = max(line_width, self.get_string_width(line))
            cached = line_width
            self._block_widths[text] = cached
        return cached


class StyledChar:
    """A single character with its ANSI style prefix."""
    __slots__ = ("value", "styles", "full_width")

    def __init__(self, value: str = " ", styles: str = "", full_width: bool = False):
        self.value = value
        self.styles = styles
        self.full_width = full_width

    def to_string(self) -> str:
        if not self.styles:
            return self.value
        return f"{self.styles}{self.value}{RESET}"


# Type alias for output transformers (port of Ink's OutputTransformer)
OutputTransformer = Any  # Callable[[str, int], str]


class Output:
    """Virtual terminal buffer matching Ink's Output class.

    Uses a StyledChar[][] grid. Supports transformers, clipping,
    and wide characters.

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
        self._caches = _OutputCaches()

    def write(
        self,
        x: int,
        y: int,
        text: str,
        *,
        transformers: list[OutputTransformer] | None = None,
    ) -> None:
        """Write styled text at position (x, y).

        Port of Ink's Output.write (output.ts lines 105–124).

        Parameters
        ----------
        x : int
            Column position.
        y : int
            Row position.
        text : str
            Styled text to write (may contain newlines).
        transformers : list, optional
            Output transformer functions to apply per-line.
        """
        if not text:
            return
        self._operations.append(
            ("write", (x, y, text, transformers or []))
        )

    def clip(
        self,
        x1: int | None = None,
        x2: int | None = None,
        y1: int | None = None,
        y2: int | None = None,
    ) -> None:
        """Push a clipping region.

        Port of Ink's Output.clip (output.ts lines 126–133).
        Values of ``None`` mean no clip on that axis.
        """
        self._operations.append(("clip", (x1, x2, y1, y2)))

    def unclip(self) -> None:
        """Pop the most recent clipping region."""
        self._operations.append(("unclip", None))

    def get(self) -> tuple[str, int]:
        """Convert the buffer to final string output.

        Port of Ink's Output.get() (output.ts lines 139–318).

        Returns
        -------
        tuple[str, int]
            ``(output_string, height)``
        """
        # Initialize grid with spaces
        grid: list[list[StyledChar]] = []
        for _y in range(self.height):
            row: list[StyledChar] = []
            for _x in range(self.width):
                row.append(StyledChar(" ", "", False))
            grid.append(row)

        clips: list[tuple[int | None, int | None, int | None, int | None]] = []

        for op_type, data in self._operations:
            if op_type == "clip":
                clips.append(data)
                continue
            if op_type == "unclip":
                if clips:
                    clips.pop()
                continue

            x, y, text, transformers = data
            lines = text.split("\n")

            clip = clips[-1] if clips else None

            if clip:
                cx1, cx2, cy1, cy2 = clip

                clip_h = cx1 is not None and cx2 is not None
                clip_v = cy1 is not None and cy2 is not None

                # Skip if entirely outside clip region
                if clip_h:
                    width = self._caches.get_widest_line(text)
                    if x + width < cx1 or x > cx2:  # type: ignore
                        continue

                if clip_v:
                    height = len(lines)
                    if y + height < cy1 or y > cy2:  # type: ignore
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
                    if cy1 is not None and cy2 is not None:
                        if row_idx < cy1 or row_idx >= cy2:
                            offset_y += 1
                            continue

                current_row = grid[row_idx]

                # Apply transformers (Ink output.ts line 238-239)
                for transformer in transformers:
                    line = transformer(line, line_idx)

                # Tokenize the line into styled characters
                characters = self._caches.get_styled_chars(line)
                if not characters:
                    offset_y += 1
                    continue

                offset_x = x

                # Apply horizontal clipping
                if clip:
                    cx1, cx2, cy1, cy2 = clip
                    if cx1 is not None and cx2 is not None:
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

        generated_output = "\n".join(result_lines)

        return (generated_output, len(grid))


def _styled_row_to_string(row: list[StyledChar]) -> str:
    """Convert a row of StyledChars to a string."""
    if not row:
        return ""

    result: list[str] = []
    current_styles = ""

    for cell in row:
        if cell.value == "":
            continue

        if cell.styles != current_styles:
            if current_styles:
                result.append(RESET)
            if cell.styles:
                result.append(cell.styles)
            current_styles = cell.styles

        result.append(cell.value)

    if current_styles:
        result.append(RESET)

    return "".join(result)
