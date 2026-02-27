from __future__ import annotations

from state import State


def row_len(state: State, y: int | None = None) -> int:
    y = state.cy if y is None else y
    if 0 <= y < len(state.rows):
        return len(state.rows[y])
    return 0


def clamp_cursor_x(state: State) -> None:
    state.cx = min(state.cx, row_len(state))


def move_left(state: State) -> None:
    if state.cx > 0:
        state.cx -= 1
    elif state.cy > 0:
        state.cy -= 1
        state.cx = len(state.rows[state.cy])
    clamp_cursor_x(state)


def move_right(state: State) -> None:
    line_len = row_len(state)
    if state.cx < line_len:
        state.cx += 1
    elif state.cy + 1 < len(state.rows):
        state.cy += 1
        state.cx = 0
    clamp_cursor_x(state)


def move_up(state: State) -> None:
    if state.cy > 0:
        state.cy -= 1
    clamp_cursor_x(state)


def move_down(state: State) -> None:
    if state.cy + 1 < len(state.rows):
        state.cy += 1
    clamp_cursor_x(state)


def insert_char(state: State, c: str) -> None:
    if state.cy == len(state.rows):
        state.rows.append("")
    row = state.rows[state.cy]
    state.rows[state.cy] = row[: state.cx] + c + row[state.cx :]
    state.cx += len(c)
    state.dirty = True


def insert_newline(state: State) -> None:
    if state.cy == len(state.rows):
        state.rows.append("")
    else:
        row = state.rows[state.cy]
        state.rows[state.cy] = row[: state.cx]
        state.rows.insert(state.cy + 1, row[state.cx :])
    state.cy += 1
    state.cx = 0
    state.dirty = True


def delete_char(state: State) -> None:
    if state.cy == len(state.rows):
        return
    if state.cx == 0 and state.cy == 0:
        return
    if state.cx > 0:
        row = state.rows[state.cy]
        state.rows[state.cy] = row[: state.cx - 1] + row[state.cx :]
        state.cx -= 1
    else:
        prev_len = len(state.rows[state.cy - 1])
        state.rows[state.cy - 1] += state.rows[state.cy]
        del state.rows[state.cy]
        state.cy -= 1
        state.cx = prev_len
    state.dirty = True


def move_home(state: State) -> None:
    state.cx = 0


def move_end(state: State) -> None:
    state.cx = row_len(state)


def page_up(state: State) -> None:
    state.cy = max(0, state.cy - state.screenrows)


def page_down(state: State) -> None:
    state.cy = min(max(0, len(state.rows) - 1), state.cy + state.screenrows)


def insert_tab(state: State) -> None:
    insert_char(state, "    ")
