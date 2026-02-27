from __future__ import annotations

from dataclasses import dataclass, field

from consts import KILO_QUIT_TIMES


@dataclass
class SearchSnapshot:
    cx: int
    cy: int
    coloff: int
    rowoff: int


@dataclass
class State:
    filename: str
    stdin_fd: int
    stdout_fd: int

    cx: int = 0
    cy: int = 0
    rowoff: int = 0
    coloff: int = 0
    screenrows: int = 0
    screencols: int = 0
    rows: list[str] = field(default_factory=list)
    dirty: bool = False
    statusmsg: str = ""
    status_time: float = 0.0
    quit_times: int = KILO_QUIT_TIMES
