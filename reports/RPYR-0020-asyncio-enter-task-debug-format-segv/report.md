# RPYR-0020 — `_asyncio._enter_task` `{:?}` reaches the unsound `PyAtomicRef` Debug → SIGSEGV

`_asyncio._enter_task(loop, task)` (a `#[pyfunction]`) formats the `task` argument with `{:?}`
**unconditionally** in its "a task is already running" error (`crates/stdlib/src/_asyncio.rs:2491`). That
`{:?}` on a payload containing a **populated** `PyAtomicRef` reaches the unsound Debug cast of **RUSTPY-0018**
(`object/ext.rs:278`) — which reads the stored `Py<T>*` pointer as bare `T`, misinterpreting the object
header as payload → garbage dereference → **SIGSEGV**. This is a new, live, pure-Python path into 0018.

The exact argument type matters: a `PyFunction`'s `code: PyAtomicRef<PyCode>` is always populated, so a
**function** crashes; a fresh coroutine's `exception` is `None`, which prints harmlessly (the cast only
fires on a non-null load).

## Reproducer

```python
import _asyncio, asyncio
loop = asyncio.new_event_loop()
async def c(): pass
def g(): pass                       # PyFunction: code: PyAtomicRef is always populated
_asyncio._enter_task(loop, c())     # set the current task
_asyncio._enter_task(loop, g)       # formats g with {:?} -> unsound cast on populated PyAtomicRef -> SIGSEGV
```

## Evidence (differential)

| input | RustPython 0.5.0 | CPython 3.14.4 |
|---|---|---|
| `_enter_task(loop, <coroutine>)` twice | error prints `PyAtomicRef(None)` — **no crash** | RuntimeError |
| `_enter_task(loop, <function>)` (populated) | **SIGSEGV** (exit 139) | RuntimeError |

## Root cause

Two layers:
- **Root (RUSTPY-0018):** `crates/vm/src/object/ext.rs:278` — `PyAtomicRef`'s `Debug::fmt` does
  `.load().cast::<T>()`, while `Deref`(:307), `load_raw`(:320) and `From<PyRef<T>>` all treat the stored
  pointer as `Py<T>`. `Py<T>` is `#[repr(C)]` header-first, so reading it as bare `T` dereferences the wrong
  offset. Confirmed the only cross-method cast inconsistency tree-wide.
- **Trigger:** `_asyncio.rs:2491` Debug-formats an arbitrary Python object (`{:?}`) in a user-reachable
  error path; the only payloads that reach a populated `PyAtomicRef` this way are `PyFunction` and `Coro`.

## Suggested fix

- **Root, one char:** `object/ext.rs:278` → `.cast::<Py<T>>()` (matches Deref/load_raw). Collapses the
  whole 0018 class — including this trigger — to at worst cosmetic.
- **Trigger:** format the task with Python `repr`, not Rust `{:?}` — never `{:?}` an arbitrary `PyObjectRef`
  in a message.

## Impact

A short pure-Python `_asyncio` sequence segfaults the interpreter (memory-unsafety, not a clean panic).
Reachable without threads or the JIT.

## Provenance

The debug-format-auditor (informed explore) identified this as the one live `{:?}`-on-pyobject trigger
reaching the unsound Debug — and, on reachability analysis, *downgraded* the catalogued `typevar.rs`/`os.rs`
triggers to cosmetic (their reaching types always have `__name__`, taking the safe path). The
unsafe-soundness-auditor confirmed the RUSTPY-0018 root is still present and the sole cross-method cast
tree-wide. See `catalog/known_panics.tsv` (RUSTPY-0018).
