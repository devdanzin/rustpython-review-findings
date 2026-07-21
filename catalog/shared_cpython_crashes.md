# Shared CPython crash ledger

When the CPython differential finds that **CPython also crashes** on an input, that is **not**
proof the behaviour is intended. CPython crashing can be an *unreported* — or reported-and-being-
fixed — bug in **both** interpreters. This session proved it: a RustPython `genericalias.__parameters__`
SIGSEGV that "matches CPython" turned out to be CPython bug **#154275** (open, with fix PR #154277).

So a "both crash" result must be split, and **every shared crash checked against the CPython tracker**:

- **ACCEPTABLE-by-contract** — the crash is CPython's *documented intent*: a C-API function whose
  contract says "caller must pass a valid/non-NULL pointer", or `ctypes` dereferencing a
  small-int-as-pointer (`ctypes` is `unsafe`-by-design). Genuinely fine; not a bug in either.
- **SHARED-BUG** — a **pure-Python-reachable** segfault/abort that should never happen in *either*
  interpreter. A bug in both: fix RustPython, and file/track the CPython side.

This closes a real trap: the recursion-guard agent initially dismissed the genericalias crash as
"both crash → not a RustPython bug." #154275 shows that dismissal was wrong.

## Ledger (whole-tree v0.2 run, RustPython `3290f287f` vs CPython 3.14.4)

| Shared crash | Reachable from | RustPython | CPython | CPython tracker | Verdict / action |
|---|---|---|---|---|---|
| `L=[]; L.append(L); list[L].__parameters__` (self-referential generic-alias arg → `make_parameters` unbounded recursion) | **pure Python** | SIGSEGV (139) | SIGSEGV (139) | **REPORTED — [#154275](https://github.com/python/cpython/issues/154275)** (open; fix PR #154277 adds `Py_EnterRecursiveCall`) | **SHARED-BUG.** RustPython: guard `make_parameters`/`subs_parameters` with `with_recursion` (it already guards repr/compare) — recorded as **RPYR-0015**. RustPython umbrella: **#2796** ("Recursions in rust code trigger segmentation faults" = fuzzer RUSTPY-0007a). RustPython crashes on strictly more inputs (eager params): bare `list[L]` SIGSEGVs RustPython, CPython only on `.__parameters__`. Will *diverge* once CPython's fix lands. |
| `hash()` of a deeply-nested `tuple` (unguarded `tuple_hash` element recursion), incl. `types.GenericAlias.__hash__` which routes through the args-tuple hash | **pure Python** | SIGSEGV (~200–300k deep) | SIGSEGV (~250k deep, 8 MB stack) | **TRACKER CHECKED 2026-07-20 → NOVEL.** No open/closed issue for tuple-hash recursion; repr sibling fixed 2007 (#44763), comparison guarded (`" in comparison"`), hash never was. ASan on `main` (3.16.0a0) names the frame: `tuple_hash` at `tupleobject.c:385`. Draft ready: `catalog/cpython-issue-tuple_hash-recursion.md`. | **SHARED-BUG — file upstream** (draft prepared; companion to #154275). RustPython should guard tuple `hash` with `with_recursion`. **Corrections to earlier note:** `typing.Union`/`X\|None` hash do NOT crash (survive to 1M); `frozenset` hash is unaffected (order-independent, iterative, cached); RustPython is *not* more robust than CPython — both overflow at a comparable depth. |
| `PyObject_GetItem`/`Size`/`SetItem`/`DelItem`, `PySequence_*`, `PyMapping_Check`/`Size` on a NULL argument (~30 capi fns) | **C caller only** | segfault | CPython `null_error()`s → returns -1/NULL + `SystemError`, or short-circuits | (behaviour differs) | **RustPython-unique divergence** (not a shared crash). Harden at the `with_vm` boundary with a `null_error`-equivalent guard. Instructive pair: `PySequence_Check(NULL)` segfaults in **both** (ACCEPTABLE) but `PyMapping_Check(NULL)` returns `0` in CPython (DIVERGENT). |
| `Py_TYPE(arg)`-immediate capi fns on NULL (~210: number/attribute/dict/call protocols) | **C caller only** | segfault | segfault | documented C-API contract (caller must pass non-NULL) | **ACCEPTABLE-by-contract.** Both segfault by design. |
| `ctypes.c_void_p(12345)` dereferenced as a pointer | pure Python, but `ctypes` is `unsafe`-by-design | segfault | segfault | intended (`objc_getClass(12345)` segfaults CPython too) | **ACCEPTABLE-by-contract.** Only a *divergence* (CPython raises where RustPython crashes) counts — see RUSTPY-0024, which is that divergence. |

## Standing practice

1. Never file a "both crash" case as ACCEPTABLE without checking whether the crash is CPython's
   *documented intent* (C-API contract / `ctypes` unsafety) vs a latent bug.
2. For every **pure-Python-reachable** shared crash: search the CPython tracker; if unreported,
   file it upstream, and fix the RustPython side regardless (a Python program should never
   segfault the interpreter, in either implementation).
3. Record the outcome here so a future reviewer does not re-investigate — and so the "fix
   RustPython too" argument is anchored to the CPython issue (as #154275 anchors `make_parameters`).
