from __future__ import annotations

import os
import time

from model import (
    ANSI_CLEAR_LINE,
    ANSI_CURSOR_HOME,
    ANSI_HIDE_CURSOR,
    ANSI_INVERT_OFF,
    ANSI_INVERT_ON,
    ANSI_SHOW_CURSOR,
    KILO_VERSION,
    State,
)


def scroll(state: State) -> None:
    if state.cy < state.rowoff:
        state.rowoff = state.cy
    if state.cy >= state.rowoff + state.screenrows:
        state.rowoff = state.cy - state.screenrows + 1
    if state.cx < state.coloff:
        state.coloff = state.cx
    if state.cx >= state.coloff + state.screencols:
        state.coloff = state.cx - state.screencols + 1


def refresh_screen(state: State) -> None:
    scroll(state)
    out: list[str] = [ANSI_HIDE_CURSOR, ANSI_CURSOR_HOME]
    draw_rows(state, out)
    draw_status_bar(state, out)
    draw_message_bar(state, out)
    out.append(cursor_escape(state))
    out.append(ANSI_SHOW_CURSOR)
    os.write(state.stdout_fd, "".join(out).encode("utf-8", errors="replace"))


def draw_rows(state: State, out: list[str]) -> None:
    for y in range(state.screenrows):
        filerow = state.rowoff + y
        if filerow < len(state.rows):
            out.append(state.rows[filerow][state.coloff : state.coloff + state.screencols])
        elif not state.rows and y == state.screenrows // 3:
            draw_welcome(state, out)
        else:
            out.append("~")
        out.append(ANSI_CLEAR_LINE)
        out.append("\r\n")


def draw_welcome(state: State, out: list[str]) -> None:
    welcome = f"Kilo editor -- version {KILO_VERSION}"
    if len(welcome) > state.screencols:
        welcome = welcome[: state.screencols]
    pad = (state.screencols - len(welcome)) // 2
    if pad:
        out.append("~")
        pad -= 1
    if pad > 0:
        out.append(" " * pad)
    out.append(welcome)


def draw_status_bar(state: State, out: list[str]) -> None:
    name = os.path.basename(state.filename) or "[No Name]"
    mod = " (modified)" if state.dirty else ""
    status = f"{name:.20} - {len(state.rows)} lines{mod}"[: state.screencols]
    rstatus = f"{state.cy + 1}/{max(1, len(state.rows))}"
    out.append(ANSI_INVERT_ON)
    out.append(status)
    fill = len(status)
    while fill < state.screencols:
        if state.screencols - fill == len(rstatus):
            out.append(rstatus)
            break
        out.append(" ")
        fill += 1
    out.append(ANSI_INVERT_OFF)
    out.append("\r\n")


def draw_message_bar(state: State, out: list[str]) -> None:
    out.append(ANSI_CLEAR_LINE)
    if state.statusmsg and (time.time() - state.status_time) < 5:
        out.append(state.statusmsg[: state.screencols])


def cursor_escape(state: State) -> str:
    screen_cy = max(1, (state.cy - state.rowoff) + 1)
    screen_cx = max(1, (state.cx - state.coloff) + 1)
    return f"\x1b[{screen_cy};{screen_cx}H"
