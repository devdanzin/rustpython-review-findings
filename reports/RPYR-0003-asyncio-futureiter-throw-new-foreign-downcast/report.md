# RPYR-0003 — `Future.__await__().throw(E)` aborts on a `__new__`-foreign exception

`FutureIter.throw(exc_type)` constructs the exception via `exc = exc_type.call((), vm)?`
after checking that `exc_type` is a `BaseException` subclass — then does
`Err(exc.downcast().unwrap())`. But `exc_type.call(())` runs `exc_type.__new__`, which can
return **any** object; a subclass whose `__new__` returns a non-exception makes the downcast
fail, and `.unwrap()` aborts the interpreter.

## Reproducer

```python
import _asyncio
f = _asyncio.Future(loop=object())
class E(Exception):
    def __new__(cls, *a):
        return 42
f.__await__().throw(E)
```

```
thread 'main' panicked at crates/stdlib/src/_asyncio.rs:1081:32:
called `Result::unwrap()` on an `Err` value: [PyObject PyInt { value: 42 }]
```

The precondition is standard Python: `class E(Exception)` with an overriding `__new__` that
returns a foreign object makes `E()` return that object (confirmed: `E()` → `42`).

## Root cause

`crates/stdlib/src/_asyncio.rs`, `PyFutureIter::throw`:

```rust
let exc = if exc_type.fast_isinstance(vm.ctx.types.type_type) {
    let exc_class: PyTypeRef = exc_type.clone().downcast().unwrap();
    if !exc_class.fast_issubclass(vm.ctx.exceptions.base_exception_type) { /* TypeError */ }
    // ...
    exc_type.call((), vm)?              // runs E.__new__ -> may return anything
} else { exc_type };
// ...
Err(exc.downcast().unwrap())           // L1081: Err when E.__new__ returned a non-exception
```

The `fast_issubclass(BaseException)` check is on **`exc_type`** (the class); the failing
downcast is on **`exc`** (the *instance* returned by `exc_type.call(())`). A subclass can be a
`BaseException` subclass while its `__new__` returns something else.

## Divergence from CPython

CPython raises `TypeError` — a `__new__` that returns a non-instance is not accepted as the
raised exception.

## Suggested fix

Propagate a `TypeError` instead of unwrapping:

```rust
Err(exc.downcast().map_err(|o| {
    vm.new_type_error(format!("calling {} returned a non-exception", o.class().name()))
})?)
```

## The guarded twin (fix pattern already in the file)

The `map_err` downcast idiom is used correctly at five other sites in the same file (`879`,
`920`, `2038`, `2297`, `2762`); only `throw` uses `.unwrap()`.

## Toolkit meta-evaluation note (why this finding is instructive)

The panic-site **scanner** correctly flagged this FIX, but the panic-site **agent** wrongly
dismissed it as ACCEPTABLE, arguing from a payload invariant ("`exc_type.call(())` returns a
`BaseException` because `exc_type` is `fast_issubclass(BaseException)`"). The
git-history-analyzer disagreed, and a one-line binary test settled it in the scanner's favour.
This is exactly why the invariant-downcast calibration only down-ranks a downcast when the
`fast_isinstance` gate is on the **same** variable as the downcast subject — here the gate is
on `exc_type` but the downcast is on `exc`, a distinct value, so the site correctly stays FIX.

## Prior art

No hit in the RustPython tracker. Appears unreported. Not in the fuzzing catalog.
