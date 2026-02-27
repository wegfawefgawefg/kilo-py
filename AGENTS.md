# Project Agent Rules

These rules apply to code produced in this repository.

## File Size
- Keep source files between 300 and 500 lines when practical.
- If a file grows beyond 500 lines, split it by responsibility.
- Prefer several focused modules over one large file.

## Separation of Concerns
- Group related logic in dedicated files.
- Keep terminal I/O, editor state, syntax highlighting, and rendering separate.
- Avoid cross-cutting helpers in random places; place them in the owning module.

## Organization
- Prefer small, cohesive APIs between modules.
- Keep entrypoint files thin and orchestration-focused.
- Keep behavior faithful to original references unless explicitly changing semantics.
