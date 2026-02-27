# Unrelated Musings

These notes capture side discussions from development chats.

They are intentionally out of scope for the `kilo-py` implementation plan in [../plan.md](/home/vega/Coding/Training/kilo-py/docs/plan.md), which focuses on a Python implementation of Kilo LISP.

## Topics Discussed

## 1) How minimal Kilo LISP is
- Kilo LISP is very minimal while still practical.
- It has a small symbolic core and builds higher-level behavior from derived forms.

## 2) Scheme vs Kilo LISP
- Scheme is generally much larger in standardized surface area and library expectations.
- Kilo LISP is closer to a compact kernel language.

## 3) "Smallest possible Lisp" question
- There is no single absolute smallest Lisp across all criteria.
- You can make smaller cores than Kilo LISP by sacrificing usability, ergonomics, or runtime features.

## 4) Lambda-calculus-level cores
- Lambda-calculus-only cores are elegant but often operationally inefficient for everyday programming due to encoding overhead.
- Practical Lisps include richer primitives to avoid this cost.

## 5) FA-first language idea
- Some systems are rooted in automata execution models (regex engines, lexer generators, FSM DSLs, synchronous/reactive tools).
- For general-purpose programming, pure finite automata are too weak for unbounded recursion/stack-like behavior.

## 6) State explosion and mitigation
- Modeling fixed-width values as finite graphs is possible, but state space can blow up when variables interact.
- Typical mitigation strategies:
  - symbolic representations (BDD/SAT/SMT)
  - slicing (cone-of-influence)
  - abstraction/refinement (CEGAR)
  - partial-order reduction
  - bounded and on-the-fly exploration

## Relevance Note
- Interesting architecture and PL theory ideas, but not part of current `kilo-py` delivery scope.
