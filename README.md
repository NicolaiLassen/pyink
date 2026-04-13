# PyInk

[![PyPI](https://img.shields.io/pypi/v/pyinklib)](https://pypi.org/project/pyinklib/)
[![Tests](https://github.com/NicolaiLassen/pyink/actions/workflows/test.yml/badge.svg)](https://github.com/NicolaiLassen/pyink/actions/workflows/test.yml)
[![Python](https://img.shields.io/pypi/pyversions/pyinklib)](https://pypi.org/project/pyinklib/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Build terminal UIs with Python using React-like components and flexbox layout.

A 1:1 Python port of [Ink](https://github.com/vadimdemedes/ink).

## Install

```
pip install pyinklib
```

Or with [uv](https://github.com/astral-sh/uv):

```
uv add pyinklib
```

## Usage

```python
from pyink import component, render, Box, Text
from pyink.hooks import use_state, use_input, use_app

@component
def counter():
    count, set_count = use_state(0)
    app = use_app()

    def handle_input(input_str, key):
        if key.up_arrow:
            set_count(lambda c: c + 1)
        elif key.down_arrow:
            set_count(lambda c: max(0, c - 1))
        elif input_str == "q":
            app.exit()

    use_input(handle_input)

    return Box(
        Text(f"Counter: {count}", color="cyan", bold=True),
        Box(
            Text("Up/Down to change, q to quit", dim_color=True),
            margin_top=1,
        ),
        flex_direction="column",
        padding=1,
        border_style="round",
    )

render(counter())
```

## Components

### `Box`

Flexbox container, like `<div>`. Supports all flexbox props:

```python
Box(
    *children,
    flex_direction="row",       # row | column | row-reverse | column-reverse
    justify_content="center",   # flex-start | center | flex-end | space-between | space-around | space-evenly
    align_items="stretch",      # flex-start | center | flex-end | stretch | baseline
    padding=1,                  # padding on all sides
    margin_top=1,               # individual margin
    border_style="round",       # single | double | round | bold | classic
    border_color="green",       # named color, hex, or rgb
    width=40,
    height=10,
    overflow="hidden",
)
```

### `Text`

Text with styling:

```python
Text("Hello", color="green", bold=True, italic=True, underline=True, strikethrough=True, dim_color=True, inverse=True)
```

### `Spacer`

Fills available space (like `flex: 1`):

```python
Box(Text("Left"), Spacer(), Text("Right"), flex_direction="row")
```

### `Static`

Render items once (for logs, completed tasks):

```python
Static(items=completed, render_item=lambda item, i: Text(f"Done: {item}"))
```

### `Transform`

Transform text output per line:

```python
Transform(Text("hello"), transform=lambda text, idx: text.upper())
```

## Hooks

| Hook | Description |
|------|-------------|
| `use_state(initial)` | Local state, returns `(value, setter)` |
| `use_effect(fn, deps)` | Side effects with cleanup |
| `use_input(handler)` | Keyboard input |
| `use_app()` | App lifecycle (`exit()`) |
| `use_focus()` | Tab-based focus |
| `use_focus_manager()` | Programmatic focus control |
| `use_animation(interval=100)` | Frame animation |
| `use_window_size()` | Terminal dimensions |
| `use_ref(initial)` | Mutable ref |
| `use_memo(fn, deps)` | Memoized value |
| `use_paste(handler)` | Paste events |
| `use_stdout()` / `use_stderr()` / `use_stdin()` | Stream access |
| `use_cursor()` | Cursor position |
| `use_box_metrics(ref)` | Element measurements |
| `use_is_screen_reader_enabled()` | Accessibility detection |

## Examples

```bash
pip install pyinklib

python -m pyink.examples.counter            # Auto-incrementing counter
python -m pyink.examples.use_input          # Move a face with arrow keys
python -m pyink.examples.chat               # Type messages + Enter
python -m pyink.examples.select_input       # Arrow key selection list
python -m pyink.examples.dashboard          # Animated multi-panel dashboard
python -m pyink.examples.use_animation      # Unicorn animation
python -m pyink.examples.borders            # All 8 border styles
python -m pyink.examples.border_backgrounds # Per-edge border colors
python -m pyink.examples.box_backgrounds    # Background colors
python -m pyink.examples.use_focus          # Tab focus navigation
python -m pyink.examples.use_focus_with_id  # Programmatic focus by ID
python -m pyink.examples.focus              # Focus with visual indicators
python -m pyink.examples.table              # Data table with columns
python -m pyink.examples.justify_content    # All justify-content modes
python -m pyink.examples.terminal_resize    # Live terminal size display
python -m pyink.examples.use_stdout         # Terminal dimensions
python -m pyink.examples.alternate_screen   # Snake game (alt screen)
python -m pyink.examples.hello              # Hello World
```

## Acknowledgements

PyInk is a Python port of [Ink](https://github.com/vadimdemedes/ink) by [Vadim Demedes](https://github.com/vadimdemedes). All credit for the architecture and design goes to the Ink team.

## License

MIT
