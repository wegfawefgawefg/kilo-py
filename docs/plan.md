# kilo-py Plan (Kilo LISP)

## Goal
Implement a Python version of Kilo LISP semantics, not the Kilo text editor.

## How Minimal Kilo LISP Is
- Purely symbolic language.
- Only two data types: atom (symbol) and pair/list.
- Truth values: `T` (true) and `NIL` (false/empty list).
- Lexical scope, tail call elimination, macros, image files.

## Language Keywords To Support
Core special forms:
- `APPLY`
- `IF`
- `IFNOT`
- `LAMBDA`
- `PROG`
- `QUOTE`
- `SETQ`

Derived forms:
- `LET`
- `LABELS`
- `COND`
- `AND`
- `OR`
- `QQUOTE`
- `LOOP`

## Predefined Functions To Support
Primitive:
- `ATOM`, `CAR`, `CDR`, `CONS`, `EQ`, `EOFP`, `ERROR`, `GC`, `GENSYM`, `LOAD`, `PRIN`, `PRIN1`, `PRINT`, `READ`, `SETCAR`, `SETCDR`, `SUSPEND`

Derived:
- `ASSOC`, `CAAR ... CDDDR`, `CONC`, `EQUAL`, `LIST`, `MAP`, `MEMB`, `NOT`, `NCONC`, `NRECONC`, `NREVER`, `NULL`, `RECONC`, `REVER`

## Reader Syntax Features
- `'x` -> `(QUOTE x)`
- `@x` -> `(QQUOTE x)`
- `,x` -> `(UNQUOTE x)`
- `,@x` -> `(SPLICE x)`
- `#xyz` -> `(QUOTE (x y z))`

## Python Implementation Milestones
1. Data model and reader
   - Symbol interning.
   - Pair/cons cell representation.
   - Parser for dotted pairs and sugar forms.
2. Evaluator core
   - Environments and lexical scoping.
   - Core special forms with correct evaluation rules.
3. Function layer
   - Primitive functions.
   - Derived functions/forms from a bootstrap prelude.
4. Runtime
   - REPL.
   - `(LOAD ...)`.
   - Suspend/save image hook points (can be stubbed first).
5. Verification
   - Golden tests for reader, evaluator, and macro behavior.
   - Tail-call stress tests.

## Suggested Layout
- `src/main.py` - CLI entrypoint + REPL
- `src/reader.py` - tokenization/parser
- `src/runtime.py` - symbols, pairs, printer
- `src/eval.py` - evaluator + special forms
- `src/primitives.py` - primitive builtins
- `src/prelude.kl` - derived forms/functions
- `tests/` - unit and integration tests
