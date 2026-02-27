from __future__ import annotations

import os
import termios

from model import (
    CSI_SIMPLE_MAP,
    CSI_TILDE_MAP,
    ESC,
    SS3_SIMPLE_MAP,
)


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
