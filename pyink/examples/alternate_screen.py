"""Port of Ink's examples/alternate-screen — Snake game on alternate screen."""
import random

from pyink import Box, Text, component, render
from pyink.hooks import use_app, use_effect, use_input, use_ref, use_state, use_window_size

BOARD_W = 20
BOARD_H = 15
TICK_MS = 150
HEAD = "\U0001f984"   # unicorn
BODY = "\u2728"       # sparkles
FOOD = "\U0001f308"   # rainbow
EMPTY = "  "
RAINBOW = ["red", "#FF7F00", "yellow", "green", "cyan", "blue", "magenta"]

OFFSETS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPPOSITES = {"up": "down", "down": "up", "left": "right", "right": "left"}

BORDER_H = "\u2500" * (BOARD_W * 2)
BORDER_TOP = f"\u250c{BORDER_H}\u2510"
BORDER_BOTTOM = f"\u2514{BORDER_H}\u2518"


def random_pos(exclude):
    while True:
        p = (random.randint(0, BOARD_W - 1), random.randint(0, BOARD_H - 1))
        if p not in {(s[0], s[1]) for s in exclude}:
            return p


def initial_state():
    snake = [(10, 7), (9, 7), (8, 7)]
    return {
        "snake": snake,
        "food": random_pos(snake),
        "score": 0,
        "game_over": False,
        "won": False,
        "frame": 0,
    }


def tick_game(state, direction):
    if state["game_over"]:
        return state

    hx, hy = state["snake"][0]
    dx, dy = OFFSETS[direction]
    nh = (hx + dx, hy + dy)

    if nh[0] < 0 or nh[0] >= BOARD_W or nh[1] < 0 or nh[1] >= BOARD_H:
        return {**state, "game_over": True}

    ate = nh == state["food"]
    check = state["snake"] if ate else state["snake"][:-1]
    if nh in check:
        return {**state, "game_over": True}

    new_snake = [nh] + state["snake"]
    if not ate:
        new_snake.pop()

    return {
        "snake": new_snake,
        "food": random_pos(new_snake) if ate else state["food"],
        "score": state["score"] + (1 if ate else 0),
        "game_over": False,
        "won": False,
        "frame": state["frame"] + 1,
    }


def build_board(snake, food):
    head_key = snake[0]
    snake_set = set(snake)
    rows = [BORDER_TOP]
    for y in range(BOARD_H):
        row = "\u2502"
        for x in range(BOARD_W):
            p = (x, y)
            if p == head_key:
                row += HEAD
            elif p in snake_set:
                row += BODY
            elif p == food:
                row += FOOD
            else:
                row += EMPTY
        row += "\u2502"
        rows.append(row)
    rows.append(BORDER_BOTTOM)
    return "\n".join(rows)


@component
def snake_game():
    app = use_app()
    use_window_size()  # trigger re-render on resize
    game, set_game = use_state(initial_state())
    direction_ref = use_ref("right")

    # Capture app for timer
    captured_app = app

    def effect():
        def do_tick():
            set_game(lambda g: tick_game(g, direction_ref.current))

        handle = captured_app._app.add_timer(TICK_MS / 1000, do_tick, repeating=True)

        def cleanup():
            captured_app._app.remove_timer(handle)

        return cleanup

    use_effect(effect, ())

    def handle_input(ch, key):
        if ch == "q":
            app.exit()
        if game["game_over"] and ch == "r":
            direction_ref.current = "right"
            set_game(initial_state())
            return
        if game["game_over"]:
            return

        cur = direction_ref.current
        if key.up_arrow and cur != "down":
            direction_ref.current = "up"
        elif key.down_arrow and cur != "up":
            direction_ref.current = "down"
        elif key.left_arrow and cur != "right":
            direction_ref.current = "left"
        elif key.right_arrow and cur != "left":
            direction_ref.current = "right"

    use_input(handle_input)

    title_color = RAINBOW[game["frame"] % len(RAINBOW)]
    board = build_board(game["snake"], game["food"])

    title_text = Text(
        "\U0001f984 Unicorn Snake \U0001f984", bold=True, color=title_color
    )
    score_text = Text(
        f"Score: {game['score']}", bold=True, color="yellow"
    )
    children = [
        Box(title_text, justify_content="center"),
        Box(score_text, justify_content="center", margin_top=1),
        Box(Text(board), margin_top=1),
    ]

    if game["game_over"]:
        children.append(
            Box(
                Text("Game Over! ", bold=True, color="red"),
                Text("r: restart | q: quit", dim_color=True),
                flex_direction="row",
                justify_content="center",
                margin_top=1,
            )
        )
    else:
        children.append(
            Box(
                Text(f"Arrow keys: move | Eat {FOOD} to grow | q: quit", dim_color=True),
                justify_content="center",
                margin_top=1,
            )
        )

    return Box(*children, flex_direction="column", padding_y=1)


if __name__ == "__main__":
    render(snake_game(), use_alt_screen=True)
