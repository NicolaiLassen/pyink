"""Port of Ink's examples/select-input/select-input.tsx — arrow key selection."""
from pyink import component, render, Box, Text
from pyink.hooks import use_state, use_input, use_app

ITEMS = ["Red", "Green", "Blue", "Yellow", "Magenta", "Cyan"]


@component
def select_input():
    selected, set_selected = use_state(0)
    app = use_app()

    def handle_input(input_str, key):
        if key.up_arrow:
            set_selected(lambda i: (i - 1) % len(ITEMS))
        elif key.down_arrow:
            set_selected(lambda i: (i + 1) % len(ITEMS))
        elif input_str == "q":
            app.exit()

    use_input(handle_input)

    rows = [Text("Select a color (up/down, q to quit):")]
    for i, item in enumerate(ITEMS):
        is_selected = i == selected
        label = f"> {item}" if is_selected else f"  {item}"
        rows.append(Text(label, color="blue" if is_selected else None))

    return Box(*rows, flex_direction="column")


if __name__ == "__main__":
    render(select_input())
