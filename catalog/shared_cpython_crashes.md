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
| `L=[]; L.append(L); list[L].__parameters__` (self-referential generic-alias arg → `make_parameters` unbounded recursion) | **pure Python** | SIGSEGV (139) | SIGSEGV (139) | **REPORTED — [#154275](https://github.com/python/cpython/issues/154275)** (open; fix PR #154277 adds `Py_EnterRecursiveCall`) | **SHARED-BUG.** RustPython: guard `make_parameters`/`subs_parameters` with `with_recursion` (it already guards repr/compare). RustPython umbrella: **#4862**. Will *diverge* once CPython's fix lands. |
| `hash()` of a deeply-nested `types.GenericAlias`/`union`/`tuple` (unguarded `ga_hash`/`tuplehash` element recursion) | **pure Python** | SIGSEGV (deep) | SIGSEGV (deep) | **no clear open issue found** (only old/closed relatives: repr-of-nested-dicts #32137, itertools #14010) → **likely unreported** | **SHARED-BUG candidate — file upstream** after a proper tracker check. RustPython should guard `PyObject::hash` with `with_recursion` (a defense-in-depth/parity win — it is currently *more* robust than CPython, surviving ~200k finite depth). |
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
