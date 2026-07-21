# RPYR-0013 — `tuple.__hash__` recurses without a guard → native stack overflow (SIGSEGV)

RustPython's `tuple_hash` hashes each element with `val.hash(vm)` inside an unguarded loop. For a
deeply nested tuple, `val.hash(vm)` dispatches straight back into `tuple_hash`, recursing one native
stack frame per nesting level until the stack overflows — a **SIGSEGV**, not a catchable
`RecursionError`. The same tuple's `repr` and `==` are recursion-guarded and degrade cleanly, so this
is a guard that was simply left off the hash path.

The crash needs no explicit `hash()` call: using the nested tuple as a **dict key**, **set member**,
or **frozenset element** hashes it on insertion and crashes identically. `types.GenericAlias.__hash__`
hashes its `__args__` tuple, so it dies here too.

This is a **shared bug with CPython** (same unguarded shape in `Objects/tupleobject.c`), filed
upstream this session as [CPython #154318](https://github.com/python/cpython/issues/154318) — see
`catalog/shared_cpython_crashes.md` for why "both interpreters crash" is a bug in both, not
ACCEPTABLE behaviour.

## Reproducer

```python
t = ()
for _ in range(300_000):     # stack-size dependent; ~200-300k on an 8 MB stack
    t = (t,)
hash(t)                      # SIGSEGV
#   {t: 1}   -> SIGSEGV      (dict key — insertion hashes it)
#   {t}      -> SIGSEGV      (set member)
```

## Evidence (differential)

| operation on the same depth-300k nested tuple | RustPython 0.5.0 | CPython 3.14.4 |
|---|---|---|
| `hash(t)` | **SIGSEGV** (exit 139) | **SIGSEGV** (exit 139) |
| `{t: 1}` / `{t}` (insertion hashes key) | **SIGSEGV** | **SIGSEGV** |
| `repr(t)` (guarded twin) | `RecursionError: maximum recursion depth exceeded …` | `RecursionError: Stack overflow …` |
| `t == t` (guarded twin) | `RecursionError` (to depth 2,000,000) | `RecursionError` |

Only `hash` crashes; the guarded siblings raise cleanly on both interpreters. An ASan build of
CPython `main` names the frame: `stack-overflow … in tuple_hash` at `Objects/tupleobject.c:385`.

## Root cause

`crates/vm/src/builtins/tuple.rs` — the hash slot delegates to `tuple_hash`, which maps `val.hash(vm)`
over the elements with **no recursion guard**:

```rust
impl Hashable for PyTuple {
    fn hash(zelf: &Py<Self>, vm: &VirtualMachine) -> PyResult<PyHash> {
        tuple_hash(zelf.as_slice(), vm)                                   // :499
    }
}

pub(super) fn tuple_hash(elements: &[PyObjectRef], vm: &VirtualMachine) -> PyResult<PyHash> {
    hash::hash_tuple(elements.iter().map(|val| val.hash(vm)))            // :683  <-- unguarded recursion
}
```

The sibling `repr` in the **same file** *is* guarded — it enters a `ReprGuard`, and deep nesting
degrades to a `RecursionError` rather than a segfault:

```rust
impl Representable for PyTuple {
    fn repr(zelf: &Py<Self>, vm: &VirtualMachine) -> PyResult<PyStrRef> {
        ...
        } else if let Some(_guard) = ReprGuard::enter(vm, zelf.as_object()) {   // :535  guarded
        ...
    }
}
```

`tuple_hash` enters neither `ReprGuard` nor `vm.with_recursion(...)`, so `val.hash(vm)` on a nested
tuple recurses without bound and overflows the native stack.

## Divergence from CPython

None in behaviour — CPython SIGSEGVs the same way, in `tuple_hash` (`Objects/tupleobject.c:385`,
unguarded `PyObject_Hash(item[i])`), and its newly added `frozendict` (main only) inherits the bug
through copied code (`frozendict_pair_hash`). Both are the same defect class already being fixed
upstream with a recursion guard (`_Py_make_parameters` #154275, `_elementtree` #148801). RustPython
should fix its side regardless — a Python program should never segfault the interpreter.

## Suggested fix

Wrap the element hashing in `vm.with_recursion(...)` — the depth guard `repr`/`compare` already rely
on — so the overflow becomes a catchable `RecursionError`:

```rust
pub(super) fn tuple_hash(elements: &[PyObjectRef], vm: &VirtualMachine) -> PyResult<PyHash> {
    vm.with_recursion("while hashing a tuple", || {
        hash::hash_tuple(elements.iter().map(|val| val.hash(vm)))
    })
}
```

Note: use `with_recursion` (a **depth** limit), not `ReprGuard` — `ReprGuard` keys on object-id
re-entrance (for *cycles*) and would not catch deep *acyclic* nesting, which is the case here (tuples
are immutable and cannot be cyclic).

**Better (systemic) fix — see [[RPYR-0014]]:** the informed explore traced this past the per-slot view to
the hash **dispatch** (`protocol/object.rs:695`), which lacks the `with_recursion` wrap that repr(:383) and
compare(:291) have. Guarding there fixes tuple, `genericalias`, `slice`, and `code` `__hash__` at once and
supersedes the per-slot `tuple.rs` patch above.

## Impact

Any Python program that hashes — or merely uses as a dict key / set member — a sufficiently deeply
nested tuple aborts the whole interpreter with SIGSEGV. Reachable from trivial pure-Python code and
not catchable (`try/except RecursionError` does not help against a native stack overflow): a
denial-of-service on the interpreter.

## Provenance

Surfaced by the `recursion-guard-auditor` (the same-file slot asymmetry — `repr` guarded at
tuple.rs:535, `hash` unguarded) and the CPython differential / shared-crash ledger, which found the
crash reproduces on CPython too and — after a tracker check — was **unreported**, so it was filed
upstream as [CPython #154318](https://github.com/python/cpython/issues/154318). RustPython umbrella
[#2796](https://github.com/RustPython/RustPython/issues/2796) (= fuzzer RUSTPY-0007a). Same defect *class*
as the genericalias `make_parameters` recursion (CPython #154275; recorded [[RPYR-0015]]), a distinct site. RustPython has no `frozendict`, so the CPython issue's second (copied-code) site does
not apply here.
