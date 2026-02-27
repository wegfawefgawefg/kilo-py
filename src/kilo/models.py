from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EditorSyntax:
    filematch: tuple[str, ...]
    keywords: tuple[str, ...]
    singleline_comment_start: str
    multiline_comment_start: str
    multiline_comment_end: str
    flags: int


@dataclass(slots=True)
class Row:
    idx: int
    chars: str
    render: str = ""
    hl: list[int] = field(default_factory=list)
    hl_oc: bool = False

    @property
    def size(self) -> int:
        return len(self.chars)

    @property
    def rsize(self) -> int:
        return len(self.render)


@dataclass(slots=True)
class EditorConfig:
    cx: int = 0
    cy: int = 0
    rowoff: int = 0
    coloff: int = 0
    screenrows: int = 0
    screencols: int = 0
    rows: list[Row] = field(default_factory=list)
    dirty: int = 0
    filename: str | None = None
    statusmsg: str = ""
    statusmsg_time: float = 0.0
    syntax: EditorSyntax | None = None

    @property
    def numrows(self) -> int:
        return len(self.rows)
