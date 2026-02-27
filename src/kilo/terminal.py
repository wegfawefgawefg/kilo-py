from __future__ import annotations

import errno
import fcntl
import os
import re
import struct
import termios
from contextlib import AbstractContextManager

from .constants import (
    ARROW_DOWN,
    ARROW_LEFT,
    ARROW_RIGHT,
    ARROW_UP,
    DEL_KEY,
    END_KEY,
    ESC,
    HOME_KEY,
    PAGE_DOWN,
    PAGE_UP,
)


def _read_byte_once(fd: int) -> int | None:
    try:
        data = os.read(fd, 1)
    except InterruptedError:
        return None
    if not data:
        return None
    return data[0]


def _read_byte_blocking(fd: int) -> int:
    while True:
        c = _read_byte_once(fd)
        if c is not None:
            return c


def read_key(fd: int) -> int:
    c = _read_byte_blocking(fd)
    if c != ESC:
        return c

    seq0 = _read_byte_once(fd)
    if seq0 is None:
        return ESC
    seq1 = _read_byte_once(fd)
    if seq1 is None:
        return ESC

    if seq0 == ord("["):
        if ord("0") <= seq1 <= ord("9"):
            seq2 = _read_byte_once(fd)
            if seq2 is None:
                return ESC
            if seq2 == ord("~"):
                if seq1 == ord("3"):
                    return DEL_KEY
                if seq1 == ord("5"):
                    return PAGE_UP
                if seq1 == ord("6"):
                    return PAGE_DOWN
        else:
            if seq1 == ord("A"):
                return ARROW_UP
            if seq1 == ord("B"):
                return ARROW_DOWN
            if seq1 == ord("C"):
                return ARROW_RIGHT
            if seq1 == ord("D"):
                return ARROW_LEFT
            if seq1 == ord("H"):
                return HOME_KEY
            if seq1 == ord("F"):
                return END_KEY
    elif seq0 == ord("O"):
        if seq1 == ord("H"):
            return HOME_KEY
        if seq1 == ord("F"):
            return END_KEY
    return ESC


def get_cursor_position(ifd: int, ofd: int) -> tuple[int, int]:
    if os.write(ofd, b"\x1b[6n") != 4:
        raise OSError(errno.EIO, "cursor query write failed")

    buf = bytearray()
    while len(buf) < 31:
        c = _read_byte_once(ifd)
        if c is None:
            break
        buf.append(c)
        if c == ord("R"):
            break

    match = re.match(rb"\x1b\[(\d+);(\d+)R", bytes(buf))
    if not match:
        raise OSError(errno.EIO, "invalid cursor position response")
    return int(match.group(1)), int(match.group(2))


def get_window_size(ifd: int, ofd: int) -> tuple[int, int]:
    try:
        packed = fcntl.ioctl(ofd, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        rows, cols, _, _ = struct.unpack("HHHH", packed)
        if cols:
            return rows, cols
    except OSError:
        pass

    orig_row, orig_col = get_cursor_position(ifd, ofd)
    if os.write(ofd, b"\x1b[999C\x1b[999B") != 12:
        raise OSError(errno.EIO, "window query write failed")
    rows, cols = get_cursor_position(ifd, ofd)
    restore = f"\x1b[{orig_row};{orig_col}H".encode()
    os.write(ofd, restore)
    return rows, cols


class RawMode(AbstractContextManager["RawMode"]):
    def __init__(self, fd: int) -> None:
        self.fd = fd
        self._orig: list[int] | None = None

    def __enter__(self) -> "RawMode":
        if not os.isatty(self.fd):
            raise OSError(errno.ENOTTY, "stdin is not a tty")

        self._orig = termios.tcgetattr(self.fd)
        raw = termios.tcgetattr(self.fd)
        raw[0] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON)
        raw[1] &= ~termios.OPOST
        raw[2] |= termios.CS8
        raw[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
        raw[6][termios.VMIN] = 0
        raw[6][termios.VTIME] = 1
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, raw)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._orig is not None:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self._orig)
