from __future__ import annotations

import time
import shutil

from consts import State


def resize(state: State) -> None:
    size = shutil.get_terminal_size((80, 24))
    state.screencols = size.columns
    state.screenrows = max(1, size.lines - 2)


def set_status(state: State, msg: str) -> None:
    state.statusmsg = msg
    state.status_time = time.time()


def open_file(state: State) -> None:
    try:
        with open(state.filename, "r", encoding="utf-8", errors="replace") as f:
            state.rows = [line.rstrip("\n").rstrip("\r") for line in f]
    except FileNotFoundError:
        state.rows = []


def save_file(state: State) -> None:
    text = "".join(f"{line}\n" for line in state.rows)
    try:
        with open(state.filename, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    except OSError as exc:
        set_status(state, f"Can't save! I/O error: {exc}")
        return
    state.dirty = False
    set_status(state, f"{len(text.encode('utf-8'))} bytes written to disk")
