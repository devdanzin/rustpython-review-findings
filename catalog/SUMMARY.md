# RustPython static-review findings — summary

Snapshot: 2026-07-20 · RustPython `0.5.0` · static review against source `3290f287f`, reproduced
on the `a9c2c529b` binary · **11 reproduced bugs (RPYR-0001…0007, 0009…0012) + 1 lead (RPYR-0008)**.
RPYR-0009/0010 came from the first **whole-tree** run (v0.1, six agents); **RPYR-0011/0012 came
from the v0.2 whole-tree run** (all thirteen agents — the seven class-expansion agents' debut),
which also reproduced live several fuzzer-catalog crashes (0008 uninit, 0017/0024 ctypes, 0018-I
debug-format, 0012–0016 eager-collect) and produced the **[shared-CPython-crash ledger](shared_cpython_crashes.md)**
— a discipline for "both interpreters crash" cases (a RustPython crash that "matches CPython" may
be an unreported bug in both; the genericalias `make_parameters` case is CPython #154275).

**Method.** Static review with [rustpy-review-toolkit](https://github.com/devdanzin/rustpy-review-toolkit):
tree-sitter-rust scanners find high-recall candidates; per-aspect agents triage each by reading
the real code, ranking Python-reachability, and reproducing on the interpreter binary. One
report per bug under `reports/RPYR-####-*/` (`report.md`, `repro.py`, `panic.txt`, `meta.json`).
Disjoint from the `fusil` fuzzing catalog in `rustpython-findings` (`RUSTPY-*`).

**Legend**
- **Kind** — `panic` (Rust `panic!` unwinds/aborts the interpreter) · `abort` (SIGABRT, usually
  an allocator abort) · `segv` · `leak` (an uncollectable reference cycle — no crash, but memory
  grows unbounded and finalizers never run; proven with a weakref/`__del__` differential oracle).
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
| RPYR-0009 | `itertools.combinations`/`_with_replacement`/`permutations(r=2**64)` int-narrow | panic | `itertools.rs:1205`,`1306`,`1412` | panic-site + history | raises `OverflowError` |
| RPYR-0010 | `deque`/`defaultdict` leak reference cycles (no GC traverse) | leak | `_collections.rs:33`,`759` | gc-traverse + history | collects the cycle |
| RPYR-0011 | `math.sumprod` big-int generic path eager-collects both iterables | abort | `math.rs:733`,`735` | eager-collect-parity | streams at O(1) memory |
| RPYR-0012 | `itertools.cycle` (+ the itertools cluster) leak reference cycles (no GC traverse) | leak | `itertools.rs:242` | gc-traverse + history | collects the cycle |

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
- RPYR-0009 → the **negative** side is already guarded in the same function
  (`if r.is_negative() { return Err(...) }`); the too-large side is one symmetric guard away, and
  every other `to_usize()` in stdlib discharges the `Option` with `?` (maintainer-fixed twin: #6561).
- RPYR-0010 → the twin is a *sibling type* rather than a line next door: `list`/`dict`/`tuple`/`set`
  all declare `traverse` and their cycles collect (verified in the same harness); `deque`/`defaultdict`
  are the two `_collections` payloads the Jan-2026 traverse migration (#6780) missed.

This "guarded-twin asymmetry" is the highest-signal heuristic a static reviewer has on this
codebase, and it is what the history agent's similar-bug detection keys on. RPYR-0010 shows the
same asymmetry one level up — a whole *type* that forgot the opt-in its siblings have.

## Toolkit meta-evaluation byproducts

Running the full agent panel per file also validated and calibrated the toolkit itself — the
false-positive classes it surfaced are catalogued in [`non_bugs.md`](non_bugs.md), and several
became scanner calibrations (the panic-site FIX false-positive rate fell as each class was
fixed: `exceptions.rs` 0/14 real, `_asyncio.rs` 2/9→2/2 after calibration, `mmap.rs` 2/5,
`tuple.rs` 0/1).

The first **whole-tree** run (all six agents on all 472 files at once) then stress-tested the
toolkit at scale. Result: the design holds — the reachability tier default-silenced 91% of panic
sites, and the panic auditor's 25-finding cap lost no real signal (raw 42 FIX collapse to 9
genuine after triage; all fit the cap). Only two new bugs cleared the higher whole-tree bar and
were reproduced: **RPYR-0009** (found by the int-narrowing signal; history proved the three sites
are the complete tree-wide population and have a maintainer-fixed twin) and **RPYR-0010** (the
gc-traverse auditor's first confirmed instance, dated by history to an incomplete Jan-2026
migration). The whole-tree run also produced a calibration lead — 30 panic false positives in six
recurring shapes, two of which (owner-downcast in `#[pyslot]` methods, same-line `&&` guards)
would reclaim 12 of them — recorded for the next toolkit-calibration cycle.
