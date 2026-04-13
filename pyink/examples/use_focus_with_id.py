"""Port of Ink's examples/use-focus-with-id/use-focus-with-id.tsx."""
from pyink import component, render, Box, Text
from pyink.hooks import use_focus, use_input, use_focus_manager


@component
def item(id="", label="Item"):
    focus = use_focus(id=id)
    indicator = Text(" (focused)", color="green") if focus.is_focused else Text("")
    return Box(
        Text(f"{label}"),
        indicator,
        flex_direction="row",
    )


@component
def focus_with_id():
    fm = use_focus_manager()

    def handle_input(input_str, key):
        if input_str == "1":
            fm.focus("1")
        elif input_str == "2":
            fm.focus("2")
        elif input_str == "3":
            fm.focus("3")

    use_input(handle_input)

    return Box(
        Box(
            Text("Press Tab to focus next, Shift+Tab for previous."),
            margin_bottom=1,
        ),
        item(id="1", label="Press 1 to focus"),
        item(id="2", label="Press 2 to focus"),
        item(id="3", label="Press 3 to focus"),
        flex_direction="column",
        padding=1,
    )


if __name__ == "__main__":
    render(focus_with_id())
