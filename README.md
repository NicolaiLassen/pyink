# PyInk

> Build terminal UIs with Python using React-like components and flexbox layout.

A 1:1 Python port of [Ink](https://github.com/vadimdemedes/ink).

## Install

```
pip install pyink
```

Or with [uv](https://github.com/astral-sh/uv):

```
uv add pyink
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
uv run python -m pyink.examples.counter
uv run python -m pyink.examples.chat
uv run python -m pyink.examples.dashboard
uv run python -m pyink.examples.select_input
uv run python -m pyink.examples.use_animation
uv run python -m pyink.examples.borders
uv run python -m pyink.examples.alternate_screen
uv run python -m pyink.examples.use_focus
uv run python -m pyink.examples.table
uv run python -m pyink.examples.justify_content
uv run python -m pyink.examples.terminal_resize
```

## Acknowledgements

PyInk is a Python port of [Ink](https://github.com/vadimdemedes/ink) by [Vadim Demedes](https://github.com/vadimdemedes). All credit for the architecture and design goes to the Ink team.
