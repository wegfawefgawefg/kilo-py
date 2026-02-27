from __future__ import annotations

import errno
import os
import signal
import sys
import time
from typing import Final

from .constants import (
    ARROW_DOWN,
    ARROW_LEFT,
    ARROW_RIGHT,
    ARROW_UP,
    BACKSPACE,
    CTRL_C,
    CTRL_F,
    CTRL_H,
    CTRL_L,
    CTRL_Q,
    CTRL_S,
    DEL_KEY,
    ENTER,
    ESC,
    KILO_QUIT_TIMES,
    KILO_TAB_STOP,
    PAGE_DOWN,
    PAGE_UP,
)
from .models import EditorConfig, Row
from .syntax import select_syntax_highlight, update_syntax
from .terminal import RawMode, get_window_size, read_key
from .ui import find, refresh_screen


STDIN_FD: Final[int] = sys.stdin.fileno()
STDOUT_FD: Final[int] = sys.stdout.fileno()


class Editor:
    def __init__(self) -> None:
        self.cfg = EditorConfig()
        self.quit_times = KILO_QUIT_TIMES
        self.stdin_fd = STDIN_FD
        self.stdout_fd = STDOUT_FD
        self.update_window_size()

    def update_window_size(self) -> None:
        try:
            rows, cols = get_window_size(STDIN_FD, STDOUT_FD)
        except OSError as exc:
            raise OSError(exc.errno, "Unable to query screen size") from exc
        self.cfg.screenrows = max(1, rows - 2)
        self.cfg.screencols = max(1, cols)

    def handle_sigwinch(self, _signum: int, _frame) -> None:
        self.update_window_size()
        if self.cfg.cy > self.cfg.screenrows - 1:
            self.cfg.cy = self.cfg.screenrows - 1
        if self.cfg.cx > self.cfg.screencols - 1:
            self.cfg.cx = self.cfg.screencols - 1
        self.refresh_screen()

    def set_status_message(self, fmt: str, *args: object) -> None:
        self.cfg.statusmsg = fmt % args if args else fmt
        self.cfg.statusmsg_time = time.time()

    def select_syntax_highlight(self, filename: str) -> None:
        select_syntax_highlight(self.cfg, filename)
        for row in self.cfg.rows:
            update_syntax(self.cfg, row.idx)

    def update_row(self, row: Row) -> None:
        out: list[str] = []
        idx = 0
        for ch in row.chars:
            if ch == "\t":
                out.append(" ")
                idx += 1
                while idx % KILO_TAB_STOP != 0:
                    out.append(" ")
                    idx += 1
            else:
                out.append(ch)
                idx += 1
        row.render = "".join(out)
        update_syntax(self.cfg, row.idx)

    def insert_row(self, at: int, s: str) -> None:
        if at > self.cfg.numrows:
            return
        self.cfg.rows.insert(at, Row(idx=at, chars=s))
        for j in range(at + 1, self.cfg.numrows):
            self.cfg.rows[j].idx = j
        self.update_row(self.cfg.rows[at])
        self.cfg.dirty += 1

    def del_row(self, at: int) -> None:
        if at >= self.cfg.numrows:
            return
        del self.cfg.rows[at]
        for j in range(at, self.cfg.numrows):
            self.cfg.rows[j].idx = j
        self.cfg.dirty += 1

    def rows_to_string(self) -> str:
        return "".join(f"{row.chars}\n" for row in self.cfg.rows)

    @staticmethod
    def _to_c_bytes(text: str) -> bytes:
        # Match C char truncation semantics for values outside one byte.
        return bytes((ord(ch) & 0xFF) for ch in text)

    def row_insert_char(self, row: Row, at: int, c: str) -> None:
        if at > row.size:
            pad = at - row.size
            row.chars = row.chars + (" " * pad) + c
        else:
            row.chars = row.chars[:at] + c + row.chars[at:]
        self.update_row(row)
        self.cfg.dirty += 1

    def row_append_string(self, row: Row, s: str) -> None:
        row.chars += s
        self.update_row(row)
        self.cfg.dirty += 1

    def row_del_char(self, row: Row, at: int) -> None:
        if at >= row.size:
            return
        row.chars = row.chars[:at] + row.chars[at + 1 :]
        self.update_row(row)
        self.cfg.dirty += 1

    def insert_char(self, c: int) -> None:
        filerow = self.cfg.rowoff + self.cfg.cy
        filecol = self.cfg.coloff + self.cfg.cx

        if filerow >= self.cfg.numrows:
            while self.cfg.numrows <= filerow:
                self.insert_row(self.cfg.numrows, "")

        row = self.cfg.rows[filerow]
        self.row_insert_char(row, filecol, chr(c & 0xFF))
        if self.cfg.cx == self.cfg.screencols - 1:
            self.cfg.coloff += 1
        else:
            self.cfg.cx += 1
        self.cfg.dirty += 1

    def insert_newline(self) -> None:
        filerow = self.cfg.rowoff + self.cfg.cy
        filecol = self.cfg.coloff + self.cfg.cx
        row = self.cfg.rows[filerow] if filerow < self.cfg.numrows else None

        if row is None:
            if filerow == self.cfg.numrows:
                self.insert_row(filerow, "")
            else:
                return
        else:
            if filecol >= row.size:
                filecol = row.size
            if filecol == 0:
                self.insert_row(filerow, "")
            else:
                self.insert_row(filerow + 1, row.chars[filecol:])
                row = self.cfg.rows[filerow]
                row.chars = row.chars[:filecol]
                self.update_row(row)

        if self.cfg.cy == self.cfg.screenrows - 1:
            self.cfg.rowoff += 1
        else:
            self.cfg.cy += 1
        self.cfg.cx = 0
        self.cfg.coloff = 0

    def del_char(self) -> None:
        filerow = self.cfg.rowoff + self.cfg.cy
        filecol = self.cfg.coloff + self.cfg.cx
        row = self.cfg.rows[filerow] if filerow < self.cfg.numrows else None
        if row is None or (filecol == 0 and filerow == 0):
            return

        if filecol == 0:
            filecol = self.cfg.rows[filerow - 1].size
            self.row_append_string(self.cfg.rows[filerow - 1], row.chars)
            self.del_row(filerow)
            row = None
            if self.cfg.cy == 0:
                self.cfg.rowoff -= 1
            else:
                self.cfg.cy -= 1
            self.cfg.cx = filecol
            if self.cfg.cx >= self.cfg.screencols:
                shift = (self.cfg.screencols - self.cfg.cx) + 1
                self.cfg.cx -= shift
                self.cfg.coloff += shift
        else:
            self.row_del_char(row, filecol - 1)
            if self.cfg.cx == 0 and self.cfg.coloff:
                self.cfg.coloff -= 1
            else:
                self.cfg.cx -= 1

        if row is not None:
            self.update_row(row)
        self.cfg.dirty += 1

    def open_file(self, filename: str) -> int:
        self.cfg.dirty = 0
        self.cfg.filename = filename
        try:
            with open(filename, "rb") as f:
                while True:
                    line = f.readline()
                    if line == b"":
                        break
                    if line and (line[-1] == 0x0A or line[-1] == 0x0D):
                        line = line[:-1]
                    self.insert_row(self.cfg.numrows, line.decode("latin-1"))
        except FileNotFoundError:
            return 1
        except OSError as exc:
            raise OSError(exc.errno, f"Opening file failed: {filename}") from exc
        self.cfg.dirty = 0
        return 0

    def save(self) -> int:
        if not self.cfg.filename:
            self.set_status_message("Can't save! No filename.")
            return 1

        data = self._to_c_bytes(self.rows_to_string())
        fd = -1
        try:
            fd = os.open(self.cfg.filename, os.O_RDWR | os.O_CREAT, 0o644)
            os.ftruncate(fd, len(data))
            written = 0
            while written < len(data):
                n = os.write(fd, data[written:])
                if n <= 0:
                    raise OSError(errno.EIO, "short write")
                written += n
        except OSError as exc:
            if fd != -1:
                os.close(fd)
            self.set_status_message("Can't save! I/O error: %s", os.strerror(exc.errno or errno.EIO))
            return 1

        os.close(fd)
        self.cfg.dirty = 0
        self.set_status_message("%d bytes written on disk", len(data))
        return 0

    def refresh_screen(self) -> None:
        refresh_screen(self)

    def find(self, fd: int) -> None:
        find(self, fd)

    def move_cursor(self, key: int) -> None:
        filerow = self.cfg.rowoff + self.cfg.cy
        filecol = self.cfg.coloff + self.cfg.cx
        row = self.cfg.rows[filerow] if filerow < self.cfg.numrows else None

        if key == ARROW_LEFT:
            if self.cfg.cx == 0:
                if self.cfg.coloff:
                    self.cfg.coloff -= 1
                elif filerow > 0:
                    self.cfg.cy -= 1
                    self.cfg.cx = self.cfg.rows[filerow - 1].size
                    if self.cfg.cx > self.cfg.screencols - 1:
                        self.cfg.coloff = self.cfg.cx - self.cfg.screencols + 1
                        self.cfg.cx = self.cfg.screencols - 1
            else:
                self.cfg.cx -= 1
        elif key == ARROW_RIGHT:
            if row is not None and filecol < row.size:
                if self.cfg.cx == self.cfg.screencols - 1:
                    self.cfg.coloff += 1
                else:
                    self.cfg.cx += 1
            elif row is not None and filecol == row.size:
                self.cfg.cx = 0
                self.cfg.coloff = 0
                if self.cfg.cy == self.cfg.screenrows - 1:
                    self.cfg.rowoff += 1
                else:
                    self.cfg.cy += 1
        elif key == ARROW_UP:
            if self.cfg.cy == 0:
                if self.cfg.rowoff:
                    self.cfg.rowoff -= 1
            else:
                self.cfg.cy -= 1
        elif key == ARROW_DOWN:
            if filerow < self.cfg.numrows:
                if self.cfg.cy == self.cfg.screenrows - 1:
                    self.cfg.rowoff += 1
                else:
                    self.cfg.cy += 1

        filerow = self.cfg.rowoff + self.cfg.cy
        filecol = self.cfg.coloff + self.cfg.cx
        row = self.cfg.rows[filerow] if filerow < self.cfg.numrows else None
        rowlen = row.size if row is not None else 0
        if filecol > rowlen:
            self.cfg.cx -= filecol - rowlen
            if self.cfg.cx < 0:
                self.cfg.coloff += self.cfg.cx
                self.cfg.cx = 0

    def process_keypress(self, fd: int) -> None:
        c = read_key(fd)
        if c == ENTER:
            self.insert_newline()
        elif c == CTRL_C:
            pass
        elif c == CTRL_Q:
            if self.cfg.dirty and self.quit_times:
                self.set_status_message(
                    "WARNING!!! File has unsaved changes. Press Ctrl-Q %d more times to quit.",
                    self.quit_times,
                )
                self.quit_times -= 1
                return
            raise SystemExit(0)
        elif c == CTRL_S:
            self.save()
        elif c == CTRL_F:
            self.find(fd)
        elif c in (BACKSPACE, CTRL_H, DEL_KEY):
            self.del_char()
        elif c in (PAGE_UP, PAGE_DOWN):
            if c == PAGE_UP and self.cfg.cy != 0:
                self.cfg.cy = 0
            elif c == PAGE_DOWN and self.cfg.cy != self.cfg.screenrows - 1:
                self.cfg.cy = self.cfg.screenrows - 1
            times = self.cfg.screenrows
            while times > 0:
                self.move_cursor(ARROW_UP if c == PAGE_UP else ARROW_DOWN)
                times -= 1
        elif c in (ARROW_UP, ARROW_DOWN, ARROW_LEFT, ARROW_RIGHT):
            self.move_cursor(c)
        elif c in (CTRL_L, ESC):
            pass
        else:
            self.insert_char(c)

        self.quit_times = KILO_QUIT_TIMES

    def file_was_modified(self) -> bool:
        return bool(self.cfg.dirty)


def run(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Usage: kilo <filename>", file=sys.stderr)
        return 1
    if not os.isatty(STDIN_FD) or not os.isatty(STDOUT_FD):
        print("kilo: stdin/stdout must be a tty", file=sys.stderr)
        return 1

    editor = Editor()
    filename = args[0]
    editor.select_syntax_highlight(filename)
    editor.open_file(filename)

    signal.signal(signal.SIGWINCH, editor.handle_sigwinch)
    try:
        with RawMode(STDIN_FD):
            editor.set_status_message("HELP: Ctrl-S = save | Ctrl-Q = quit | Ctrl-F = find")
            while True:
                editor.refresh_screen()
                editor.process_keypress(STDIN_FD)
    except OSError as exc:
        if exc.errno == errno.ENOTTY:
            print("kilo: stdin is not a tty", file=sys.stderr)
            return 1
        raise
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 0
