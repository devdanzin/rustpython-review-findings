# RPYR-0012 — `itertools.cycle` (and the itertools cluster) leak reference cycles

`itertools.cycle` holds Python references — `iter: PyIter` and `saved: PyRwLock<Vec<PyObjectRef>>`
(the buffer of already-yielded items) — but its `#[pyclass]` payload declares **no GC `Traverse`**.
So a reference cycle routed through a `cycle` object is invisible to RustPython's cycle collector
and can never be reclaimed. CPython's `itertools.cycle` defines `tp_traverse` and collects the same
cycle. The entire itertools iterator family (~21 payloads) shares this gap — `cycle` is the most
weaponizable because it accumulates a back-reference *after* construction.

This is the same root cause as **RPYR-0010** (`collections.deque`/`defaultdict`), which explicitly
scoped the itertools cluster as "same class, not individually reproduced" — this report reproduces it.

## Reproducer

```python
import gc, weakref, itertools
class Node: pass
d = []
c = itertools.cycle(d)   # cycles over d
n = Node(); n.c = c       # n -> c
d.append(n)               # d -> n
next(c)                   # c.saved = [n]   =>   cycle:  c -> saved -> n -> c
w = weakref.ref(n)
del c, d, n
gc.collect()
assert w() is not None    # RustPython: node still alive -> LEAKED   (CPython: collected)
```

## Evidence (weakref differential)

| cycle | RustPython 0.5.0 | CPython 3.14.4 |
|-------|------------------|----------------|
| user-class self-cycle (control) | collected | collected |
| `itertools.cycle` embedded-node cycle | **LEAKED** | collected |

The control collects on both, so the harness is sound; only the `cycle`-routed cycle leaks, and
only on RustPython.

## Root cause

`crates/vm/src/stdlib/itertools.rs`:

```rust
#[pyclass(name = "cycle")]           // <-- no `traverse`
#[derive(Debug, PyPayload)]
struct PyItertoolsCycle {
    iter: PyIter,                     // owned Python ref
    saved: PyRwLock<Vec<PyObjectRef>>, // owned Python refs, accumulated post-construction
    index: AtomicCell<usize>,
}
// IterNext::next (:266):
zelf.saved.write().push(item.clone());   // :268  <-- back-reference injectable after construction
```

With no `traverse`, `HAS_TRAVERSE = false`, so the collector never traces `saved`/`iter`. Every
other itertools iterator (`chain`/`tee`/`product`/`combinations`/`permutations`/…) has the same
shape and the same missing opt-in — `grep -c traverse itertools.rs` is 0.

## Divergence from CPython

CPython's `itertools` iterators all implement `tp_traverse`, so their cycles are collected.
RustPython should do the same.

## Suggested fix

Add `traverse` to each itertools iterator `#[pyclass]` (the derive traces the ref-bearing fields;
skip the `index`/atomics), exactly as `list`/`dict`/`tuple` were fixed in RustPython #6780:

```rust
#[pyclass(name = "cycle", traverse)]
struct PyItertoolsCycle {
    iter: PyIter,
    saved: PyRwLock<Vec<PyObjectRef>>,
    #[pytraverse(skip)] index: AtomicCell<usize>,
}
```

## Impact

Unbounded memory growth in any long-running program that builds cyclic structures through an
itertools iterator — a slow-burn denial of service, plus finalizers on objects in such cycles
never run (a silent correctness gap vs CPython).

## Provenance

Surfaced by the `gc-traverse-auditor` (top cycle-plausibility of the 21-payload itertools cluster);
the `git-history-analyzer` dated the gap to the incomplete Jan-2026 traverse rollout
(#6760/#6623/#6780) that hardened the object model but skipped itertools/collections. Cross-linked
to RPYR-0010 as the same root-cause class in a different module. No hit in the RustPython tracker.
