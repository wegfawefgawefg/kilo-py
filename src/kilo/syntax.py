from __future__ import annotations

from .constants import (
    C_HL_EXTENSIONS,
    C_HL_KEYWORDS,
    HL_COMMENT,
    HL_HIGHLIGHT_NUMBERS,
    HL_HIGHLIGHT_STRINGS,
    HL_KEYWORD1,
    HL_KEYWORD2,
    HL_MATCH,
    HL_MLCOMMENT,
    HL_NONPRINT,
    HL_NORMAL,
    HL_NUMBER,
    HL_STRING,
)
from .models import EditorConfig, EditorSyntax, Row


HLDB: tuple[EditorSyntax, ...] = (
    EditorSyntax(
        filematch=C_HL_EXTENSIONS,
        keywords=C_HL_KEYWORDS,
        singleline_comment_start="//",
        multiline_comment_start="/*",
        multiline_comment_end="*/",
        flags=HL_HIGHLIGHT_STRINGS | HL_HIGHLIGHT_NUMBERS,
    ),
)


def is_separator(c: str) -> bool:
    return not c or c.isspace() or c in ",.()+-/*=~%[];"


def row_has_open_comment(row: Row) -> bool:
    if not row.hl or not row.rsize:
        return False
    if row.hl[row.rsize - 1] != HL_MLCOMMENT:
        return False
    if row.rsize < 2:
        return True
    return not (row.render[row.rsize - 2] == "*" and row.render[row.rsize - 1] == "/")


def syntax_to_color(hl: int) -> int:
    if hl in (HL_COMMENT, HL_MLCOMMENT):
        return 36
    if hl == HL_KEYWORD1:
        return 33
    if hl == HL_KEYWORD2:
        return 32
    if hl == HL_STRING:
        return 35
    if hl == HL_NUMBER:
        return 31
    if hl == HL_MATCH:
        return 34
    return 37


def select_syntax_highlight(config: EditorConfig, filename: str) -> None:
    config.syntax = None
    for syntax in HLDB:
        for pattern in syntax.filematch:
            pos = filename.find(pattern)
            if pos == -1:
                continue
            if pattern.startswith("."):
                if filename.endswith(pattern):
                    config.syntax = syntax
                    return
            else:
                config.syntax = syntax
                return


def _propagate(config: EditorConfig, idx: int) -> None:
    if idx + 1 >= config.numrows:
        return
    update_syntax(config, idx + 1)


def update_syntax(config: EditorConfig, idx: int) -> None:
    row = config.rows[idx]
    row.hl = [HL_NORMAL] * row.rsize
    if config.syntax is None:
        return

    syntax = config.syntax
    keywords = syntax.keywords
    scs = syntax.singleline_comment_start
    mcs = syntax.multiline_comment_start
    mce = syntax.multiline_comment_end

    p = row.render
    i = 0
    while i < len(p) and p[i].isspace():
        i += 1

    prev_sep = True
    in_string = ""
    in_comment = False
    if row.idx > 0 and row_has_open_comment(config.rows[row.idx - 1]):
        in_comment = True

    while i < len(p):
        ch = p[i]
        next_ch = p[i + 1] if i + 1 < len(p) else ""

        if prev_sep and scs and ch == scs[0] and next_ch == scs[1]:
            for h in range(i, len(row.hl)):
                row.hl[h] = HL_COMMENT
            break

        if in_comment:
            row.hl[i] = HL_MLCOMMENT
            if mce and ch == mce[0] and next_ch == mce[1]:
                if i + 1 < len(row.hl):
                    row.hl[i + 1] = HL_MLCOMMENT
                i += 2
                in_comment = False
                prev_sep = True
                continue
            i += 1
            prev_sep = False
            continue

        if mcs and ch == mcs[0] and next_ch == mcs[1]:
            row.hl[i] = HL_MLCOMMENT
            if i + 1 < len(row.hl):
                row.hl[i + 1] = HL_MLCOMMENT
            i += 2
            in_comment = True
            prev_sep = False
            continue

        if in_string:
            row.hl[i] = HL_STRING
            if ch == "\\" and i + 1 < len(p):
                row.hl[i + 1] = HL_STRING
                i += 2
                prev_sep = False
                continue
            if ch == in_string:
                in_string = ""
            i += 1
            prev_sep = False
            continue

        if ch in ("'", '"'):
            in_string = ch
            row.hl[i] = HL_STRING
            i += 1
            prev_sep = False
            continue

        if not ch.isprintable():
            row.hl[i] = HL_NONPRINT
            i += 1
            prev_sep = False
            continue

        prev_hl = row.hl[i - 1] if i > 0 else HL_NORMAL
        if (ch.isdigit() and (prev_sep or prev_hl == HL_NUMBER)) or (
            ch == "." and i > 0 and prev_hl == HL_NUMBER
        ):
            row.hl[i] = HL_NUMBER
            i += 1
            prev_sep = False
            continue

        if prev_sep:
            matched = False
            for kw in keywords:
                kw2 = kw.endswith("|")
                token = kw[:-1] if kw2 else kw
                klen = len(token)
                segment = p[i : i + klen]
                tail = p[i + klen] if i + klen < len(p) else ""
                if segment == token and is_separator(tail):
                    mark = HL_KEYWORD2 if kw2 else HL_KEYWORD1
                    for h in range(i, i + klen):
                        row.hl[h] = mark
                    i += klen
                    matched = True
                    break
            if matched:
                prev_sep = False
                continue

        prev_sep = is_separator(ch)
        i += 1

    oc = row_has_open_comment(row)
    if row.hl_oc != oc:
        row.hl_oc = oc
        _propagate(config, idx)
