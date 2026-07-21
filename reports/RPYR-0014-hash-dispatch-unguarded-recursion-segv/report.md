# RPYR-0014 — the hash dispatch is unguarded → container `__hash__` SIGSEGV

RustPython's hash **dispatch** — `PyObject::hash` at `crates/vm/src/protocol/object.rs:695` — calls a
type's hash slot with **no `vm.with_recursion(...)` wrap**, while the sibling dispatches in the same file,
`repr` (`:383`) and rich-compare/`_cmp` (`:291`), both have one. So any element-wise `__hash__` that
follows a Python object graph recurses one native stack frame per level and overflows the stack — a
**SIGSEGV, not a catchable `RecursionError`**.

This is the systemic root beneath **RPYR-0013** (which fixed only `tuple.rs`): the same gap makes
`GenericAlias.__hash__`, `slice.__hash__`, and `code.__hash__` crash too. It is the RustPython face of
umbrella **#2796** (= fuzzer **RUSTPY-0007a**), and shared with CPython (genericalias/slice hash route
through CPython's `tuple_hash`, filed as **#154318**).

## Reproducer

```python
# GenericAlias
x = int
for _ in range(400_000):
    x = list[x]
hash(x)                      # SIGSEGV

# slice (hashable since 3.12)
s = slice(0)
for _ in range(2_000_000):
    s = slice(s)
hash(s)                      # SIGSEGV
```

## Evidence (differential)

| op on the nested object | RustPython 0.5.0 | CPython 3.14.4 |
|---|---|---|
| `hash(genericalias)` @400k | **SIGSEGV** | SIGSEGV (shared, #154318) |
| `hash(slice)` @2M | **SIGSEGV** | SIGSEGV |
| `repr(...)` / `... == ...` (guarded twins) | `RecursionError` | `RecursionError` |

Only the hash path crashes; repr and compare degrade cleanly on both interpreters — because their
dispatch is guarded and hash's is not.

## Root cause

`crates/vm/src/protocol/object.rs`:

```rust
// :291  _cmp  -> wraps rich-compare dispatch in with_recursion   (guarded)
// :383  repr  -> wraps repr dispatch in with_recursion            (guarded)
// :695  hash  -> dispatches the hash slot with NO with_recursion  (UNGUARDED)  <-- the bug
```

`PyObject::hash` invokes the type's `Hashable::hash` slot directly; for a nested container the slot
re-enters `PyObject::hash` on each element, recursing to the full nesting depth with nothing counting the
frames.

## Suggested fix (one line, closes the whole class)

Wrap the hash dispatch at `object.rs:695` in `vm.with_recursion(...)`, exactly as `:291`/`:383` do:

```rust
vm.with_recursion("while hashing", || zelf.class().slots.hash.load()(zelf, vm))
```

This guards **every** `__hash__` at once — tuple (RPYR-0013), genericalias, slice, code — converting the
overflow into a `RecursionError`. It supersedes RPYR-0013's per-slot `tuple.rs` fix.

## Divergence from CPython

For genericalias/slice, none — CPython shares the crash (both route through `tuple_hash`; filed #154318).
RustPython should still guard its dispatch; the fix location differs (one dispatch site vs CPython's
per-function `Py_EnterRecursiveCall`).

## Impact

Hashing — or using as a dict key / set member — a deeply nested `GenericAlias`/`slice`/`tuple` aborts the
interpreter with SIGSEGV. Reachable from trivial pure-Python code, not catchable.

## Provenance

The recursion-guard-auditor, run informed with the RPYR-0013 template, traced the crash past the per-slot
view to the dispatch layer (`object.rs:695`) — the systemic finding a cold per-site run misses. The
git-history-analyzer independently flagged `genericalias.__hash__` as an RPYR-0013 sibling. Umbrella
[#2796](https://github.com/RustPython/RustPython/issues/2796) (= fuzzer RUSTPY-0007a); shared CPython
[#154318](https://github.com/python/cpython/issues/154318). See [[RPYR-0013]] (the tuple face) and
[[RPYR-0015]] (genericalias `make_parameters`, a *separate* recursion not on this dispatch path).
