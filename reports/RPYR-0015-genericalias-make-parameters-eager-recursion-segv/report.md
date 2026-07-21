# RPYR-0015 — genericalias `make_parameters` eager unguarded recursion → SIGSEGV (RustPython-only)

`make_parameters_from_slice` (`crates/vm/src/builtins/genericalias.rs`) collects a generic alias's type
parameters by recursing into any argument that is a `list`/`tuple` (self-call at `genericalias.rs:329`),
with **no recursion guard**. RustPython computes `__parameters__` **eagerly, at subscript time**, so a
self-referential or deeply-nested list argument overflows the native stack the moment the alias is created.

This is the RustPython face of umbrella **#2796** (the fuzzer's second fleet names
`genericalias::make_parameters_from_slice` explicitly) and the twin of CPython **#154275**. It is
**distinct from RPYR-0014**: that is the hash *dispatch*; this is a standalone parameter walk that never
touches the hash guard.

## Reproducer

```python
L = []
L.append(L)          # self-referential
list[L]              # SIGSEGV on RustPython at subscript

# non-cyclic variant (proves it's unguarded depth, not cycle-specific):
x = [0]
for _ in range(300_000):
    x = [x]
list[x]              # SIGSEGV
```

## Evidence (differential)

| input | RustPython 0.5.0 | CPython 3.14.4 |
|---|---|---|
| `L=[]; L.append(L); list[L]` | **SIGSEGV** | ok (params are lazy) |
| `list[L].__parameters__` | SIGSEGV | SIGSEGV (= #154275) |

RustPython crashes on strictly more inputs than CPython: because RustPython builds `__parameters__` eagerly
at subscript, the bare `list[L]` already overflows, whereas CPython defers until `__parameters__` is forced.

## Root cause

`crates/vm/src/builtins/genericalias.rs` — `make_parameters_from_slice` recurses into nested `list`/`tuple`
args (`:329`) unguarded; `union.rs:236` delegates into the same walk. None of these pass through the
`vm.with_recursion` guards on hash/compare/repr (RPYR-0014), so the descent is unbounded.

## Suggested fix

Wrap the descent in `vm.with_recursion("while computing __parameters__", ...)`, mirroring CPython PR
#154277 which wraps `_Py_make_parameters` in `Py_EnterRecursiveCall`. (RustPython's eager computation makes
the guard matter even more than CPython's lazy one.)

## Impact

Constructing a generic alias over a self-referential or deeply-nested list argument aborts the interpreter
with SIGSEGV — reachable from a three-line pure-Python program, not catchable.

## Provenance

Surfaced by the recursion-guard-auditor in the informed explore, which separated it from the hash class
(RPYR-0014) as a distinct raw-Rust recursion. Umbrella
[#2796](https://github.com/RustPython/RustPython/issues/2796) (= fuzzer RUSTPY-0007a); CPython twin
[#154275](https://github.com/python/cpython/issues/154275). See [[RPYR-0014]] (hash dispatch) and the
shared-crash ledger in `catalog/shared_cpython_crashes.md`.
