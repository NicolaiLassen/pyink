#!/usr/bin/env python3
"""Smoke test — 1:1 copy of the orxhestra CLI rendering pipeline.

Run with: uv run python smoke_test_cli.py

Reproduces the exact orx REPL architecture with fake events, fake tools,
and fake async delays so pyink rendering can be debugged without
releasing to PyPI or needing a real LLM.

Uses the same event-driven model as orxhestra: a FakeRunner yields
Event objects, and fake_stream_response() consumes them exactly like
the real stream.py does.

Commands:
    /stream   — full pipeline: spinner → stream → tool call → approval → response
    /long     — stream a long response (50+ lines) to test overflow
    /tools    — multiple tool calls in parallel, some require approval
    /error    — simulate an error mid-stream
    /spin     — start spinner
    /stop     — stop spinner
    Ctrl+C    — interrupt running agent
    Ctrl+D    — exit
    any text  — echo + short fake response
"""
from __future__ import annotations

import asyncio
import re
import shutil
import threading
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import Enum

from pyink import Box, Text, component, render
from pyink.hooks import (
    use_animation,
    use_app,
    use_input,
    use_mouse,
    use_ref,
    use_state,
    use_window_size,
)

# ── Constants (mirrors orxhestra/cli/ink_app.py) ──

_ACCENT = "#6C8EBF"
_MUTED = "#6c6c6c"
_SEPARATOR = "\u2500" * (shutil.get_terminal_size().columns - 1)

SPINNER_FRAMES = ["\u2669", "\u266a", "\u266b", "\u266c", "\u266b", "\u266a"]

APPROVAL_OPTIONS = [
    "Yes",
    "Yes, allow all edits during this session",
    "No",
]
APPROVAL_RESULTS = ["y", "a", "n"]

# ── Rendering constants (mirrors orxhestra/cli/theme.py) ──

TOOL_TOP = "  \u250c"
TOOL_MID = "  \u2502"
TOOL_BOT = "  \u2514"
SEP = " \u00b7 "
TURN_DOT = "\u25cb"


# ═══════════════════════════════════════════════════════════════════
# Event model (mirrors orxhestra/events/event.py + models/part.py)
# ═══════════════════════════════════════════════════════════════════


class EventType(str, Enum):
    AGENT_MESSAGE = "agent_message"
    TOOL_RESPONSE = "tool_response"


@dataclass
class ToolCallPart:
    tool_call_id: str
    tool_name: str
    args: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class ToolResponsePart:
    tool_call_id: str
    tool_name: str
    result: str = ""
    error: str | None = None


@dataclass
class Event:
    """Minimal mirror of orxhestra's Event for the smoke test."""

    type: EventType
    partial: bool = False
    turn_complete: bool = True
    _text: str = ""
    _thinking: str = ""
    _tool_calls: list[ToolCallPart] = field(default_factory=list)
    _tool_responses: list[ToolResponsePart] = field(default_factory=list)
    agent_name: str | None = None
    metadata: dict = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_name: str = ""

    @property
    def text(self) -> str:
        return self._text

    @property
    def thinking(self) -> str:
        return self._thinking

    @property
    def tool_calls(self) -> list[ToolCallPart]:
        return self._tool_calls

    @property
    def has_tool_calls(self) -> bool:
        return len(self._tool_calls) > 0

    def is_final_response(self) -> bool:
        if self.partial:
            return False
        if self.type != EventType.AGENT_MESSAGE:
            return False
        if self.has_tool_calls:
            return False
        if self.metadata.get("react_step"):
            return False
        if self.metadata.get("error"):
            return False
        return bool(self._text)


# ═══════════════════════════════════════════════════════════════════
# Permission system (mirrors orxhestra/cli/approval.py)
# ═══════════════════════════════════════════════════════════════════

APPROVE_REQUIRED: frozenset[str] = frozenset({
    "write_file", "edit_file", "shell_exec", "mkdir",
})

_DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\brm\s+(-rf?|--recursive)", re.IGNORECASE),
    re.compile(r"\bgit\s+(push\s+--force|reset\s+--hard|clean\s+-f)", re.IGNORECASE),
    re.compile(r"\bsudo\b"),
]

_READ_TOOLS: frozenset[str] = frozenset({
    "read_file", "ls", "glob", "grep",
})
def _is_dangerous(tool_name: str, args: dict) -> bool:
    if tool_name == "shell_exec":
        cmd = args.get("command", "")
        for pattern in _DANGEROUS_PATTERNS:
            if pattern.search(cmd):
                return True
    return False


def _tool_arg_summary(tool_name: str, args: dict) -> str:
    """Build a concise one-line summary (mirrors render.py)."""
    if "path" in args:
        return args["path"]
    if "command" in args:
        cmd: str = args["command"]
        return cmd[:80] + ("..." if len(cmd) > 80 else "")
    if "pattern" in args:
        return args["pattern"]
    return ""


# ═══════════════════════════════════════════════════════════════════
# Fake tools — sync and async callables (like real LangChain tools)
# ═══════════════════════════════════════════════════════════════════


def tool_read_file(*, path: str) -> str:
    """Sync tool — reads a file (instant)."""
    time.sleep(0.1)
    return f"# {path}\nDATABASE_URL = 'sqlite:///db.sqlite3'\nDEBUG = True\n... (42 lines)"


def tool_grep(*, pattern: str, path: str = ".") -> str:
    """Sync tool — searches files (fast)."""
    time.sleep(0.2)
    return f"{path}/main.py:12: # {pattern}\n{path}/utils.py:34: # {pattern}"


async def tool_write_file(*, path: str, content: str) -> str:
    """Async tool — writes a file (moderate delay)."""
    await asyncio.sleep(0.3)
    n_lines = content.count("\n") + 1
    return f"wrote {n_lines} line(s) to {path}"


async def tool_edit_file(*, path: str, old: str, new: str) -> str:
    """Async tool — edits a file (moderate delay)."""
    await asyncio.sleep(0.2)
    return f"replaced '{old}' with '{new}' in {path}"


async def tool_shell_exec(*, command: str) -> str:
    """Async tool — runs a shell command (slow)."""
    await asyncio.sleep(1.5)
    if "pytest" in command:
        return "7 passed in 1.23s"
    if "curl" in command:
        raise RuntimeError("API rate limit exceeded (429). Please retry in 30 seconds.")
    return f"$ {command}\nOK"


def tool_mkdir(*, path: str) -> str:
    """Sync tool — creates a directory (instant)."""
    time.sleep(0.1)
    return f"created directory {path}"


# Tool registry — maps name → (callable, default_args, requires_approval)
TOOLS: dict[str, dict] = {
    "read_file": {
        "fn": tool_read_file,
        "args": {"path": "src/config.py"},
    },
    "grep": {
        "fn": tool_grep,
        "args": {"pattern": "TODO", "path": "src/"},
    },
    "write_file": {
        "fn": tool_write_file,
        "args": {"path": "src/main.py", "content": "print('hello world')"},
    },
    "edit_file": {
        "fn": tool_edit_file,
        "args": {"path": "src/utils.py", "old": "foo", "new": "bar"},
    },
    "shell_exec": {
        "fn": tool_shell_exec,
        "args": {"command": "pytest tests/ -x -q"},
    },
    "mkdir": {
        "fn": tool_mkdir,
        "args": {"path": "src/new_module"},
    },
}


async def _execute_tool(name: str, args: dict) -> str:
    """Execute a fake tool by name — handles both sync and async callables."""
    tool = TOOLS[name]
    fn = tool["fn"]
    if asyncio.iscoroutinefunction(fn):
        return await fn(**args)
    else:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: fn(**args))


_SHORT_TEXT = (
    "Sure! Here is a response that streams in **word by word** to "
    "test the rendering pipeline.\n\n"
    "Each word appears with a small delay to simulate real LLM token streaming. "
    "This includes `inline code`, **bold text**, and *italic* formatting.\n\n"
    "- First bullet point with some context\n"
    "- Second bullet with a `code reference`\n"
    "- Third bullet wrapping up the response"
)

_LONG_TEXT = """# Long Response Test

This is a **very long response** designed to test viewport overflow and scrolling behavior.

## Section 1: Code Example

```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

for i in range(20):
    print(f"fib({i}) = {fibonacci(i)}")
```

## Section 2: Bullet Points

- First item in the list with some additional context
- Second item that explains another important detail
- Third item with a reference to the code above
- Fourth item discussing edge cases and error handling
- Fifth item about testing and verification
- Sixth item covering deployment considerations
- Seventh item on monitoring and observability
- Eighth item regarding documentation updates

## Section 3: Table

| Feature | Status | Notes |
|---------|--------|-------|
| Streaming | Done | Works with throttling |
| Tool calls | Done | Approval flow works |
| Spinner | Done | Animation frames |
| History | Done | Capped at 200 items |
| Input | Done | Cursor + history |

## Section 4: More Text

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim
veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea
commodo consequat. Duis aute irure dolor in reprehenderit in voluptate
velit esse cillum dolore eu fugiat nulla pariatur.

Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia
deserunt mollit anim id est laborum. Sed ut perspiciatis unde omnis iste
natus error sit voluptatem accusantium doloremque laudantium.

## Section 5: Nested Lists

1. First top-level item
   - Sub-item A with details
   - Sub-item B with more details
2. Second top-level item
   - Sub-item C
   - Sub-item D
3. Third top-level item

That concludes this long test response. The input prompt should remain
visible at the bottom of the terminal throughout the streaming process."""


# ── Event helpers ──

def _text_event(word: str) -> Event:
    """Partial streaming text event (one word)."""
    return Event(type=EventType.AGENT_MESSAGE, partial=True, _text=word + " ")


def _tool_call_event(*tool_names: str, overrides: dict | None = None) -> Event:
    """Agent message with tool calls."""
    parts = []
    for i, name in enumerate(tool_names):
        tool = TOOLS.get(name, {"args": {}})
        args = (overrides or {}).get(name, tool["args"])
        parts.append(ToolCallPart(
            tool_call_id=f"tc_{name}_{i}",
            tool_name=name,
            args=args,
        ))
    return Event(type=EventType.AGENT_MESSAGE, partial=False, _tool_calls=parts)


def _tool_response_event(name: str, call_id: str, result: str) -> Event:
    """Tool response event."""
    return Event(
        type=EventType.TOOL_RESPONSE,
        tool_name=name,
        _tool_responses=[ToolResponsePart(
            tool_call_id=call_id, tool_name=name, result=result,
        )],
        _text=result,
    )


def _final_event(
    text: str = "", tokens: tuple[int, int] = (1200, 340),
) -> Event:
    """Non-partial final agent message."""
    return Event(
        type=EventType.AGENT_MESSAGE,
        partial=False,
        _text=text,
        prompt_tokens=tokens[0],
        completion_tokens=tokens[1],
    )


def _error_event(text: str) -> Event:
    return Event(
        type=EventType.AGENT_MESSAGE,
        metadata={"error": True},
        _text=text,
    )


# ═══════════════════════════════════════════════════════════════════
# FakeRunner — async iterator yielding events (mirrors Runner.astream)
#
# Each scenario is a coroutine that yields Event objects. Tool calls
# are followed by actual tool execution (sync or async) and the
# result is yielded as a TOOL_RESPONSE event.
# ═══════════════════════════════════════════════════════════════════


async def _stream_text(text: str, delay: float = 0.05) -> AsyncIterator[Event]:
    """Yield partial text events word-by-word."""
    for word in text.split():
        yield _text_event(word)
        await asyncio.sleep(delay)


async def _call_and_run_tools(
    *tool_names: str,
    overrides: dict | None = None,
) -> AsyncIterator[Event]:
    """Yield a tool call event, execute tools, yield responses."""
    event = _tool_call_event(*tool_names, overrides=overrides)
    yield event

    for tc in event.tool_calls:
        try:
            result = await _execute_tool(tc.tool_name, tc.args)
        except Exception as exc:
            result = f"Error: {exc}"
        yield _tool_response_event(tc.tool_name, tc.tool_call_id, result)


async def scenario_short() -> AsyncIterator[Event]:
    """Short response: think → stream → done."""
    await asyncio.sleep(0.8)  # LLM thinking
    async for e in _stream_text(_SHORT_TEXT):
        yield e
    yield _final_event()


async def scenario_long() -> AsyncIterator[Event]:
    """Long response to test viewport overflow."""
    await asyncio.sleep(0.5)
    async for e in _stream_text(_LONG_TEXT, delay=0.02):
        yield e
    yield _final_event()


async def scenario_stream() -> AsyncIterator[Event]:
    """Full pipeline: think → stream → write_file → shell_exec → final.

    Models a realistic LLM turn:
    1. Agent streams initial reasoning
    2. Calls write_file (async, requires approval)
    3. Calls shell_exec to run tests (async, requires approval)
    4. Streams final summary
    """
    await asyncio.sleep(0.8)

    # Phase 1: initial streaming response
    async for e in _stream_text(
        "I'll help you with that. Let me **write the file** for you.\n\n"
        "Here's what I'm going to do:\n"
        "1. Create `src/main.py` with the hello world code\n"
        "2. Run `pytest` to verify everything works",
    ):
        yield e

    # Phase 2: write_file tool call → actual async execution
    async for e in _call_and_run_tools("write_file"):
        yield e

    # Phase 3: shell_exec to run tests → actual async execution
    async for e in _call_and_run_tools("shell_exec"):
        yield e

    # Phase 4: final response
    async for e in _stream_text(
        "Done! I've written the file and all **tests pass**.\n\n"
        "```python\n# src/main.py\nprint('hello world')\n```\n\n"
        "The file is ready to run with `python src/main.py`.",
    ):
        yield e
    yield _final_event()


async def scenario_tools() -> AsyncIterator[Event]:
    """Multiple tool calls — batch of 4 tools at once.

    Models a realistic multi-tool turn:
    1. Agent streams plan
    2. Calls read_file (sync) + grep (sync) + write_file (async) + edit_file (async)
    3. All executed, responses returned one by one
    4. Agent streams final summary
    """
    await asyncio.sleep(0.6)

    async for e in _stream_text(
        "I'll read the config, search for TODOs, and update the code.",
    ):
        yield e

    # Batch: 4 tool calls at once (mix of sync and async)
    async for e in _call_and_run_tools(
        "read_file", "grep", "write_file", "edit_file",
    ):
        yield e

    async for e in _stream_text(
        "All done. I found 3 TODOs and updated the relevant files.",
    ):
        yield e
    yield _final_event(tokens=(2400, 680))


async def scenario_error() -> AsyncIterator[Event]:
    """Error mid-stream — tool execution raises an exception.

    Models: agent streams, calls curl via shell_exec, tool raises.
    """
    await asyncio.sleep(0.6)

    async for e in _stream_text("Let me fetch that data for you..."):
        yield e

    # shell_exec with curl — tool_shell_exec raises RuntimeError
    async for e in _call_and_run_tools(
        "shell_exec",
        overrides={"shell_exec": {"command": "curl -s https://api.example.com/data"}},
    ):
        yield e

    # The LLM sees the error and reports it
    yield _error_event("API rate limit exceeded (429). Please retry in 30 seconds.")


SCENARIOS: dict[str, Callable] = {
    "short": scenario_short,
    "long": scenario_long,
    "stream": scenario_stream,
    "tools": scenario_tools,
    "error": scenario_error,
}


# ═══════════════════════════════════════════════════════════════════
# Writer bridge (mirrors orxhestra/cli/writer.py)
# ═══════════════════════════════════════════════════════════════════


def _rich_to_ansi(text: str, width: int = 100) -> str:
    """Render text as Rich Markdown to ANSI string."""
    try:
        from io import StringIO

        from rich.console import Console
        from rich.markdown import Markdown

        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=width, no_color=False)
        console.print(Markdown(text))
        raw = buf.getvalue().rstrip("\n")
        return "\n".join(line.rstrip() for line in raw.split("\n"))
    except ImportError:
        return text


class _SpinnerHandle:
    def __init__(self, set_spinner_text: Callable, set_phase: Callable) -> None:
        self._set_spinner_text = set_spinner_text
        self._set_phase = set_phase

    def update_text(self, text: str) -> None:
        self._set_spinner_text(text)

    def stop(self) -> None:
        self._set_phase("idle")
        self._set_spinner_text("")


class _LiveHandle:
    """Live region — throttled to ~12 FPS (same as orxhestra)."""

    _MIN_INTERVAL = 1.0 / 12

    def __init__(
        self,
        set_stream: Callable,
        set_phase: Callable,
        set_history: Callable,
    ) -> None:
        self._set_stream = set_stream
        self._set_phase = set_phase
        self._set_history = set_history
        self._last_text: str = ""
        self._last_update = 0.0

    def update(self, text: str) -> None:
        self._last_text = text
        now = time.monotonic()
        if now - self._last_update < self._MIN_INTERVAL:
            return
        self._last_update = now
        self._set_stream(_rich_to_ansi(text))

    def stop(self, *, keep: bool = True) -> None:
        self._set_stream("")
        self._set_phase("idle")
        if keep and self._last_text:
            final = _rich_to_ansi(self._last_text)
            self._set_history(lambda h: [*h, {"type": "response", "ansi": final}])


class FakeWriter:
    """1:1 mirror of orxhestra's InkWriter (without Rich dependency)."""

    def __init__(
        self,
        set_history: Callable,
        set_spinner_text: Callable,
        set_stream: Callable,
        set_phase: Callable,
        approval_callback: Callable | None = None,
    ) -> None:
        self._set_history = set_history
        self._set_spinner_text = set_spinner_text
        self._set_stream = set_stream
        self._set_phase = set_phase
        self._approval_callback = approval_callback

    def print_rich(self, text: str = "", *, item_type: str | None = None) -> None:
        if text:
            if item_type is None:
                item_type = "tool_done" if "\u2514" in text else "rich"
            self._set_history(lambda h: [*h, {"type": item_type, "ansi": text}])

    def start_spinner(self, text: str) -> _SpinnerHandle:
        self._set_phase("spinning")
        self._set_spinner_text(text)
        return _SpinnerHandle(self._set_spinner_text, self._set_phase)

    def stop_spinner(self, handle: _SpinnerHandle) -> None:
        handle.stop()

    def start_live(self) -> _LiveHandle:
        self._set_phase("streaming")
        self._set_stream("")
        return _LiveHandle(self._set_stream, self._set_phase, self._set_history)

    def stop_live(self, handle: _LiveHandle, *, keep: bool = True) -> None:
        handle.stop(keep=keep)

    async def prompt_input(self, label: str) -> str:
        if self._approval_callback:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._approval_callback, label)
        return "y"


# ═══════════════════════════════════════════════════════════════════
# Rendering helpers (mirrors orxhestra/cli/render.py)
# ═══════════════════════════════════════════════════════════════════


def render_tool_call(event: Event, writer: FakeWriter) -> None:
    """Render tool calls with boxed format (mirrors render.py)."""
    read_tools: list[str] = []
    other_tools: list[tuple[str, str]] = []

    for tc in event.tool_calls:
        if tc.metadata.get("interactive"):
            continue
        summary = _tool_arg_summary(tc.tool_name, tc.args)
        if tc.tool_name in _READ_TOOLS and len(event.tool_calls) > 1:
            read_tools.append(
                f"{tc.tool_name}({summary})" if summary else tc.tool_name,
            )
        else:
            other_tools.append((tc.tool_name, summary))

    if read_tools:
        collapsed = ", ".join(read_tools[:4])
        if len(read_tools) > 4:
            collapsed += f" +{len(read_tools) - 4} more"
        writer.print_rich(f"{TOOL_TOP} {collapsed}")

    for name, summary in other_tools:
        writer.print_rich(f"\x1b[1m{TOOL_TOP} {name}\x1b[0m")
        if summary:
            writer.print_rich(f"{TOOL_MID} {summary}")


def render_tool_response(
    event: Event,
    writer: FakeWriter,
    *,
    elapsed: float | None = None,
    is_last: bool = False,
) -> None:
    """Render a tool response (mirrors render.py)."""
    text = (event.text or "")[:500]
    elapsed_str = ""
    if elapsed is not None and elapsed >= 0.1:
        elapsed_str = f" ({elapsed:.1f}s)"
    tag = "tool_done_last" if is_last else "tool_done"
    if text:
        lines = text.splitlines()
        first_line = lines[0][:200]
        if len(lines) > 1:
            first_line += f"  ({len(lines)} lines)"
        writer.print_rich(
            f"\x1b[2m{TOOL_BOT} {first_line}{elapsed_str}\x1b[0m",
            item_type=tag,
        )
    else:
        writer.print_rich(
            f"\x1b[2m{TOOL_BOT} done{elapsed_str}\x1b[0m",
            item_type=tag,
        )


def render_turn_summary(
    elapsed: float,
    writer: FakeWriter,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Print a concise summary line (mirrors render.py)."""
    ts = time.strftime("%H:%M")
    parts = [f"{elapsed:.1f}s"]
    total = prompt_tokens + completion_tokens
    if total > 0:
        parts.append(
            f"{total:,} tokens"
            f" ({prompt_tokens:,}\u2191 {completion_tokens:,}\u2193)"
        )
    summary = SEP.join(parts)
    writer.print_rich(
        f"\x1b[2m  {TURN_DOT} {summary}  {ts}\x1b[0m",
        item_type="plain",
    )


# ═══════════════════════════════════════════════════════════════════
# Stream response (mirrors orxhestra/cli/stream.py)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class _StreamState:
    """Mutable state tracked during a single streaming turn."""

    buffer: str = ""
    in_stream: bool = False
    thinking_active: bool = False
    live_handle: _LiveHandle | None = None
    spinner: _SpinnerHandle | None = None
    tool_start: float = 0.0
    turn_start: float = field(default_factory=time.monotonic)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    pending_tool_ids: set[str] = field(default_factory=set)

    def stop_spinner(self, writer: FakeWriter) -> None:
        if self.spinner is not None:
            writer.stop_spinner(self.spinner)
            self.spinner = None

    def end_stream(self, writer: FakeWriter) -> None:
        if self.in_stream:
            if self.live_handle is not None:
                if self.buffer:
                    self.live_handle.update(self.buffer)
                writer.stop_live(self.live_handle, keep=True)
                self.live_handle = None
            elif self.buffer:
                writer.print_rich(self.buffer)
            self.in_stream = False
            self.buffer = ""


async def _prompt_approval(
    tool_name: str,
    args: dict,
    writer: FakeWriter,
    auto_approve: bool,
) -> tuple[bool, bool]:
    """Prompt for tool approval (mirrors stream.py prompt_approval)."""
    if auto_approve:
        return True, auto_approve
    if tool_name not in APPROVE_REQUIRED:
        return True, auto_approve

    arg_summary = ""
    if "command" in args:
        arg_summary = f"\n  {args['command']}"
    elif "path" in args:
        arg_summary = f"\n  {args['path']}"
    label = f"  {tool_name}{arg_summary}"

    if _is_dangerous(tool_name, args):
        label += "\n  \x1b[31m\u26a0 destructive command\x1b[0m"

    response = (await writer.prompt_input(label)).strip().lower()
    if response in ("a", "all"):
        return True, True
    return response in ("y", "yes"), auto_approve


async def fake_stream_response(
    writer: FakeWriter,
    mode: str = "short",
    auto_approve: bool = False,
) -> bool:
    """Consume events exactly like orxhestra/cli/stream.py does.

    This is a 1:1 mirror of the real stream_response function:
    same state machine, same event checks, same rendering calls.
    The scenario coroutine yields Event objects (including executing
    real sync/async tool functions), and this loop processes them.
    """
    scenario_fn = SCENARIOS.get(mode, scenario_short)
    s = _StreamState()

    # Start spinner (mirrors stream.py line 242)
    s.spinner = writer.start_spinner("Thinking...")

    async for event in scenario_fn():
        # Accumulate token usage
        s.prompt_tokens += event.prompt_tokens
        s.completion_tokens += event.completion_tokens

        # ── Thinking (mirrors stream.py lines 252-263) ──
        if event.partial and event.type == EventType.AGENT_MESSAGE and event.thinking:
            s.stop_spinner(writer)
            if not s.thinking_active:
                s.thinking_active = True
                writer.print_rich("\x1b[2m  thinking ...\x1b[0m")
            writer.print_rich(f"\x1b[2m{event.thinking}\x1b[0m")
            continue

        # ── Streaming text (mirrors stream.py lines 265-277) ──
        if event.partial and event.type == EventType.AGENT_MESSAGE and event.text:
            s.stop_spinner(writer)
            if s.thinking_active:
                writer.print_rich()
                s.thinking_active = False
            s.buffer += event.text
            if not s.in_stream:
                s.in_stream = True
                s.live_handle = writer.start_live()
                s.live_handle.update(s.buffer)
            else:
                s.live_handle.update(s.buffer)
            continue

        # ── Tool calls (mirrors stream.py lines 279-313) ──
        if event.has_tool_calls:
            s.stop_spinner(writer)
            s.end_stream(writer)

            for tc in event.tool_calls:
                s.pending_tool_ids.add(tc.tool_call_id)

            render_tool_call(event, writer)

            # Approval for destructive tools
            for tc in event.tool_calls:
                if tc.tool_name in APPROVE_REQUIRED and not auto_approve:
                    approved, auto_approve = await _prompt_approval(
                        tc.tool_name, tc.args, writer, auto_approve,
                    )
                    if not approved:
                        writer.print_rich("\x1b[31m  Denied.\x1b[0m")

            s.tool_start = time.monotonic()
            n_tools = len(event.tool_calls)
            if n_tools > 1:
                tool_label = f"{n_tools} tools"
            else:
                tool_label = event.tool_calls[-1].tool_name
            s.spinner = writer.start_spinner(f"Running {tool_label}...")
            continue

        # ── Tool response (mirrors stream.py lines 315-342) ──
        if event.type == EventType.TOOL_RESPONSE:
            s.stop_spinner(writer)
            tool_call_id = ""
            if event._tool_responses:
                tool_call_id = event._tool_responses[0].tool_call_id
            s.pending_tool_ids.discard(tool_call_id)

            is_last = len(s.pending_tool_ids) == 0
            elapsed: float | None = None
            if is_last and s.tool_start > 0:
                elapsed = time.monotonic() - s.tool_start
            if is_last:
                render_tool_response(event, writer, elapsed=elapsed, is_last=True)

            if is_last and s.spinner is None:
                s.spinner = writer.start_spinner("Thinking...")
            continue

        # ── Final response (mirrors stream.py lines 344-357) ──
        if event.is_final_response():
            s.stop_spinner(writer)
            was_streaming = s.in_stream
            s.end_stream(writer)
            if not was_streaming and event.text:
                writer.print_rich(event.text)
            continue

        # ── Error (mirrors stream.py lines 370-374) ──
        if event.metadata.get("error") and event.text:
            s.stop_spinner(writer)
            s.end_stream(writer)
            writer.print_rich(
                f"\x1b[31mError: {event.text}\x1b[0m", item_type="plain",
            )
            continue

    # Turn summary (mirrors stream.py lines 385-393)
    s.stop_spinner(writer)
    if s.in_stream:
        s.end_stream(writer)

    turn_elapsed = time.monotonic() - s.turn_start
    render_turn_summary(
        turn_elapsed,
        writer,
        prompt_tokens=s.prompt_tokens or 1200,
        completion_tokens=s.completion_tokens or 340,
    )

    return auto_approve


# ═══════════════════════════════════════════════════════════════════
# History item renderer (mirrors orxhestra/cli/ink_app.py)
# ═══════════════════════════════════════════════════════════════════


def _history_item(item: dict, _index: int = 0):
    t = item.get("type", "")
    ansi = item.get("ansi", "")
    if t == "user":
        return Box(
            Text("\u276f ", color=_ACCENT),
            Text(item["text"], bold=True),
            flex_direction="row",
            margin_top=1,
            margin_bottom=1,
        )
    if t == "response":
        return Text(f"\x1b[38;2;108;142;191m\u25cf\x1b[0m {ansi}")
    if t == "rich":
        return Text(ansi)
    if t in ("tool_done", "tool_done_last"):
        return Text(ansi)
    if t == "plain":
        return Text(ansi, color=item.get("color"), dim=item.get("dim", False))
    if t == "separator":
        return Text(_SEPARATOR, color=_MUTED, dim=True)
    return Text(str(item))


# ═══════════════════════════════════════════════════════════════════
# Selector component (mirrors orxhestra/cli/ink_app.py)
# ═══════════════════════════════════════════════════════════════════


@component
def _selector_view(prompt_text, options, selected_idx, show_type_option):
    rows = [Text(prompt_text, bold=True, color="#E5C07B")]
    rows.append(Text(""))
    for i, opt in enumerate(options):
        is_sel = i == selected_idx
        prefix = "\u276f" if is_sel else " "
        rows.append(Text(
            f"  {prefix} {i + 1}. {opt}",
            color="white" if is_sel else _MUTED,
            bold=is_sel,
        ))
    if show_type_option:
        is_sel = selected_idx == len(options)
        prefix = "\u276f" if is_sel else " "
        rows.append(Text(
            f"  {prefix} {len(options) + 1}. Type something...",
            color="white" if is_sel else _MUTED,
            bold=is_sel,
        ))
    rows.append(Text(""))
    rows.append(Text("  Esc to cancel", color=_MUTED, dim=True))
    return Box(*rows, flex_direction="column", margin_top=1)


# ═══════════════════════════════════════════════════════════════════
# Main REPL component (mirrors orxhestra/cli/ink_app.py)
# ═══════════════════════════════════════════════════════════════════


@component
def smoke_repl(banner_ansi="", help_text=""):
    win = use_window_size()
    use_mouse()  # Capture scroll events so terminal doesn't shift display

    history, set_history = use_state([])
    scroll_offset, set_scroll_offset = use_state(0)  # items from bottom
    buf, set_buf = use_state("")
    cursor, set_cursor = use_state(0)
    phase, set_phase = use_state("idle")
    spinner_text, set_spinner_text = use_state("")
    stream_buf, set_stream = use_state("")

    # Selector state (approval prompts)
    sel_active, set_sel_active = use_state(False)
    sel_prompt, set_sel_prompt = use_state("")
    sel_options, set_sel_options = use_state([])
    sel_idx, set_sel_idx = use_state(0)
    sel_mode = use_ref("approval")
    sel_show_type = use_ref(False)
    sel_event = use_ref(None)
    sel_result = use_ref(None)
    freetext, set_freetext = use_state(False)

    cmd_hist = use_ref([])
    hist_idx = use_ref(-1)
    running = use_ref(False)
    writer_ref = use_ref(None)
    auto_approve_ref = use_ref(False)

    app = use_app()

    if writer_ref.current is None:
        selector_cb = _make_selector_callback(
            set_sel_active, set_sel_prompt, set_sel_options,
            set_sel_idx, sel_mode, sel_show_type,
            sel_event, sel_result,
        )
        writer_ref.current = FakeWriter(
            set_history=set_history,
            set_spinner_text=set_spinner_text,
            set_stream=set_stream,
            set_phase=set_phase,
            approval_callback=selector_cb,
        )

    # Spinner animation
    anim = use_animation(interval=200, is_active=(phase == "spinning"))
    fi = anim.frame % len(SPINNER_FRAMES)
    frame_char = SPINNER_FRAMES[fi]

    total_opts = len(sel_options) + (1 if sel_show_type.current else 0)

    def on_key(ch, key):
        # ── Free-text input mode ──
        if freetext:
            if key.return_key:
                answer = buf.strip()
                if answer:
                    sel_result.current = answer
                    set_freetext(False)
                    set_buf("")
                    set_cursor(0)
                    if sel_event.current:
                        sel_event.current.set()
                return
            if key.escape:
                set_freetext(False)
                return

        # ── Selector mode ──
        elif sel_active:
            if key.up_arrow:
                set_sel_idx(lambda i: max(0, i - 1))
                return
            if key.down_arrow:
                set_sel_idx(lambda i: min(total_opts - 1, i + 1))
                return
            if key.return_key:
                idx = sel_idx
                if sel_mode.current == "approval":
                    sel_result.current = APPROVAL_RESULTS[
                        min(idx, len(APPROVAL_RESULTS) - 1)
                    ]
                elif idx < len(sel_options):
                    sel_result.current = sel_options[idx]
                else:
                    set_sel_active(False)
                    set_freetext(True)
                    set_buf("")
                    set_cursor(0)
                    return
                set_sel_active(False)
                if sel_event.current:
                    sel_event.current.set()
                return
            if key.escape:
                sel_result.current = (
                    "n" if sel_mode.current == "approval" else ""
                )
                set_sel_active(False)
                if sel_event.current:
                    sel_event.current.set()
                return
            return

        # ── Normal mode ──

        # Scroll: mouse wheel + PgUp/PgDn
        if key.scroll_up or key.page_up:
            step = 1 if key.scroll_up else 10
            set_scroll_offset(lambda o: o + step)
            return
        if key.scroll_down or key.page_down:
            step = 1 if key.scroll_down else 10
            set_scroll_offset(lambda o: max(0, o - step))
            return

        # Any typing resets scroll to bottom (re-pin)
        if scroll_offset > 0:
            if key.return_key or (ch and not key.ctrl and not key.meta):
                set_scroll_offset(0)

        if key.ctrl and ch == "d":
            app.exit()
            return

        if key.ctrl and ch == "c":
            if running.current:
                running.current = False
                set_phase("idle")
                set_spinner_text("")
                set_stream("")
                set_history(lambda h: [
                    *h,
                    {"type": "plain", "ansi": "  Interrupted.", "color": _MUTED},
                ])
            return

        if key.return_key:
            msg = buf.strip()
            if not msg:
                return
            set_buf("")
            set_cursor(0)
            cmd_hist.current = [*cmd_hist.current, msg]
            hist_idx.current = -1

            if msg == "/spin":
                set_phase("spinning")
                set_spinner_text("Thinking...")
            elif msg == "/stop":
                set_phase("idle")
                set_spinner_text("")
            elif msg.startswith("/"):
                mode_map = {
                    "/stream": "stream",
                    "/long": "long",
                    "/tools": "tools",
                    "/error": "error",
                }
                mode = mode_map.get(msg.split()[0], "short")
                if not running.current:
                    _dispatch_agent(
                        msg, mode, writer_ref.current,
                        set_history, set_phase, running,
                        auto_approve_ref,
                    )
                return
            elif not running.current:
                set_history(lambda h: [*h, {"type": "user", "text": msg}])
                _dispatch_agent(
                    msg, "short", writer_ref.current,
                    set_history, set_phase, running,
                    auto_approve_ref,
                )
            else:
                set_history(lambda h: [
                    *h,
                    {"type": "plain", "ansi": "  Agent is still running.",
                     "color": _MUTED},
                ])
            return

        if key.up_arrow:
            h = cmd_hist.current
            if h:
                i = hist_idx.current
                i = len(h) - 1 if i == -1 else max(0, i - 1)
                hist_idx.current = i
                set_buf(h[i])
                set_cursor(len(h[i]))
            return
        if key.down_arrow:
            i = hist_idx.current
            h = cmd_hist.current
            if i >= 0:
                if i < len(h) - 1:
                    hist_idx.current = i + 1
                    set_buf(h[i + 1])
                    set_cursor(len(h[i + 1]))
                else:
                    hist_idx.current = -1
                    set_buf("")
                    set_cursor(0)
            return

        if key.left_arrow:
            set_cursor(lambda c: max(0, c - 1))
            return
        if key.right_arrow:
            set_cursor(lambda c: min(len(buf), c + 1))
            return

        if key.backspace or key.delete:
            if cursor > 0:
                pos = cursor
                set_buf(lambda t: t[:pos - 1] + t[pos:])
                set_cursor(lambda c: max(0, c - 1))
            return

        if ch and not key.ctrl and not key.meta and not key.escape:
            text = ch
            set_cursor(lambda c: c + len(text))
            set_buf(
                lambda t: t + text if cursor >= len(t)
                else t[:cursor] + text + t[cursor:]
            )

    use_input(on_key)

    # ── Build component tree ──
    # Fixed chrome: banner (3 lines) + input (3 lines) = 6 lines.
    # Messages area gets the rest. Show only last N items that fit
    # (like open-claude-code's conversation.slice(-maxMessages)).
    banner_lines = 3  # banner + help + separator
    input_lines = 3   # separator + prompt + separator
    available = max(1, win.rows - banner_lines - input_lines)
    # Each message is ~3 lines on average (user msg + response + summary)
    max_items = max(1, available)

    children = []

    # Banner — fixed at top
    if banner_ansi:
        children.append(Text(banner_ansi))
    if help_text:
        children.append(Text(help_text, color=_MUTED, dim=True))
    children.append(Text(_SEPARATOR, color=_MUTED, dim=True))

    # Build all items (history + ephemeral spinner/stream/selector)
    all_items = [
        _history_item(item, i)
        for i, item in enumerate(history[-200:] if len(history) > 200 else history)
    ]

    if phase == "spinning" and spinner_text:
        all_items.append(
            Text(f"{frame_char} {spinner_text}", color=_ACCENT),
        )

    if phase == "streaming" and stream_buf:
        all_items.append(Box(
            Text("\u25cf ", color=_ACCENT),
            Text(stream_buf),
            flex_direction="row",
        ))

    if sel_active:
        all_items.append(_selector_view(
            prompt_text=sel_prompt,
            options=sel_options,
            selected_idx=sel_idx,
            show_type_option=sel_show_type.current,
        ))

    # Visible window: scroll_offset=0 shows latest items (pinned to bottom).
    # scroll_offset>0 shifts the window back into history.
    n = len(all_items)
    clamped_offset = min(scroll_offset, max(0, n - 1))
    end = n - clamped_offset
    start = max(0, end - max_items)
    visible_items = all_items[start:end] if end > start else []

    # Messages container: FIXED height (not flex_grow) so yoga doesn't
    # let the inner content push siblings off-screen. Inner Box has
    # flex_shrink=0 so items keep their measured height (no overlap).
    # overflow=hidden clips at the boundary. Same pattern as openClaude.
    children.append(
        Box(
            Box(*visible_items, flex_direction="column", flex_shrink=0),
            flex_direction="column",
            height=available,
            overflow="hidden",
        ),
    )

    # Input area — fixed at bottom
    before = buf[:cursor]
    char_at = buf[cursor] if cursor < len(buf) else " "
    after = buf[cursor + 1:] if cursor < len(buf) else ""
    prompt_label = "?" if freetext else "\u276f"

    input_children = [
        Text(_SEPARATOR, color=_MUTED, dim=True),
        Box(
            Text(f"  {prompt_label} ", color=_ACCENT, bold=True),
            Text(before, bold=True),
            Text(char_at, bold=True, inverse=True),
            Text(after, bold=True),
            flex_direction="row",
        ),
        Text(_SEPARATOR, color=_MUTED, dim=True),
    ]
    children.append(Box(*input_children, flex_direction="column"))

    # Root Box fills terminal height so flex_grow works correctly
    return Box(*children, flex_direction="column", height=win.rows)


# ═══════════════════════════════════════════════════════════════════
# Selector callback (mirrors orxhestra/cli/ink_app.py)
# ═══════════════════════════════════════════════════════════════════


def _make_selector_callback(
    set_sel_active, set_sel_prompt, set_sel_options,
    set_sel_idx, sel_mode, sel_show_type,
    sel_event, sel_result,
):
    def request_input(label: str) -> str:
        evt = threading.Event()
        sel_event.current = evt
        sel_result.current = ""
        set_sel_idx(0)

        sel_mode.current = "approval"
        sel_show_type.current = False
        set_sel_prompt(label)
        set_sel_options(APPROVAL_OPTIONS)

        set_sel_active(True)
        evt.wait()
        return sel_result.current or ""

    return request_input


# ═══════════════════════════════════════════════════════════════════
# Agent dispatch (mirrors orxhestra/cli/ink_app.py)
# ═══════════════════════════════════════════════════════════════════


def _dispatch_agent(
    message, mode, writer, set_history, set_phase, running_ref,
    auto_approve_ref,
):
    if message.startswith("/"):
        set_history(lambda h: [
            *h, {"type": "plain", "ansi": f"  {message}", "color": _MUTED},
        ])
    running_ref.current = True

    def run():
        loop = asyncio.new_event_loop()
        try:
            new_auto = loop.run_until_complete(
                fake_stream_response(writer, mode, auto_approve_ref.current)
            )
            auto_approve_ref.current = new_auto
        except Exception as exc:
            err_msg = str(exc)
            if len(err_msg) > 200:
                err_msg = err_msg[:200] + "..."
            set_history(lambda h: [
                *h, {"type": "plain", "ansi": f"Error: {err_msg}", "color": "red"},
            ])
        finally:
            running_ref.current = False
            set_phase("idle")
        for task in asyncio.all_tasks(loop):
            task.cancel()
        try:
            pending = asyncio.all_tasks(loop)
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()

    threading.Thread(target=run, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════


def main():
    banner = "\x1b[1;34msmoke-test\x1b[0m v1.1.11 \u00b7 pyink rendering pipeline"
    help_text = (
        "  /stream /long /tools /error \u2014 test flows \u00b7 "
        "Ctrl+C interrupt \u00b7 Ctrl+D exit"
    )

    vnode = smoke_repl(
        banner_ansi=banner,
        help_text=help_text,
    )
    render(vnode, exit_on_ctrl_c=False, max_fps=30, use_alt_screen=True)


if __name__ == "__main__":
    main()
