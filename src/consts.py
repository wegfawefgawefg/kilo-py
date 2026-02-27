from __future__ import annotations

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

SEARCH_CONTINUE = 0
SEARCH_CANCEL = 1
SEARCH_ACCEPT = 2
SEARCH_RUN = 3


def ctrl(ch: str) -> int:
    return ord(ch.upper()) & 0x1F


CTRL_Q = ctrl("q")
CTRL_S = ctrl("s")
CTRL_F = ctrl("f")
CTRL_A = ctrl("a")
CTRL_E = ctrl("e")
CTRL_H = ctrl("h")
CTRL_L = ctrl("l")
