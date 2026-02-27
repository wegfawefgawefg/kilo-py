from __future__ import annotations

import signal
import sys

from controller import open_file, process_keypress, refresh_screen, resize, set_status
from consts import State
from terminal import RawMode


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python3 src/main.py <filename>", file=sys.stderr)
        return 1
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("kilo-py requires a real terminal (TTY).", file=sys.stderr)
        return 1

    state = State(
        filename=argv[1],
        stdin_fd=sys.stdin.fileno(),
        stdout_fd=sys.stdout.fileno(),
    )
    resize(state)
    open_file(state)
    set_status(state, "HELP: Ctrl-S save | Ctrl-Q quit | Ctrl-F find")

    def on_resize(_signum: int, _frame) -> None:
        resize(state)
        refresh_screen(state)

    signal.signal(signal.SIGWINCH, on_resize)
    with RawMode(state.stdin_fd):
        while True:
            refresh_screen(state)
            if process_keypress(state):
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
