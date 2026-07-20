# RPYR-0010 — `collections.deque` / `collections.defaultdict` leak reference cycles (missing GC traverse)

`collections.deque` and `collections.defaultdict` hold Python references, but their RustPython
payload structs declare **no GC `Traverse`** implementation. RustPython's cycle collector reaches
an object's referents only through `Traverse`; a payload with `HAS_TRAVERSE=false` is a wall the
collector cannot see past. So any reference cycle routed through a `deque` or a `defaultdict`
becomes **uncollectable** — the objects live forever, even after every external reference is gone
and `gc.collect()` has run. CPython collects the identical cycles.

This is the **first reproduction-confirmed instance of the gc-traverse class** the toolkit's
`gc-traverse-auditor` flags (the class was previously 0-confirmed, and is leak-only — no crash).

## Reproducer

```python
import gc, weakref
from collections import deque

d = deque()
d.append(d)                 # self-cycle
w = weakref.ref(d)
del d
gc.collect()
assert w() is not None      # RustPython: still alive -> LEAKED   (CPython: w() is None)
```

`defaultdict` is not itself weakref-able, so it is proven with a weakref-able node embedded in
the cycle:

```python
import gc, weakref
from collections import defaultdict

class Node: pass
d = defaultdict(int)
n = Node(); n.ref = d       # n -> d
d['x'] = n                  # d -> n   => cycle
w = weakref.ref(n)
del d, n
gc.collect()
assert w() is not None      # RustPython: node still alive -> LEAKED   (CPython: collected)
```

## Evidence (differential, weakref-strength)

Same harness on both interpreters (`evidence.txt` has the full transcript):

| cycle | RustPython 0.5.0 | CPython 3.14.4 |
|-------|------------------|----------------|
| user-class self-cycle (control) | collected | collected |
| `deque` self-cycle | **LEAKED** | collected |
| `deque` → node → `deque` | **LEAKED** | collected |
| `defaultdict` → node → `defaultdict` | **LEAKED** | collected |
| `list` self-cycle (baseline) | collected | collected |
| `dict` item self-cycle (baseline) | collected | collected |

The user-class control and the `list`/`dict` baselines collect on both interpreters — so the
harness detects collection correctly and RustPython's collector works in general. Only the two
`_collections` containers leak, and only on RustPython.

## Root cause

`crates/vm/src/stdlib/_collections.rs`:

```rust
// PyDeque (:31-37): owns a container of Python refs, no `traverse` in the pyclass attr
#[pyclass(module = "collections", name = "deque", unhashable = true)]
#[derive(Debug, Default, PyPayload)]
struct PyDeque {
    deque: PyRwLock<VecDeque<PyObjectRef>>,   // <-- owned Python refs, invisible to the collector
    maxlen: Option<usize>,
    state: AtomicCell<usize>,
}

// PyDefaultDict (:752-762): dict subclass, still no `traverse`
#[pyclass(module = "collections", name = "defaultdict", base = PyDict, unhashable = true)]
#[derive(Debug, Default)]
struct PyDefaultDict {
    dict: PyDict,                              // <-- embedded base dict, items hidden
    default_factory: PyRwLock<Option<PyObjectRef>>,  // <-- also hidden
}
```

Neither `#[pyclass]` attribute carries `traverse` (bare, which would auto-derive `Traverse`, or
`traverse = "manual"`), so the generated `MaybeTraverse` impl reports `HAS_TRAVERSE = false`. The
`defaultdict` case is doubly bad: because the subclass payload has no traverse, the collector
also never reaches the embedded base-dict's items — not just the `default_factory`.

## Divergence from CPython

CPython's `deque` (`Modules/_collectionsmodule.c`) and `defaultdict` both implement `tp_traverse`,
so their cycles are collected. RustPython should do the same: reclaim the cycle rather than leak.

## Suggested fix

Add `traverse` to each `#[pyclass]` — the derive traces the reference-bearing fields, and the
scalar/atomic fields (`maxlen`, `state`) are skipped. This is exactly how `list`/`dict`/`tuple`
were fixed in RustPython #6780:

```rust
#[pyclass(module = "collections", name = "deque", unhashable = true, traverse)]
struct PyDeque {
    deque: PyRwLock<VecDeque<PyObjectRef>>,
    #[pytraverse(skip)] maxlen: Option<usize>,
    #[pytraverse(skip)] state: AtomicCell<usize>,
}
```

For `defaultdict`, a manual traverse (or a derive that visits `dict` and `default_factory`) is
needed so the base dict's items are also traced.

## Impact

Unbounded memory growth in any long-running program that builds cyclic structures through a
`deque` or `defaultdict` — a slow-burn denial of service, and a silent correctness gap vs CPython
(finalizers on objects in such cycles never run).

## Scope — same class, not individually reproduced

The `gc-traverse-auditor` flagged ~24 further payloads in the same forgotten-opt-in class, most
prominently the `itertools` iterator cluster (`chain`/`cycle`/`tee`/…), which is the direct
structural analog of `zip`/`map`/`filter` — and those **do** declare `traverse`. Those are
high-confidence but are **not** reproduced in this report; only `deque` and `defaultdict` are
confirmed here.

## Provenance & prior art

Surfaced by the whole-tree `gc-traverse-auditor` run (`missing_traverse`, ranked top by
cycle-formation plausibility). The `git-history-analyzer` overlay dated the gap: siblings received
`traverse` in a Jan-2026 migration (#6623/#6760/#6780), but `_collections`' `PyDeque` never had a
traverse commit and `PyDefaultDict` was added brand-new in #8132 without one — a forgotten opt-in,
not a deliberate policy. No hit in the RustPython issue tracker; appears unreported. Disjoint from
the fuzzing catalog (which never examined GC completeness).
