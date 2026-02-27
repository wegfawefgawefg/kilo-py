from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from .constants import (
    ARROW_DOWN,
    ARROW_LEFT,
    ARROW_RIGHT,
    ARROW_UP,
    BACKSPACE,
    CTRL_H,
    DEL_KEY,
    ENTER,
    ESC,
    HL_MATCH,
    HL_NONPRINT,
    HL_NORMAL,
    KILO_QUERY_LEN,
    KILO_TAB_STOP,
    KILO_VERSION,
)
from .syntax import syntax_to_color
from .terminal import read_key

if TYPE_CHECKING:
    from .editor import Editor


def refresh_screen(editor: Editor) -> None:
    cfg = editor.cfg
    ab: list[str] = []
    ab.append("\x1b[?25l")
    ab.append("\x1b[H")

    for y in range(cfg.screenrows):
        filerow = cfg.rowoff + y
        if filerow >= cfg.numrows:
            if cfg.numrows == 0 and y == cfg.screenrows // 3:
                welcome = f"Kilo editor -- verison {KILO_VERSION}"
                if len(welcome) > cfg.screencols:
                    welcome = welcome[: cfg.screencols]
                padding = (cfg.screencols - len(welcome)) // 2
                if padding:
                    ab.append("~")
                    padding -= 1
                if padding > 0:
                    ab.append(" " * padding)
                ab.append(welcome)
                ab.append("\x1b[0K\r\n")
            else:
                ab.append("~\x1b[0K\r\n")
            continue

        row = cfg.rows[filerow]
        length = row.rsize - cfg.coloff
        current_color = -1
        if length > 0:
            if length > cfg.screencols:
                length = cfg.screencols
            c = row.render[cfg.coloff : cfg.coloff + length]
            hl = row.hl[cfg.coloff : cfg.coloff + length]
            for j, ch in enumerate(c):
                h = hl[j] if j < len(hl) else HL_NORMAL
                if h == HL_NONPRINT:
                    if ord(ch) <= 26:
                        sym = chr(ord("@") + ord(ch))
                    else:
                        sym = "?"
                    ab.append("\x1b[7m")
                    ab.append(sym)
                    ab.append("\x1b[0m")
                elif h == HL_NORMAL:
                    if current_color != -1:
                        ab.append("\x1b[39m")
                        current_color = -1
                    ab.append(ch)
                else:
                    color = syntax_to_color(h)
                    if color != current_color:
                        ab.append(f"\x1b[{color}m")
                        current_color = color
                    ab.append(ch)
        ab.append("\x1b[39m")
        ab.append("\x1b[0K")
        ab.append("\r\n")

    ab.append("\x1b[0K")
    ab.append("\x1b[7m")
    filename = cfg.filename if cfg.filename else "[No Name]"
    status = f"{filename:.20} - {cfg.numrows} lines {'(modified)' if cfg.dirty else ''}"
    rstatus = f"{cfg.rowoff + cfg.cy + 1}/{cfg.numrows}"
    if len(status) > cfg.screencols:
        status = status[: cfg.screencols]
    ab.append(status)
    fill = len(status)
    while fill < cfg.screencols:
        if cfg.screencols - fill == len(rstatus):
            ab.append(rstatus)
            break
        ab.append(" ")
        fill += 1
    ab.append("\x1b[0m\r\n")

    ab.append("\x1b[0K")
    if cfg.statusmsg and time.time() - cfg.statusmsg_time < 5:
        msg = cfg.statusmsg
        if len(msg) > cfg.screencols:
            msg = msg[: cfg.screencols]
        ab.append(msg)

    cx = 1
    filerow = cfg.rowoff + cfg.cy
    row = cfg.rows[filerow] if filerow < cfg.numrows else None
    if row is not None:
        for j in range(cfg.coloff, cfg.cx + cfg.coloff):
            if j < row.size and row.chars[j] == "\t":
                cx += (KILO_TAB_STOP - 1) - (cx % KILO_TAB_STOP)
            cx += 1
    ab.append(f"\x1b[{cfg.cy + 1};{cx}H")
    ab.append("\x1b[?25h")

    os.write(editor.stdout_fd, "".join(ab).encode(errors="replace"))


def find(editor: Editor, fd: int) -> None:
    cfg = editor.cfg
    query = ""
    last_match = -1
    find_next = 0
    saved_hl_line = -1
    saved_hl: list[int] | None = None

    saved_cx = cfg.cx
    saved_cy = cfg.cy
    saved_coloff = cfg.coloff
    saved_rowoff = cfg.rowoff

    def restore_hl() -> None:
        nonlocal saved_hl, saved_hl_line
        if saved_hl is not None and 0 <= saved_hl_line < cfg.numrows:
            cfg.rows[saved_hl_line].hl = saved_hl
        saved_hl = None
        saved_hl_line = -1

    while True:
        editor.set_status_message("Search: %s (Use ESC/Arrows/Enter)", query)
        editor.refresh_screen()

        c = read_key(fd)
        if c in (DEL_KEY, CTRL_H, BACKSPACE):
            if query:
                query = query[:-1]
                last_match = -1
        elif c in (ESC, ENTER):
            if c == ESC:
                cfg.cx = saved_cx
                cfg.cy = saved_cy
                cfg.coloff = saved_coloff
                cfg.rowoff = saved_rowoff
            restore_hl()
            editor.set_status_message("")
            return
        elif c in (ARROW_RIGHT, ARROW_DOWN):
            find_next = 1
        elif c in (ARROW_LEFT, ARROW_UP):
            find_next = -1
        elif 32 <= c <= 126:
            if len(query) < KILO_QUERY_LEN:
                query += chr(c)
                last_match = -1

        if last_match == -1:
            find_next = 1
        if not find_next:
            continue

        match_row = -1
        match_offset = -1
        current = last_match
        for _ in range(cfg.numrows):
            current += find_next
            if current == -1:
                current = cfg.numrows - 1
            elif current == cfg.numrows:
                current = 0
            idx = cfg.rows[current].render.find(query)
            if idx != -1:
                match_row = current
                match_offset = idx
                break
        find_next = 0

        restore_hl()
        if match_row == -1:
            continue

        row = cfg.rows[match_row]
        last_match = match_row
        saved_hl_line = match_row
        saved_hl = row.hl.copy()
        for i in range(match_offset, min(match_offset + len(query), row.rsize)):
            row.hl[i] = HL_MATCH

        cfg.cy = 0
        cfg.cx = match_offset
        cfg.rowoff = match_row
        cfg.coloff = 0
        if cfg.cx > cfg.screencols:
            diff = cfg.cx - cfg.screencols
            cfg.cx -= diff
            cfg.coloff += diff
