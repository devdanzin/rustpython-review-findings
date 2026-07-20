# RPYR-0001 — `pickle.dumps(ImportError())` aborts the interpreter

`BaseException.__reduce__` for the `ImportError` family builds its reduce tuple as
`vm.new_tuple((exc.get_arg(0).unwrap(),))` with **no arity guard**. `get_arg(0)` is
`self.args.read().get(0).cloned()`, which returns `None` when the exception has zero
positional args. `ImportError()` (and `ModuleNotFoundError()`) construct with an *empty*
args tuple, so `get_arg(0)` is `None` and `.unwrap()` aborts the interpreter.

## Reproducer

```python
import pickle
pickle.dumps(ImportError())        # or: ImportError().__reduce__()
```

```
thread 'main' panicked at crates/vm/src/exceptions.rs:1778:46:
called `Option::unwrap()` on a `None` value
```

(The reviewed source tree is `3290f287f`, where the site is `exceptions.rs:1872`; the
installed `a9c2c529b` binary panics at `:1778` — the ~94-line drift between the two
checkouts, handled by the toolkit's drift-tolerant `known-issues` cross-reference.)

`pickle.dumps(ImportError())` is the common path — `pickle` calls `__reduce__` internally —
so any program that pickles or copies a no-argument `ImportError`/`ModuleNotFoundError`
aborts.

## Root cause

`crates/vm/src/exceptions.rs`, `PyImportError`'s `__reduce__`:

```rust
fn __reduce__(exc: PyBaseExceptionRef, vm: &VirtualMachine) -> PyTupleRef {
    let obj = exc.as_object().to_owned();
    let mut result: Vec<PyObjectRef> = vec![
        obj.class().to_owned().into(),
        vm.new_tuple((exc.get_arg(0).unwrap(),)).into(),   // <-- None on empty args
    ];
    // ...
}
```

`ImportError`'s `slot_init` (same file) only consumes the `name`/`path`/`name_from`
keyword arguments and never appends a positional arg, so a bare `ImportError()` stores an
empty `args` tuple. `get_arg(0)` is then `None`, and `.unwrap()` turns a normal case into a
Rust panic that aborts the whole interpreter. `ModuleNotFoundError` inherits `__reduce__`
from `PyImportError`, so it is affected too.

## Divergence from CPython

```pycon
>>> ImportError().__reduce__()
(<class 'ImportError'>, ())
```

CPython returns the class plus an empty args tuple. RustPython aborts.

## Suggested fix

Handle the empty case instead of unwrapping — mirror the base class / OSError twin:

```rust
let args_elem: PyObjectRef = match exc.get_arg(0) {
    Some(arg0) => vm.new_tuple((arg0,)).into(),
    None => exc.args().into(),
};
```

## The guarded twin (fix pattern already in the file)

`PyOSError::__reduce__`, 400 lines down in the same file, guards the identical
`get_arg` access with `if args.len() >= 2 && args.len() <= 5 { ... }`, and the base
`PyBaseException::__reduce__` uses `self.args()` wholesale with no indexing. `ImportError`
simply never adopted the guard its siblings use.

## Impact

A trivial, pure-Python one-liner (`pickle.dumps(ImportError())`) aborts the interpreter — a
denial of service. It has been reachable since the `crates/vm` layout was created, and no
test exercises it.

## Prior art

No hit in the RustPython tracker for an `ImportError.__reduce__` panic. Appears unreported.
Not in the `rustpython-findings` fuzzing catalog.
