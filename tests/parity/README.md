# Parity Suite

This suite compares `src/main.py` (Python Kilo) against `ref/kilo` (C reference) by replaying the same terminal key sequences in a PTY.

## What is asserted
- `file_bytes`: final file bytes are identical.
- `exit_summary`: both processes exit the same way (`exit:N`, `signal:N`, or `timeout`).

The suite supports `transcript_bytes` assertions as well, but that is off by default because terminal transcripts can be noisy across implementations.

## Run
```bash
python3 tests/parity/run_parity.py
```

The runner builds `ref/kilo` automatically if `ref/kilo` is missing.

## Case file schema
Each case is JSON in `tests/parity/cases/*.json`.

- `name`: case label.
- `initial_text`: initial file contents (UTF-8 text).
- `initial_bytes_hex`: optional raw bytes initializer (overrides `initial_text` when set).
- `actions`: ordered list of key/text actions.
- `assert_equal`: list of outputs to compare (`file_bytes`, `exit_summary`, `transcript_bytes`).
- `timeout_s`: max session duration per implementation.
- `auto_quit_presses`: extra `Ctrl-Q` presses sent after actions.

Action formats:
- `{"type":"text","value":"hello"}`
- `{"type":"bytes_hex","value":"1b5b41"}`
- `{"type":"key","value":"CTRL_S"}`
- `{"type":"wait","sleep_ms":120}`

Supported key values:
- `ENTER`, `ESC`, `BACKSPACE`, `TAB`
- `UP`, `DOWN`, `LEFT`, `RIGHT`
- `HOME`, `END`, `DEL`, `PAGE_UP`, `PAGE_DOWN`
- `CTRL_<letter>` such as `CTRL_Q`, `CTRL_S`, `CTRL_F`
