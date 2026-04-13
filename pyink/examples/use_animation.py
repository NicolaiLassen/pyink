"""Port of Ink's examples/use-animation/use-animation.tsx — animated unicorn."""
from pyink import Box, Text, component, render
from pyink.hooks import use_animation, use_input, use_state

RAINBOW = ["red", "yellow", "green", "cyan", "blue", "magenta"]
SPINNER_FRAMES = [
    "\u280b", "\u2819", "\u2839", "\u2838", "\u283c",
    "\u2834", "\u2826", "\u2827", "\u2807", "\u280f",
]
TRAIL_CHAR = "\u2501"
MAX_TRAIL = len(RAINBOW) * 3
TRACK_WIDTH = 44


@component
def animation_demo():
    paused, set_paused = use_state(False)

    fast = use_animation(interval=80, is_active=not paused)
    movement = use_animation(interval=50, is_active=not paused)
    use_animation(interval=400, is_active=not paused)  # slow timer for sparkles

    def handle_input(input_str, key):
        if input_str == " ":
            set_paused(lambda p: not p)

    use_input(handle_input)

    position = movement.frame % TRACK_WIDTH

    # Build track cells
    cells = []
    for col in range(TRACK_WIDTH):
        if col == position:
            cells.append(("\U0001f984", None))  # unicorn emoji
        else:
            dist_behind = (position - col + TRACK_WIDTH) % TRACK_WIDTH
            if 0 < dist_behind <= MAX_TRAIL:
                color_idx = len(RAINBOW) - 1 - (dist_behind - 1) // 3
                if 0 <= color_idx < len(RAINBOW):
                    cells.append((TRAIL_CHAR, RAINBOW[color_idx]))
                else:
                    cells.append((" ", None))
            else:
                cells.append((" ", None))

    # Build segments (group same-color cells)
    segments = []
    for text, color in cells:
        if segments and segments[-1][1] == color:
            segments[-1] = (segments[-1][0] + text, color)
        else:
            segments.append((text, color))

    track_parts = []
    for text, color in segments:
        if color:
            track_parts.append(Text(text, color=color))
        else:
            track_parts.append(Text(text))

    # Rainbow title
    title = "Unicorns are magical!"
    title_parts = []
    for i, ch in enumerate(title):
        color = RAINBOW[(fast.frame + i) % len(RAINBOW)]
        title_parts.append(Text(ch, color=color))

    spinner = SPINNER_FRAMES[fast.frame % len(SPINNER_FRAMES)]

    return Box(
        Box(*title_parts, flex_direction="row"),
        Text(""),
        Box(Text("  "), *track_parts, flex_direction="row"),
        Text(""),
        Text(f"  {spinner} Loading more unicorns...", color="cyan"),
        Text(""),
        Text(f'  Press <space> to {"resume" if paused else "pause"}', dim_color=True),
        flex_direction="column",
        padding=1,
    )


if __name__ == "__main__":
    render(animation_demo())
