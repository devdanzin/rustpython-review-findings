# RPYR-0002 — `_asyncio.current_task()` aborts when `_current_tasks` is rebound

`current_task()`'s slow path reads the module attribute `_asyncio._current_tasks` and does
`current_tasks.downcast::<PyDict>().unwrap()`. That attribute is a plain, Python-writable
module attribute, so a program can rebind it to any object; when it is not a dict the
downcast returns `Err` and `.unwrap()` aborts the interpreter.

## Reproducer

```python
import _asyncio
_asyncio._current_tasks = 42               # rebind the internal dict
_asyncio.current_task(loop=object())       # no running loop + explicit loop -> slow path
```

```
thread 'main' panicked at crates/stdlib/src/_asyncio.rs:2408:56:
called `Result::unwrap()` on an `Err` value: [PyObject PyInt { value: 42 }]
```

The slow path (line 2408) is reached whenever `is_current_loop == false` — e.g. no loop is
running but an explicit `loop=` argument is supplied.

## Root cause

`crates/stdlib/src/_asyncio.rs`:

```rust
// get_current_tasks_dict (L2332): reads a Python-reassignable module attribute
let asyncio = vm.import("_asyncio", 0)?;
let current_tasks = vm.get_attribute_opt(asyncio, "_current_tasks")?...;

// current_task (L2408): unwraps the downcast of that attribute
let current_tasks = get_current_tasks_dict(vm)?;
let dict: PyDictRef = current_tasks.downcast().unwrap();   // <-- Err when not a dict
```

`_current_tasks` is seeded as a `PyDict` through `extend_module!`, but module objects are
mutable, so any Python code can set `_asyncio._current_tasks = <anything>`.

## Divergence from CPython

CPython tracks the current task in thread state; reassigning `_asyncio._current_tasks` does
not give the interpreter a way to crash on a subsequent `current_task()`.

## Suggested fix

Mirror the guarded siblings — degrade gracefully or raise:

```rust
let Ok(dict) = current_tasks.downcast::<PyDict>() else {
    return Ok(vm.ctx.none());   // or vm.new_type_error("_current_tasks must be a dict")
};
```

## The guarded twin (fix pattern already in the file)

The **same** `_current_tasks` dict is downcast in four functions — `_enter_task` (2503),
`_leave_task`, and `_swap_current_task` all use `if let Ok(dict) = current_tasks.downcast::<PyDict>()`
and degrade gracefully. Only `current_task()` uses `.unwrap()`. The safe idiom was written
three times and skipped once.

## Impact

A three-line pure-Python program aborts the interpreter. Any framework that touches
`_asyncio._current_tasks` (or a hostile plugin) can weaponise it.

## How the toolkit found it

Doubly-surfaced: the **panic-site-auditor** flagged it FIX (a `downcast_or_coerce` signal on
a value with no `self.`-field origin and no same-variable `fast_isinstance` gate — i.e. a
genuinely Python-controllable downcast that the invariant-downcast calibration correctly
leaves as FIX), and the **git-history-analyzer** reached it independently via similar-bug
detection (three guarded `_current_tasks` downcasts vs. this one bare `.unwrap()`).
