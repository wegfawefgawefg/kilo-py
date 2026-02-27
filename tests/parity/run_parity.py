from __future__ import annotations

import json
import os
import pty
import select
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "tests" / "parity" / "cases"
PY_KILO = ["python3", str(ROOT / "src" / "main.py")]
C_KILO = [str(ROOT / "ref" / "kilo")]


KEY_BYTES: dict[str, bytes] = {
    "ENTER": b"\r",
    "ESC": b"\x1b",
    "BACKSPACE": b"\x7f",
    "TAB": b"\t",
    "UP": b"\x1b[A",
    "DOWN": b"\x1b[B",
    "RIGHT": b"\x1b[C",
    "LEFT": b"\x1b[D",
    "HOME": b"\x1b[H",
    "END": b"\x1b[F",
    "DEL": b"\x1b[3~",
    "PAGE_UP": b"\x1b[5~",
    "PAGE_DOWN": b"\x1b[6~",
}


@dataclass(slots=True)
class SessionResult:
    status: int | None
    timed_out: bool
    transcript: bytes

    @property
    def exit_summary(self) -> str:
        if self.timed_out:
            return "timeout"
        if self.status is None:
            return "unknown"
        if os.WIFEXITED(self.status):
            return f"exit:{os.WEXITSTATUS(self.status)}"
        if os.WIFSIGNALED(self.status):
            return f"signal:{os.WTERMSIG(self.status)}"
        return f"raw:{self.status}"


def _ctrl(letter: str) -> bytes:
    if len(letter) != 1 or not letter.isalpha():
        raise ValueError(f"invalid CTRL key: {letter}")
    return bytes([ord(letter.upper()) & 0x1F])


def key_to_bytes(key: str) -> bytes:
    if key.startswith("CTRL_"):
        return _ctrl(key.split("_", 1)[1])
    try:
        return KEY_BYTES[key]
    except KeyError as exc:
        raise KeyError(f"unknown key: {key}") from exc


def read_ready(fd: int, sink: bytearray, duration_s: float) -> None:
    end = time.time() + duration_s
    while time.time() < end:
        readable, _, _ = select.select([fd], [], [], 0.02)
        if fd not in readable:
            continue
        try:
            data = os.read(fd, 65536)
        except OSError:
            break
        if not data:
            break
        sink.extend(data)


def run_session(
    cmd: list[str],
    filename: str,
    actions: list[dict[str, Any]],
    timeout_s: float,
    auto_quit_presses: int,
) -> SessionResult:
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(ROOT)
        os.execvp(cmd[0], cmd + [filename])

    transcript = bytearray()
    status: int | None = None
    timed_out = False
    try:
        time.sleep(0.2)
        read_ready(fd, transcript, 0.2)

        for action in actions:
            kind = action["type"]
            if kind == "text":
                os.write(fd, action["value"].encode())
            elif kind == "bytes_hex":
                os.write(fd, bytes.fromhex(action["value"]))
            elif kind == "key":
                os.write(fd, key_to_bytes(action["value"]))
            elif kind != "wait":
                raise ValueError(f"unknown action type: {kind}")

            sleep_ms = int(action.get("sleep_ms", 60))
            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000)
            read_ready(fd, transcript, 0.15)

        for _ in range(auto_quit_presses):
            try:
                os.write(fd, key_to_bytes("CTRL_Q"))
            except OSError:
                break
            time.sleep(0.05)
            read_ready(fd, transcript, 0.1)

        deadline = time.time() + timeout_s
        while time.time() < deadline:
            read_ready(fd, transcript, 0.05)
            wpid, status = os.waitpid(pid, os.WNOHANG)
            if wpid == pid:
                break
            time.sleep(0.02)

        if status is None:
            timed_out = True
            os.kill(pid, signal.SIGKILL)
            _, status = os.waitpid(pid, 0)
            read_ready(fd, transcript, 0.05)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass

    return SessionResult(status=status, timed_out=timed_out, transcript=bytes(transcript))


def ensure_c_kilo() -> None:
    kilo_bin = ROOT / "ref" / "kilo"
    if kilo_bin.exists():
        return
    rc = os.system(f"make -C {ROOT / 'ref'} >/dev/null")
    if rc != 0:
        raise SystemExit("failed to build ref/kilo")


def load_case(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        case = json.load(f)
    case.setdefault("assert_equal", ["file_bytes", "exit_summary"])
    case.setdefault("timeout_s", 3.0)
    case.setdefault("auto_quit_presses", 0)
    case.setdefault("initial_text", "")
    case.setdefault("initial_bytes_hex", "")
    return case


def run_case(case: dict[str, Any]) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        py_file = Path(td) / "py.txt"
        c_file = Path(td) / "c.txt"
        if case["initial_bytes_hex"]:
            initial = bytes.fromhex(case["initial_bytes_hex"])
        else:
            initial = case["initial_text"].encode()
        py_file.write_bytes(initial)
        c_file.write_bytes(initial)

        py = run_session(PY_KILO, str(py_file), case["actions"], case["timeout_s"], case["auto_quit_presses"])
        c = run_session(C_KILO, str(c_file), case["actions"], case["timeout_s"], case["auto_quit_presses"])

        py_bytes = py_file.read_bytes()
        c_bytes = c_file.read_bytes()

        failures: list[str] = []
        checks = set(case["assert_equal"])
        if "file_bytes" in checks and py_bytes != c_bytes:
            failures.append(f"file_bytes differ py={py_bytes!r} c={c_bytes!r}")
        if "exit_summary" in checks and py.exit_summary != c.exit_summary:
            failures.append(f"exit_summary differ py={py.exit_summary} c={c.exit_summary}")
        if "transcript_bytes" in checks and py.transcript != c.transcript:
            failures.append("transcript_bytes differ")

        if failures:
            return False, "; ".join(failures)
        return True, "ok"


def main() -> int:
    ensure_c_kilo()
    case_files = sorted(CASES_DIR.glob("*.json"))
    if not case_files:
        print("No parity cases found.", file=sys.stderr)
        return 1

    failed = 0
    for case_file in case_files:
        case = load_case(case_file)
        ok, reason = run_case(case)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case.get('name', case_file.stem)} ({case_file.name}) - {reason}")
        if not ok:
            failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
