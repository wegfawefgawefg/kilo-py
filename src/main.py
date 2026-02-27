from __future__ import annotations

import os
import shutil
import signal
import sys
import termios
import time
from dataclasses import dataclass, field

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


def ctrl(ch: str) -> int:
    return ord(ch.upper()) & 0x1F


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
        if ord("0") <= b <= ord("9"):
            seq2 = os.read(fd, 1)
            if not seq2:
                return ESC
            if seq2[0] == ord("~"):
                if b == ord("3"):
                    return DEL_KEY
                if b == ord("5"):
                    return PAGE_UP
                if b == ord("6"):
                    return PAGE_DOWN
        else:
            if b == ord("A"):
                return ARROW_UP
            if b == ord("B"):
                return ARROW_DOWN
            if b == ord("C"):
                return ARROW_RIGHT
            if b == ord("D"):
                return ARROW_LEFT
            if b == ord("H"):
                return HOME_KEY
            if b == ord("F"):
                return END_KEY
    elif a == ord("O"):
        if b == ord("H"):
            return HOME_KEY
        if b == ord("F"):
            return END_KEY
    return ESC


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
        out: list[str] = ["\x1b[?25l", "\x1b[H"]

        for y in range(self.screenrows):
            filerow = self.rowoff + y
            if filerow >= len(self.rows):
                if not self.rows and y == self.screenrows // 3:
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
                else:
                    out.append("~")
            else:
                line = self.rows[filerow]
                seg = line[self.coloff : self.coloff + self.screencols]
                out.append(seg)
            out.append("\x1b[K")
            out.append("\r\n")

        name = os.path.basename(self.filename) or "[No Name]"
        mod = " (modified)" if self.dirty else ""
        status = f"{name:.20} - {len(self.rows)} lines{mod}"
        rstatus = f"{self.cy + 1}/{max(1, len(self.rows))}"
        if len(status) > self.screencols:
            status = status[: self.screencols]
        out.append("\x1b[7m")
        out.append(status)
        while len(status) < self.screencols:
            if self.screencols - len(status) == len(rstatus):
                out.append(rstatus)
                break
            out.append(" ")
            status += " "
        out.append("\x1b[m")
        out.append("\r\n")

        out.append("\x1b[K")
        if self.statusmsg and (time.time() - self.status_time) < 5:
            out.append(self.statusmsg[: self.screencols])

        screen_cy = (self.cy - self.rowoff) + 1
        screen_cx = (self.cx - self.coloff) + 1
        if screen_cy < 1:
            screen_cy = 1
        if screen_cx < 1:
            screen_cx = 1
        out.append(f"\x1b[{screen_cy};{screen_cx}H")
        out.append("\x1b[?25h")
        os.write(self.stdout_fd, "".join(out).encode("utf-8", errors="replace"))

    def current_row_len(self) -> int:
        if 0 <= self.cy < len(self.rows):
            return len(self.rows[self.cy])
        return 0

    def move_cursor(self, key: int) -> None:
        if key == ARROW_LEFT:
            if self.cx > 0:
                self.cx -= 1
            elif self.cy > 0:
                self.cy -= 1
                self.cx = len(self.rows[self.cy])
        elif key == ARROW_RIGHT:
            rowlen = self.current_row_len()
            if self.cx < rowlen:
                self.cx += 1
            elif self.cy + 1 < len(self.rows):
                self.cy += 1
                self.cx = 0
        elif key == ARROW_UP and self.cy > 0:
            self.cy -= 1
        elif key == ARROW_DOWN and self.cy + 1 < len(self.rows):
            self.cy += 1

        rowlen = self.current_row_len()
        if self.cx > rowlen:
            self.cx = rowlen

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

    def find(self) -> None:
        query = ""
        last_match = -1
        direction = 1
        saved = (self.cx, self.cy, self.coloff, self.rowoff)

        while True:
            self.set_status(f"Search: {query} (ESC/Arrows/Enter)")
            self.refresh_screen()
            c = read_key(self.stdin_fd)

            if c in (BACKSPACE, ctrl("h"), DEL_KEY):
                if query:
                    query = query[:-1]
                    last_match = -1
            elif c == ESC:
                self.cx, self.cy, self.coloff, self.rowoff = saved
                self.set_status("")
                return
            elif c == ENTER:
                self.set_status("")
                return
            elif c in (ARROW_RIGHT, ARROW_DOWN):
                direction = 1
            elif c in (ARROW_LEFT, ARROW_UP):
                direction = -1
            elif 32 <= c <= 126:
                query += chr(c)
                last_match = -1
            else:
                continue

            if not query or not self.rows:
                continue
            if last_match == -1:
                direction = 1

            current = last_match
            for _ in range(len(self.rows)):
                current += direction
                if current == -1:
                    current = len(self.rows) - 1
                elif current == len(self.rows):
                    current = 0
                pos = self.rows[current].find(query)
                if pos != -1:
                    last_match = current
                    self.cy = current
                    self.cx = pos
                    self.rowoff = self.cy
                    self.coloff = 0
                    break
            direction = 0

    def process_keypress(self) -> None:
        c = read_key(self.stdin_fd)
        if c == ctrl("q"):
            if self.dirty and self.quit_times > 0:
                self.set_status(
                    f"WARNING!!! Unsaved changes. Press Ctrl-Q {self.quit_times} more times to quit."
                )
                self.quit_times -= 1
                return
            raise SystemExit(0)
        if c == ctrl("s"):
            try:
                self.save_file()
            except OSError as exc:
                self.set_status(f"Can't save! I/O error: {exc}")
        elif c == ctrl("f"):
            self.find()
        elif c in (HOME_KEY, ctrl("a")):
            self.cx = 0
        elif c in (END_KEY, ctrl("e")):
            self.cx = self.current_row_len()
        elif c == PAGE_UP:
            self.cy = max(0, self.cy - self.screenrows)
        elif c == PAGE_DOWN:
            self.cy = min(max(0, len(self.rows) - 1), self.cy + self.screenrows)
        elif c in (ARROW_UP, ARROW_DOWN, ARROW_LEFT, ARROW_RIGHT):
            self.move_cursor(c)
        elif c in (BACKSPACE, ctrl("h"), DEL_KEY):
            self.delete_char()
        elif c == ENTER:
            self.insert_newline()
        elif c == TAB:
            self.insert_char("    ")
        elif c in (ctrl("l"), ESC):
            pass
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
