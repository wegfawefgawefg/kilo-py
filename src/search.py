from __future__ import annotations

from io_ops import set_status
from render import refresh_screen
from consts import (
    ARROW_DOWN,
    ARROW_LEFT,
    ARROW_RIGHT,
    ARROW_UP,
    BACKSPACE,
    CTRL_H,
    DEL_KEY,
    ENTER,
    ESC,
    SEARCH_ACCEPT,
    SEARCH_CANCEL,
    SEARCH_CONTINUE,
    SEARCH_RUN,
)
from state import SearchSnapshot, State
from terminal import read_key


def restore_search_snapshot(state: State, saved: SearchSnapshot) -> None:
    state.cx = saved.cx
    state.cy = saved.cy
    state.coloff = saved.coloff
    state.rowoff = saved.rowoff


def search_key_update(
    c: int,
    query: str,
    last_match: int,
    direction: int,
) -> tuple[str, int, int, int]:
    if c in (BACKSPACE, CTRL_H, DEL_KEY):
        if query:
            query = query[:-1]
            last_match = -1
        return query, last_match, direction, SEARCH_CONTINUE
    if c == ESC:
        return query, last_match, direction, SEARCH_CANCEL
    if c == ENTER:
        return query, last_match, direction, SEARCH_ACCEPT
    if c in (ARROW_RIGHT, ARROW_DOWN):
        return query, last_match, 1, SEARCH_RUN
    if c in (ARROW_LEFT, ARROW_UP):
        return query, last_match, -1, SEARCH_RUN
    if 32 <= c <= 126:
        return query + chr(c), -1, direction, SEARCH_RUN
    return query, last_match, direction, SEARCH_CONTINUE


def search_next_match(
    state: State, query: str, last_match: int, direction: int
) -> tuple[int, int] | None:
    current = last_match
    for _ in range(len(state.rows)):
        current += direction
        if current == -1:
            current = len(state.rows) - 1
        elif current == len(state.rows):
            current = 0
        pos = state.rows[current].find(query)
        if pos != -1:
            return current, pos
    return None


def jump_to_match(state: State, row: int, col: int) -> None:
    state.cy = row
    state.cx = col
    state.rowoff = row
    state.coloff = 0


def find(state: State) -> None:
    query = ""
    last_match = -1
    direction = 1
    saved = SearchSnapshot(state.cx, state.cy, state.coloff, state.rowoff)

    while True:
        set_status(state, f"Search: {query} (ESC/Arrows/Enter)")
        refresh_screen(state)
        c = read_key(state.stdin_fd)

        query, last_match, direction, action = search_key_update(
            c, query, last_match, direction
        )
        if action == SEARCH_CANCEL:
            restore_search_snapshot(state, saved)
            set_status(state, "")
            return
        if action == SEARCH_ACCEPT:
            set_status(state, "")
            return
        if action != SEARCH_RUN:
            continue

        if not query or not state.rows:
            continue
        if last_match == -1:
            direction = 1

        match = search_next_match(state, query, last_match, direction)
        if match is not None:
            last_match, col = match
            jump_to_match(state, last_match, col)
        direction = 0
