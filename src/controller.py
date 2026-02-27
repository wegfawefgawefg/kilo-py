from __future__ import annotations

from typing import Callable

from actions import (
    delete_char,
    insert_char,
    insert_newline,
    insert_tab,
    move_down,
    move_end,
    move_home,
    move_left,
    move_right,
    move_up,
    page_down,
    page_up,
)
from io_ops import open_file, resize, save_file, set_status
from render import refresh_screen
from search import find
from model import (
    ARROW_DOWN,
    ARROW_LEFT,
    ARROW_RIGHT,
    ARROW_UP,
    BACKSPACE,
    CTRL_A,
    CTRL_E,
    CTRL_F,
    CTRL_H,
    CTRL_L,
    CTRL_Q,
    CTRL_S,
    DEL_KEY,
    END_KEY,
    ENTER,
    ESC,
    HOME_KEY,
    KILO_QUIT_TIMES,
    PAGE_DOWN,
    PAGE_UP,
    State,
    TAB,
)
from terminal import read_key


def confirm_or_quit(state: State) -> bool:
    if state.dirty and state.quit_times > 0:
        set_status(
            state,
            f"WARNING!!! Unsaved changes. Press Ctrl-Q {state.quit_times} more times to quit.",
        )
        state.quit_times -= 1
        return False
    return True


def process_keypress(state: State) -> bool:
    c = read_key(state.stdin_fd)

    if c == CTRL_Q:
        return confirm_or_quit(state)
    if c in IGNORED_KEYS:
        state.quit_times = KILO_QUIT_TIMES
        return False

    handler = KEY_HANDLERS.get(c)
    if handler is not None:
        handler(state)
    elif 32 <= c <= 126:
        insert_char(state, chr(c))

    state.quit_times = KILO_QUIT_TIMES
    return False


KEY_HANDLERS: dict[int, Callable[[State], None]] = {
    CTRL_S: save_file,
    CTRL_F: find,
    CTRL_A: move_home,
    CTRL_E: move_end,
    CTRL_H: delete_char,
    HOME_KEY: move_home,
    END_KEY: move_end,
    PAGE_UP: page_up,
    PAGE_DOWN: page_down,
    BACKSPACE: delete_char,
    DEL_KEY: delete_char,
    ENTER: insert_newline,
    TAB: insert_tab,
    ARROW_UP: move_up,
    ARROW_DOWN: move_down,
    ARROW_LEFT: move_left,
    ARROW_RIGHT: move_right,
}


IGNORED_KEYS = {CTRL_L, ESC}
