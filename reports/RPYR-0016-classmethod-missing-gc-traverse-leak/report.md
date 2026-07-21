# RPYR-0016 — `classmethod` missing GC `traverse` → uncollectable cycle leak

`PyClassMethod` owns a Python reference — `callable: PyMutex<PyObjectRef>` — but its `#[pyclass]` declares
**no `traverse`**, so RustPython's cycle collector never traces the wrapped callable. A reference cycle
routed through a `classmethod`'s function is therefore uncollectable. The smoking gun: the **adjacent
sibling `staticmethod` (`staticmethod.rs:10`) *is* declared `#[pyclass(traverse)]`** over an identical
`callable` field — classmethod simply never got the opt-in from the #6780 traverse rollout.

Same class as **RPYR-0010** (deque/defaultdict) and **RPYR-0012** (itertools.cycle).

## Reproducer

```python
import gc, weakref
class Node: pass
n = Node()
def f(cls): pass
f.ref = n              # f -> n
cm = classmethod(f)    # cm -> f (cm_callable)
n.cm = cm              # n -> cm     =>  cycle  n -> cm -> f -> n
w = weakref.ref(n)
del n, f, cm
gc.collect()
assert w() is not None    # RustPython: node still alive -> LEAKED   (CPython: collected)
```

## Evidence (weakref differential)

| cycle | RustPython 0.5.0 | CPython 3.14.4 |
|---|---|---|
| user-class self-cycle (control) | collected | collected |
| **classmethod** callable cycle | **LEAKED** | collected |
| **staticmethod** callable cycle (the twin) | collected | collected |

The control collects on both (harness sound). Only the classmethod cycle leaks, and only on RustPython —
while the structurally identical staticmethod cycle collects, because staticmethod carries `traverse`.

## Root cause

`crates/vm/src/builtins/classmethod.rs` — `PyClassMethod { callable: PyMutex<PyObjectRef>, .. }` with a
`#[pyclass]` that has no `traverse`. Contrast `crates/vm/src/builtins/staticmethod.rs:10` —
`#[pyclass(... traverse)]` over the same field shape.

## Suggested fix

Add `traverse` to classmethod's `#[pyclass]` (the derive traces `callable`), exactly as `staticmethod`
already does and as list/dict/tuple were fixed in **#6780**:

```rust
#[pyclass(with(...), traverse)]
struct PyClassMethod { callable: PyMutex<PyObjectRef>, .. }
```

## Impact

Any long-running program that builds a cycle through a `classmethod`'s wrapped callable leaks the whole
cycle (unbounded memory growth; finalizers on cycle members never run) — a slow-burn DoS + a silent
correctness gap vs CPython.

## Provenance

The git-history-analyzer (informed explore) found the smoking-gun asymmetry against `staticmethod`; the
gc-traverse-auditor listed classmethod among ~54 ref-owning payloads still missing `traverse`. Follows the
merged rollout [#6780](https://github.com/RustPython/RustPython/pull/6780). See [[RPYR-0010]], [[RPYR-0012]]
— same root cause, different types; the broader ~54-payload cluster (deque/dict/set iterators, itertools
accumulate/groupby/tee/pairwise) needs the same one-line opt-in.
