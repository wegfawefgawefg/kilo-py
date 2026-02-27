# kilo-py Plan

## Goal
Build a minimal, usable terminal text editor in Python inspired by Kilo.

## Scope
- Core editing workflow:
  - open file
  - edit text
  - save file
  - search in file
  - quit with unsaved-change protection
- Keep code simple and understandable.
- Keep terminal behavior practical for common Linux/macOS terminals.

## Non-Goals
- Exact byte-for-byte parity with `ref/kilo.c`.
- Full syntax highlighting parity with upstream Kilo.
- Advanced editor features (multi-buffer, undo tree, plugins, LSP, etc.).

## Current Architecture
- `src/main.py`:
  - process startup, TTY checks, event loop wiring.
- `src/model.py`:
  - editor state dataclasses and key/constants.
- `src/terminal.py`:
  - raw mode and key decoding.
- `src/io_ops.py`:
  - resize, file open/save, status messages.
- `src/render.py`:
  - screen and status/message bar rendering.
- `src/actions.py`:
  - cursor movement and text mutations.
- `src/search.py`:
  - find-mode state machine.
- `src/controller.py`:
  - key dispatch and top-level input handling.

## Quality Bar
- Behavior should be predictable and safe (especially save/quit).
- Modules should stay focused by responsibility.
- Prefer clear function names and direct control flow over abstractions.
