# RPYR-0011 — `math.sumprod` eager-collect OOM (big-int generic path)

`math.sumprod(p, q)` has a fast path that accumulates `i64` products. The moment any
operand exceeds `i64::MAX` it falls back to a big-int generic path that **materializes both
remaining iterables in full** (`chain(iter).collect::<Vec<_>>()`) before multiplying. CPython's
`sumprod` streams element-by-element at O(1) memory. So a huge or **unbounded** iterable that
forces the big-int path makes RustPython's memory grow O(N) and, unbounded, **abort the whole
interpreter with an allocator SIGABRT** — an uncatchable DoS — where CPython simply streams.

## Reproducer

```python
import math, itertools
# count(10**19) yields ints always > i64::MAX -> forces the big-int generic path,
# which collects the (infinite) iterators into Vecs.
math.sumprod(itertools.count(10**19), itertools.count(10**19))
```

- **RustPython 0.5.0**: `memory allocation of 80 bytes failed` → **SIGABRT, exit 134** (under a 1.5 GB cap; unbounded it exhausts all RAM).
- **CPython 3.14.4**: streams at O(1) memory — runs forever computing an infinite sum, peak RSS flat ~11 MB, never OOMs.

## Root cause

`crates/stdlib/src/math.rs`, the generic path of `sumprod` (fn at `:607`):

```rust
let p_remaining: Result<Vec<PyObjectRef>, _> =
    core::iter::once(Ok(p_i)).chain(p_iter).collect();   // :733  <-- collects all of p
let q_remaining: Result<Vec<PyObjectRef>, _> =
    core::iter::once(Ok(q_i)).chain(q_iter).collect();   // :735  <-- collects all of q
```

Both remaining iterators are drained into `Vec<PyObjectRef>` up front. For an unbounded
iterator this never terminates the collect — it grows until the allocator aborts.

## Divergence from CPython — memory is O(N) vs O(1)

Finite proof (both operands a generator yielding `10**19`, N elements):

| N | RustPython peak RSS | CPython peak RSS |
|---|---|---|
| 1,000,000 | 40 MB | 11 MB |
| 4,000,000 | 86 MB | 11 MB |
| 8,000,000 | 146 MB | 11 MB |
| 20,000,000 | 329 MB | 11 MB |

RustPython grows ~16 MB per million elements (the collected `Vec` + the live big-ints);
CPython is flat — it never holds more than one element pair.

## Suggested fix

Stream the generic path: iterate `p_iter`/`q_iter` in lockstep (`zip`) accumulating the running
big-int sum, instead of `chain(iter).collect()`. That matches CPython's O(1)-memory `sumprod`.

## Impact

An uncatchable interpreter abort (SIGABRT) from a single `math.sumprod` call on an untrusted /
unbounded iterable whose elements exceed `i64` — a denial of service. The finite case is a large
transient memory spike (O(N) where CPython is O(1)).

## Scope note — same class as the fuzzer's 0012–0016, distinct location

This is the eager-collect-parity class (Class G). It differs from the fuzzing catalog's
`RUSTPY-0012..0016`, which are `Vec<PyObjectRef>` gaps at **`FromArgs` bind** time — this one is a
**body-level generic-path collect**, reachable only once an operand forces the big-int path. It is
**not** Class J (abort-vs-MemoryError): CPython does not balloon here, it streams, so this is a
genuine parity gap. Surfaced by the eager-collect-parity agent (as a skeptical LOW `ArgIterable`
candidate) and confirmed by hand-tracing the body + the differential above.
