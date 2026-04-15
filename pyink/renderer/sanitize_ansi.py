"""ANSI sequence sanitizer.

Port of Ink's ``src/sanitize-ansi.ts``.
Strips layout-breaking ANSI sequences (cursor movement, screen clearing)
while preserving SGR (colors/styles) and OSC (hyperlinks).
"""
from __future__ import annotations

import re

# Match all ANSI escape sequences (comprehensive)
_ANSI_RE = re.compile(
    r"("
    r"\x1b\[[0-9;:]*[a-zA-Z]"              # CSI sequences (incl. colon-separated SGR)
    r"|\x1b\[\?[0-9;]*[a-zA-Z]"            # Private CSI (?25h etc.)
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC sequences (hyperlinks, titles)
    r"|\x1b[NOPc]"                          # SS2, SS3, DCS, RIS
    r"|\x9b[0-9;:]*[a-zA-Z]"               # 8-bit CSI (C1 control)
    r")"
)

# SGR (Select Graphic Rendition) — colors and styles: ESC [ ... m
# Includes colon-separated params for 38:2:R:G:B truecolor
_SGR_RE = re.compile(r"^\x1b\[[0-9;:]*m$")

# OSC (Operating System Command) — hyperlinks etc: ESC ] ... BEL/ST
_OSC_RE = re.compile(r"^\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)$")


def sanitize_ansi(text: str) -> str:
    """Strip layout-breaking ANSI sequences, keep colors and hyperlinks.

    Port of Ink's ``sanitizeAnsi`` (sanitize-ansi.ts).

    Parameters
    ----------
    text : str
        Text potentially containing ANSI escape sequences.

    Returns
    -------
    str
        Text with only SGR and OSC sequences preserved.
    """
    def _replace(match: re.Match) -> str:
        seq = match.group(0)
        # Keep SGR (colors/styles)
        if _SGR_RE.match(seq):
            return seq
        # Keep OSC (hyperlinks)
        if _OSC_RE.match(seq):
            return seq
        # Strip everything else (cursor movement, screen clearing, etc.)
        return ""

    return _ANSI_RE.sub(_replace, text)
