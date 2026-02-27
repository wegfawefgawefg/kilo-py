from __future__ import annotations

import os
import shutil
import signal
import sys
import termios
import time
from dataclasses import dataclass, field
from typing import Callable

KILO_VERSION = "0.1.0-py"
KILO_QUIT_TIMES = 3

BACKSPACE = 127
ENTER = 13
ESC = 27
TAB = 9

ARROW_LEFT = 1000
ARROW_RIGHT = 1001
ARROW_UP = 1002
ARROW_DOWN = 1003
DEL_KEY = 1004
HOME_KEY = 1005
END_KEY = 1006
PAGE_UP = 1007
PAGE_DOWN = 1008

ANSI_HIDE_CURSOR = "\x1b[?25l"
ANSI_SHOW_CURSOR = "\x1b[?25h"
ANSI_CURSOR_HOME = "\x1b[H"
ANSI_CLEAR_LINE = "\x1b[K"
ANSI_INVERT_ON = "\x1b[7m"
ANSI_INVERT_OFF = "\x1b[m"

CSI_SIMPLE_MAP = {
    ord("A"): ARROW_UP,
    ord("B"): ARROW_DOWN,
    ord("C"): ARROW_RIGHT,
    ord("D"): ARROW_LEFT,
    ord("H"): HOME_KEY,
    ord("F"): END_KEY,
}
CSI_TILDE_MAP = {
    ord("3"): DEL_KEY,
    ord("5"): PAGE_UP,
    ord("6"): PAGE_DOWN,
}
SS3_SIMPLE_MAP = {
    ord("H"): HOME_KEY,
    ord("F"): END_KEY,
}


def ctrl(ch: str) -> int:
    return ord(ch.upper()) & 0x1F


CTRL_Q = ctrl("q")
CTRL_S = ctrl("s")
CTRL_F = ctrl("f")
CTRL_A = ctrl("a")
CTRL_E = ctrl("e")
CTRL_H = ctrl("h")
CTRL_L = ctrl("l")


class RawMode:
    def __init__(self, fd: int) -> None:
        self.fd = fd
        self.orig: list[int] | None = None

    def __enter__(self) -> "RawMode":
        self.orig = termios.tcgetattr(self.fd)
        raw = termios.tcgetattr(self.fd)
        raw[0] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON)
        raw[1] &= ~termios.OPOST
        raw[2] |= termios.CS8
        raw[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
        raw[6][termios.VMIN] = 0
        raw[6][termios.VTIME] = 1
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, raw)
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        if self.orig is not None:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.orig)


def read_key(fd: int) -> int:
    while True:
        c = os.read(fd, 1)
        if c:
            break
    ch = c[0]
    if ch != ESC:
        return ch

    seq0 = os.read(fd, 1)
    seq1 = os.read(fd, 1)
    if not seq0 or not seq1:
        return ESC
    a, b = seq0[0], seq1[0]

    if a == ord("["):
        simple = CSI_SIMPLE_MAP.get(b)
        if simple is not None:
            return simple
        if ord("0") <= b <= ord("9"):
            seq2 = os.read(fd, 1)
            if not seq2:
                return ESC
            if seq2[0] == ord("~"):
                return CSI_TILDE_MAP.get(b, ESC)
    elif a == ord("O"):
        return SS3_SIMPLE_MAP.get(b, ESC)
    return ESC


@dataclass
class SearchSnapshot:
    cx: int
    cy: int
    coloff: int
    rowoff: int


@dataclass
class Editor:
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
    key_handlers: dict[int, Callable[[], None]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.key_handlers = {
            CTRL_S: self._safe_save,
            CTRL_F: self.find,
            CTRL_A: self._home,
            CTRL_E: self._end,
            CTRL_H: self.delete_char,
            CTRL_L: self._noop,
            ARROW_UP: self._move_up,
            ARROW_DOWN: self._move_down,
            ARROW_LEFT: self._move_left,
            ARROW_RIGHT: self._move_right,
            HOME_KEY: self._home,
            END_KEY: self._end,
            PAGE_UP: self._page_up,
            PAGE_DOWN: self._page_down,
            BACKSPACE: self.delete_char,
            DEL_KEY: self.delete_char,
            ENTER: self.insert_newline,
            TAB: self._insert_tab,
            ESC: self._noop,
        }

    def resize(self) -> None:
        size = shutil.get_terminal_size((80, 24))
        self.screencols = size.columns
        self.screenrows = max(1, size.lines - 2)

    def set_status(self, msg: str) -> None:
        self.statusmsg = msg
        self.status_time = time.time()

    def open_file(self) -> None:
        try:
            with open(self.filename, "r", encoding="utf-8", errors="replace") as f:
                self.rows = [line.rstrip("\n").rstrip("\r") for line in f]
        except FileNotFoundError:
            self.rows = []

    def save_file(self) -> None:
        text = "".join(f"{line}\n" for line in self.rows)
        with open(self.filename, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        self.dirty = False
        self.set_status(f"{len(text.encode('utf-8'))} bytes written to disk")

    def scroll(self) -> None:
        if self.cy < self.rowoff:
            self.rowoff = self.cy
        if self.cy >= self.rowoff + self.screenrows:
            self.rowoff = self.cy - self.screenrows + 1
        if self.cx < self.coloff:
            self.coloff = self.cx
        if self.cx >= self.coloff + self.screencols:
            self.coloff = self.cx - self.screencols + 1

    def refresh_screen(self) -> None:
        self.scroll()
        out: list[str] = [ANSI_HIDE_CURSOR, ANSI_CURSOR_HOME]
        self._draw_rows(out)
        self._draw_status_bar(out)
        self._draw_message_bar(out)
        out.append(self._cursor_escape())
        out.append(ANSI_SHOW_CURSOR)
        os.write(self.stdout_fd, "".join(out).encode("utf-8", errors="replace"))

    def _draw_rows(self, out: list[str]) -> None:
        for y in range(self.screenrows):
            filerow = self.rowoff + y
            if filerow < len(self.rows):
                out.append(self.rows[filerow][self.coloff : self.coloff + self.screencols])
            elif not self.rows and y == self.screenrows // 3:
                self._draw_welcome(out)
            else:
                out.append("~")
            out.append(ANSI_CLEAR_LINE)
            out.append("\r\n")

    def _draw_welcome(self, out: list[str]) -> None:
        welcome = f"Kilo editor -- version {KILO_VERSION}"
        if len(welcome) > self.screencols:
            welcome = welcome[: self.screencols]
        pad = (self.screencols - len(welcome)) // 2
        if pad:
            out.append("~")
            pad -= 1
        if pad > 0:
            out.append(" " * pad)
        out.append(welcome)

    def _draw_status_bar(self, out: list[str]) -> None:
        name = os.path.basename(self.filename) or "[No Name]"
        mod = " (modified)" if self.dirty else ""
        status = f"{name:.20} - {len(self.rows)} lines{mod}"[: self.screencols]
        rstatus = f"{self.cy + 1}/{max(1, len(self.rows))}"
        out.append(ANSI_INVERT_ON)
        out.append(status)
        fill = len(status)
        while fill < self.screencols:
            if self.screencols - fill == len(rstatus):
                out.append(rstatus)
                break
            out.append(" ")
            fill += 1
        out.append(ANSI_INVERT_OFF)
        out.append("\r\n")

    def _draw_message_bar(self, out: list[str]) -> None:
        out.append(ANSI_CLEAR_LINE)
        if self.statusmsg and (time.time() - self.status_time) < 5:
            out.append(self.statusmsg[: self.screencols])

    def _cursor_escape(self) -> str:
        screen_cy = max(1, (self.cy - self.rowoff) + 1)
        screen_cx = max(1, (self.cx - self.coloff) + 1)
        return f"\x1b[{screen_cy};{screen_cx}H"

    def row_len(self, y: int | None = None) -> int:
        y = self.cy if y is None else y
        if 0 <= y < len(self.rows):
            return len(self.rows[y])
        return 0

    def move_cursor(self, key: int) -> None:
        if key == ARROW_LEFT:
            self._move_left()
        elif key == ARROW_RIGHT:
            self._move_right()
        elif key == ARROW_UP:
            self._move_up()
        elif key == ARROW_DOWN:
            self._move_down()

        rowlen = self.row_len()
        if self.cx > rowlen:
            self.cx = rowlen

    def _move_left(self) -> None:
        if self.cx > 0:
            self.cx -= 1
        elif self.cy > 0:
            self.cy -= 1
            self.cx = len(self.rows[self.cy])

    def _move_right(self) -> None:
        rowlen = self.row_len()
        if self.cx < rowlen:
            self.cx += 1
        elif self.cy + 1 < len(self.rows):
            self.cy += 1
            self.cx = 0

    def _move_up(self) -> None:
        if self.cy > 0:
            self.cy -= 1

    def _move_down(self) -> None:
        if self.cy + 1 < len(self.rows):
            self.cy += 1

    def insert_char(self, c: str) -> None:
        if self.cy == len(self.rows):
            self.rows.append("")
        row = self.rows[self.cy]
        self.rows[self.cy] = row[: self.cx] + c + row[self.cx :]
        self.cx += len(c)
        self.dirty = True

    def insert_newline(self) -> None:
        if self.cy == len(self.rows):
            self.rows.append("")
        else:
            row = self.rows[self.cy]
            self.rows[self.cy] = row[: self.cx]
            self.rows.insert(self.cy + 1, row[self.cx :])
        self.cy += 1
        self.cx = 0
        self.dirty = True

    def delete_char(self) -> None:
        if self.cy == len(self.rows):
            return
        if self.cx == 0 and self.cy == 0:
            return
        if self.cx > 0:
            row = self.rows[self.cy]
            self.rows[self.cy] = row[: self.cx - 1] + row[self.cx :]
            self.cx -= 1
        else:
            prev_len = len(self.rows[self.cy - 1])
            self.rows[self.cy - 1] += self.rows[self.cy]
            del self.rows[self.cy]
            self.cy -= 1
            self.cx = prev_len
        self.dirty = True

    def _confirm_or_quit(self) -> None:
        if self.dirty and self.quit_times > 0:
            self.set_status(
                f"WARNING!!! Unsaved changes. Press Ctrl-Q {self.quit_times} more times to quit."
            )
            self.quit_times -= 1
            return
        raise SystemExit(0)

    def _safe_save(self) -> None:
        try:
            self.save_file()
        except OSError as exc:
            self.set_status(f"Can't save! I/O error: {exc}")

    def _home(self) -> None:
        self.cx = 0

    def _end(self) -> None:
        self.cx = self.row_len()

    def _page_up(self) -> None:
        self.cy = max(0, self.cy - self.screenrows)

    def _page_down(self) -> None:
        self.cy = min(max(0, len(self.rows) - 1), self.cy + self.screenrows)

    def _insert_tab(self) -> None:
        self.insert_char("    ")

    def _noop(self) -> None:
        return

    def _restore_search_snapshot(self, saved: SearchSnapshot) -> None:
        self.cx = saved.cx
        self.cy = saved.cy
        self.coloff = saved.coloff
        self.rowoff = saved.rowoff

    def _search_key_update(
        self,
        c: int,
        query: str,
        last_match: int,
        direction: int,
    ) -> tuple[str, int, int, str]:
        if c in (BACKSPACE, CTRL_H, DEL_KEY):
            if query:
                query = query[:-1]
                last_match = -1
            return query, last_match, direction, "continue"
        if c == ESC:
            return query, last_match, direction, "cancel"
        if c == ENTER:
            return query, last_match, direction, "accept"
        if c in (ARROW_RIGHT, ARROW_DOWN):
            return query, last_match, 1, "search"
        if c in (ARROW_LEFT, ARROW_UP):
            return query, last_match, -1, "search"
        if 32 <= c <= 126:
            return query + chr(c), -1, direction, "search"
        return query, last_match, direction, "continue"

    def _search_next_match(self, query: str, last_match: int, direction: int) -> tuple[int, int] | None:
        current = last_match
        for _ in range(len(self.rows)):
            current += direction
            if current == -1:
                current = len(self.rows) - 1
            elif current == len(self.rows):
                current = 0
            pos = self.rows[current].find(query)
            if pos != -1:
                return current, pos
        return None

    def _jump_to_match(self, row: int, col: int) -> None:
        self.cy = row
        self.cx = col
        self.rowoff = row
        self.coloff = 0

    def find(self) -> None:
        query = ""
        last_match = -1
        direction = 1
        saved = SearchSnapshot(self.cx, self.cy, self.coloff, self.rowoff)

        while True:
            self.set_status(f"Search: {query} (ESC/Arrows/Enter)")
            self.refresh_screen()
            c = read_key(self.stdin_fd)

            query, last_match, direction, action = self._search_key_update(
                c, query, last_match, direction
            )
            if action == "cancel":
                self._restore_search_snapshot(saved)
                self.set_status("")
                return
            if action == "accept":
                self.set_status("")
                return
            if action != "search":
                continue

            if not query or not self.rows:
                continue
            if last_match == -1:
                direction = 1

            match = self._search_next_match(query, last_match, direction)
            if match is not None:
                last_match, col = match
                self._jump_to_match(last_match, col)
            direction = 0

    def process_keypress(self) -> None:
        c = read_key(self.stdin_fd)

        if c == CTRL_Q:
            self._confirm_or_quit()
            return

        handler = self.key_handlers.get(c)
        if handler is not None:
            handler()
        elif 32 <= c <= 126:
            self.insert_char(chr(c))

        self.quit_times = KILO_QUIT_TIMES


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python3 src/main.py <filename>", file=sys.stderr)
        return 1
    if not os.isatty(sys.stdin.fileno()) or not os.isatty(sys.stdout.fileno()):
        print("kilo-py requires a real terminal (TTY).", file=sys.stderr)
        return 1

    editor = Editor(filename=argv[1], stdin_fd=sys.stdin.fileno(), stdout_fd=sys.stdout.fileno())
    editor.resize()
    editor.open_file()
    editor.set_status("HELP: Ctrl-S save | Ctrl-Q quit | Ctrl-F find")

    def on_resize(_signum: int, _frame) -> None:
        editor.resize()
        editor.refresh_screen()

    signal.signal(signal.SIGWINCH, on_resize)
    with RawMode(editor.stdin_fd):
        while True:
            editor.refresh_screen()
            editor.process_keypress()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
