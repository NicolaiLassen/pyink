"""Input parser matching Ink's input-parser.ts 1:1.

Parses raw terminal input into discrete keypress events and paste events.
Handles CSI sequences, SS3 sequences, escape sequences, and bracketed paste mode.
"""
from __future__ import annotations

from dataclasses import dataclass

ESCAPE = "\x1b"
PASTE_START = "\x1b[200~"
PASTE_END = "\x1b[201~"


@dataclass
class PasteEvent:
    """Represents a bracketed paste event."""

    paste: str


InputEvent = str | PasteEvent


def _is_csi_parameter_byte(byte: int) -> bool:
    return 0x30 <= byte <= 0x3F


def _is_csi_intermediate_byte(byte: int) -> bool:
    return 0x20 <= byte <= 0x2F


def _is_csi_final_byte(byte: int) -> bool:
    return 0x40 <= byte <= 0x7E


def _parse_csi_sequence(
    input_str: str, start_index: int, prefix_length: int
) -> tuple[str, int] | str | None:
    """Parse a CSI (Control Sequence Introducer) sequence.

    Parameters
    ----------
    input_str : str
        The raw input string to parse.
    start_index : int
        Index where the escape sequence begins.
    prefix_length : int
        Length of the escape prefix (1 for single ESC, 2 for double).

    Returns
    -------
    tuple[str, int] | str | None
        A ``(sequence, next_index)`` tuple on success, ``'pending'`` if
        more data is needed, or ``None`` if the sequence is invalid.
    """
    csi_payload_start = start_index + prefix_length + 1
    index = csi_payload_start

    while index < len(input_str):
        byte = ord(input_str[index])

        if _is_csi_parameter_byte(byte) or _is_csi_intermediate_byte(byte):
            index += 1
            continue

        # Preserve legacy terminal function-key sequences like ESC[[A
        if byte == 0x5B and index == csi_payload_start:
            index += 1
            continue

        if _is_csi_final_byte(byte):
            return (input_str[start_index : index + 1], index + 1)

        return None

    return "pending"


def _parse_ss3_sequence(
    input_str: str, start_index: int, prefix_length: int
) -> tuple[str, int] | str | None:
    """Parse an SS3 sequence.

    Parameters
    ----------
    input_str : str
        The raw input string to parse.
    start_index : int
        Index where the escape sequence begins.
    prefix_length : int
        Length of the escape prefix.

    Returns
    -------
    tuple[str, int] | str | None
        A ``(sequence, next_index)`` tuple on success, ``'pending'`` if
        more data is needed, or ``None`` if the sequence is invalid.
    """
    next_index = start_index + prefix_length + 2
    if next_index > len(input_str):
        return "pending"

    final_byte = ord(input_str[next_index - 1])
    if not _is_csi_final_byte(final_byte):
        return None

    return (input_str[start_index:next_index], next_index)


def _parse_control_sequence(
    input_str: str, start_index: int, prefix_length: int
) -> tuple[str, int] | str | None:
    """Parse a control sequence (CSI or SS3).

    Parameters
    ----------
    input_str : str
        The raw input string to parse.
    start_index : int
        Index where the escape sequence begins.
    prefix_length : int
        Length of the escape prefix.

    Returns
    -------
    tuple[str, int] | str | None
        A ``(sequence, next_index)`` tuple on success, ``'pending'`` if
        more data is needed, or ``None`` if the sequence is invalid.
    """
    seq_type_idx = start_index + prefix_length
    if seq_type_idx >= len(input_str):
        return "pending"

    seq_type = input_str[seq_type_idx]

    if seq_type == "[":
        return _parse_csi_sequence(input_str, start_index, prefix_length)

    if seq_type == "O":
        return _parse_ss3_sequence(input_str, start_index, prefix_length)

    return None


def _parse_escaped_code_point(
    input_str: str, escape_index: int
) -> tuple[str, int]:
    """Parse an escaped codepoint (ESC + char).

    Parameters
    ----------
    input_str : str
        The raw input string to parse.
    escape_index : int
        Index of the escape character.

    Returns
    -------
    tuple[str, int]
        A ``(sequence, next_index)`` tuple.
    """
    next_cp = ord(input_str[escape_index + 1]) if escape_index + 1 < len(input_str) else None
    next_cp_length = 2 if (next_cp is not None and next_cp > 0xFFFF) else 1
    next_index = escape_index + 1 + next_cp_length

    return (input_str[escape_index:next_index], next_index)


def _parse_escape_sequence(
    input_str: str, escape_index: int
) -> tuple[str, int] | str:
    """Parse an escape sequence.

    Parameters
    ----------
    input_str : str
        The raw input string to parse.
    escape_index : int
        Index of the escape character.

    Returns
    -------
    tuple[str, int] | str
        A ``(sequence, next_index)`` tuple on success, or ``'pending'``
        if more data is needed.
    """
    if escape_index == len(input_str) - 1:
        return "pending"

    next_char = input_str[escape_index + 1]

    # Double escape
    if next_char == ESCAPE:
        if escape_index + 2 >= len(input_str):
            return "pending"

        double_result = _parse_control_sequence(input_str, escape_index, 2)
        if double_result == "pending":
            return "pending"
        if double_result is not None:
            return double_result

        return (input_str[escape_index : escape_index + 2], escape_index + 2)

    # Single escape + control sequence
    control_result = _parse_control_sequence(input_str, escape_index, 1)
    if control_result == "pending":
        return "pending"
    if control_result is not None:
        return control_result

    return _parse_escaped_code_point(input_str, escape_index)


def _split_backspace_bytes(text: str, events: list[InputEvent]) -> None:
    """Split backspace bytes into individual events.

    When a user holds backspace, the terminal sends repeated bytes in a
    single stdin chunk. Without splitting, parseKeypress receives the
    multi-byte string and fails to recognize it.

    Parameters
    ----------
    text : str
        The raw text segment to split.
    events : list[InputEvent]
        List to append resulting events to (mutated in place).
    """
    segment_start = 0

    for index, ch in enumerate(text):
        if ch == "\x7f" or ch == "\x08":
            if index > segment_start:
                events.append(text[segment_start:index])
            events.append(ch)
            segment_start = index + 1

    if segment_start < len(text):
        events.append(text[segment_start:])


def _parse_keypresses(input_str: str) -> tuple[list[InputEvent], str]:
    """Parse input into events and pending buffer.

    Parameters
    ----------
    input_str : str
        Raw input string, potentially containing multiple keypresses
        and incomplete escape sequences.

    Returns
    -------
    tuple[list[InputEvent], str]
        A ``(events, pending)`` tuple where *events* is the list of
        completed input events and *pending* is any trailing incomplete
        data that needs more bytes.
    """
    events: list[InputEvent] = []
    index = 0

    while index < len(input_str):
        escape_index = input_str.find(ESCAPE, index)

        if escape_index == -1:
            _split_backspace_bytes(input_str[index:], events)
            return (events, "")

        if escape_index > index:
            _split_backspace_bytes(input_str[index:escape_index], events)

        result = _parse_escape_sequence(input_str, escape_index)

        if result == "pending":
            return (events, input_str[escape_index:])

        sequence, next_index = result

        if sequence == PASTE_START:
            after_start = next_index
            end_index = input_str.find(PASTE_END, after_start)
            if end_index == -1:
                return (events, input_str[escape_index:])

            events.append(PasteEvent(paste=input_str[after_start:end_index]))
            index = end_index + len(PASTE_END)
            continue

        events.append(sequence)
        index = next_index

    return (events, "")


class InputParser:
    """Stateful input parser matching Ink's createInputParser().

    Maintains a pending buffer for incomplete escape sequences.
    """

    def __init__(self) -> None:
        self._pending = ""

    def push(self, chunk: str) -> list[InputEvent]:
        """Parse a chunk of input, returning completed events.

        Parameters
        ----------
        chunk : str
            New raw input data to parse.

        Returns
        -------
        list[InputEvent]
            Completed input events extracted from the chunk.
        """
        events, self._pending = _parse_keypresses(self._pending + chunk)
        return events

    def has_pending_escape(self) -> bool:
        """Check if there's a pending escape sequence (not paste-related).

        Returns
        -------
        bool
            True if the pending buffer starts with an escape that is not
            a bracketed-paste prefix.
        """
        return (
            self._pending.startswith(ESCAPE)
            and not self._pending.startswith(PASTE_START)
            and self._pending != "\x1b[200"
        )

    def flush_pending_escape(self) -> str | None:
        """Flush and return pending escape sequence, if any.

        Returns
        -------
        str or None
            The pending escape string, or ``None`` if there is no
            pending escape.
        """
        if not self._pending.startswith(ESCAPE):
            return None
        pending = self._pending
        self._pending = ""
        return pending

    def reset(self) -> None:
        """Clear the pending buffer."""
        self._pending = ""


def create_input_parser() -> InputParser:
    """Factory function matching Ink's createInputParser().

    Returns
    -------
    InputParser
        A new stateful input parser instance.
    """
    return InputParser()
