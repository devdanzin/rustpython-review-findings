# RPYR-0018 — `_imp.find_frozen(name, <2nd arg>)` → `unimplemented!()` abort

`_imp.find_frozen`'s optional second parameter (`withdata`) is guarded by `.into_option().is_some()`
(`crates/vm/src/stdlib/_imp.rs:327`) — the guard fires whenever a second argument is passed **at all**; the
value is never inspected. It then reaches `unimplemented!()` (`:329`), aborting the interpreter. CPython's
`find_frozen` takes exactly one positional argument, so a second arg is a clean `TypeError` there.

## Reproducer

```python
import _imp
_imp.find_frozen('_frozen_importlib', True)   # RustPython: unimplemented!() -> abort (exit 101)
```

## Evidence (differential)

| input | RustPython 0.5.0 | CPython 3.14.4 |
|---|---|---|
| `_imp.find_frozen(name, True)` | **panic-abort** (`_imp.rs:329 not implemented`, exit 101) | `TypeError: find_frozen() takes exactly 1 positional argument` |

Any second argument triggers it (the value is irrelevant — the guard tests presence).

## Root cause

`crates/vm/src/stdlib/_imp.rs:322-329`:

```rust
fn find_frozen(name: ..., withdata: OptionalArg<...>, vm: &VirtualMachine) -> ... {
    if withdata.into_option().is_some() {   // :327  fires on ANY 2nd arg, value ignored
        unimplemented!();                   // :329  -> release-build abort
    }
    ...
}
```

## Suggested fix

Either implement the `withdata` path, or reject the extra argument to match CPython's arity (raise a Python
`TypeError`/`NotImplementedError` instead of `unimplemented!()`). A reachable `unimplemented!()` must never
be a bare panic.

## Impact

A two-argument call to an importlib-internal API aborts the interpreter. Low severity (obscure API), but a
trivially reachable pure-Python interpreter abort with no memory-unsafety excuse.

## Provenance

Surfaced by the panic-site-auditor in the informed explore (NEW, HIGH confidence — the guard checks
presence, not value). No fuzzer RUSTPY-* match and no RustPython-tracker hit for `find_frozen` → appears
unreported.
