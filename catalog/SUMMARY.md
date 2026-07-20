# RustPython static-review findings — summary

Snapshot: 2026-07-20 · RustPython `0.5.0` · static review against source `3290f287f`, reproduced
on the `a9c2c529b` binary · **7 reproduced bugs (RPYR-0001…0007) + 1 lead (RPYR-0008)**.

**Method.** Static review with [rustpy-review-toolkit](https://github.com/devdanzin/rustpy-review-toolkit):
tree-sitter-rust scanners find high-recall candidates; per-aspect agents triage each by reading
the real code, ranking Python-reachability, and reproducing on the interpreter binary. One
report per bug under `reports/RPYR-####-*/` (`report.md`, `repro.py`, `panic.txt`, `meta.json`).
Disjoint from the `fusil` fuzzing catalog in `rustpython-findings` (`RUSTPY-*`).

**Legend**
- **Kind** — `panic` (Rust `panic!` unwinds/aborts the interpreter) · `abort` (SIGABRT, usually
  an allocator abort) · `segv`.
- **Found by** — the toolkit agent that surfaced it. `git-history-analyzer` entries are bugs the
  *pattern scanner cannot see* (arithmetic/allocation, no `.unwrap()` token) — caught by
  similar-bug detection against a recently-fixed twin.

| ID | Title | Kind | Site | Found by | CPython does |
|----|-------|------|------|----------|--------------|
| RPYR-0001 | `ImportError().__reduce__()` unwraps empty args | panic | `exceptions.rs:1872` | panic-site-auditor | returns `(ImportError, ())` |
| RPYR-0002 | `current_task()` downcasts reassignable `_current_tasks` | panic | `_asyncio.rs:2408` | panic-site + history | no crash |
| RPYR-0003 | `FutureIter.throw()` downcasts a `__new__`-foreign result | panic | `_asyncio.rs:1081` | scanner (+ history) | raises `TypeError` |
| RPYR-0004 | `mmap.find`/`rfind` slice-panic when `start > end` | panic | `mmap.rs:795`,`812` | panic-site-auditor | returns `-1` |
| RPYR-0005 | `mmap.move(dest>size)` underflow → OOB slice | panic | `mmap.rs:903` | **history** | raises `ValueError` |
| RPYR-0006 | `deque * n` missing memory-size overflow guard | panic | `_collections.rs:317` | **history** | raises `MemoryError` |
| RPYR-0007 | shared `SequenceExt::mul` guard-hole → SIGABRT | abort | `sequence.rs:107` | panic-site (Phase-4) | raises `MemoryError` |
| RPYR-0008 | `new_invalid_state_error` downcasts a `.call()` result | panic (lead) | `_asyncio.rs:2737` | history | raises `InvalidStateError` |

## The recurring shape

Every reproduced bug is a **latent DoS in never-bug-fixed code**, and **every one has a
correctly-guarded twin in the same file** — the fix pattern is already present next door:

- RPYR-0001 → `OSError.__reduce__` guards with `args.len() >= 2`.
- RPYR-0002 → `_enter_task`/`_leave_task`/`_swap_current_task` use `if let Ok(dict) = ...`.
- RPYR-0003 → the `map_err` downcast idiom at five other `_asyncio.rs` sites.
- RPYR-0004 → the `read`/`read_byte`/`readline` accessors clamp their bounds.
- RPYR-0005 → `write()` checks `pos > size || size - pos < len` first.
- RPYR-0006 → `SequenceExt::mul` has the guard (added in RustPython #8270, 4 days prior).
- RPYR-0007 → is the shared guard; the hole is one `try_reserve` away.

This "guarded-twin asymmetry" is the highest-signal heuristic a static reviewer has on this
codebase, and it is what the history agent's similar-bug detection keys on.

## Toolkit meta-evaluation byproducts

Running the full agent panel per file also validated and calibrated the toolkit itself — the
false-positive classes it surfaced are catalogued in [`non_bugs.md`](non_bugs.md), and several
became scanner calibrations (the panic-site FIX false-positive rate fell as each class was
fixed: `exceptions.rs` 0/14 real, `_asyncio.rs` 2/9→2/2 after calibration, `mmap.rs` 2/5,
`tuple.rs` 0/1).
