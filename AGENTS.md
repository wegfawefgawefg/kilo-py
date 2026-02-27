# Project Agent Rules

These rules apply to code produced in this repository.

## Philosophy
- Prefer a minimal, Python-first implementation over strict C-byte parity.
- Keep the editor genuinely usable: open, edit, save, search, quit safely.
- Optimize for clarity and small code size.

## Size and Structure
- Keep the core editor in as few files as practical.
- A compact single-file implementation is acceptable.
- Split only when complexity clearly justifies it.

## Behavior Goals
- Match Kilo's user-facing workflow where reasonable.
- Do not add heavy abstractions unless they remove real complexity.
- Favor straightforward terminal logic over framework-style design.
