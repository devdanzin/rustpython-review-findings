# RPYR-0004 — `mmap.find`/`rfind` slice-panic when `start > end`

`mmap.find(sub, start, end)` computes its search window via `get_find_range`, which clamps
`start` and `end` **each independently** to `[0, size]` but never enforces `start <= end`.
When a Python caller passes `start > end`, the resulting `&slice[start..end]` panics and
aborts the interpreter. `rfind` shares the same helper and the same bug.

## Reproducer

```python
import mmap
mmap.mmap(-1, 10).find(b"x", 5, 2)         # find
# mmap.mmap(-1, 10).rfind(b"x", 8, 3)      # rfind, same root cause
```

```
thread 'main' panicked at crates/stdlib/src/mmap.rs:795:57:
slice index starts at 5 but ends at 2
```

A second trigger reaches it with an implicit `start` (which defaults to the current
position): `m = mmap.mmap(-1, 10); m.seek(9); m.find(b"x", None, 2)` → panic (start 9, end 2).

## Root cause

`crates/stdlib/src/mmap.rs`:

```rust
// get_find_range (L774): each bound clamped independently, no ordering check
let start = start.saturated_at(size);      // in [0, size]
let end   = end.saturated_at(size);        // in [0, size]
// ...
// find (L795) / rfind (L812):
let buf = &mmap.as_ref().unwrap().as_slice()[start..end];   // panics if start > end
```

(The `.as_ref().unwrap()` on the same line is **not** the panic vector — it sits under the
`check_valid(vm)?` guard, which holds the lock and has already verified `is_some()`. The real
vector is the `[start..end]` slice with `start > end`.)

## Divergence from CPython

CPython returns `-1` (not found) for an empty or inverted range; it does not crash.

## Suggested fix

Enforce the ordering in `get_find_range` (matching CPython's empty-range semantics):

```rust
let end = end.max(start);   // an inverted range is empty -> "not found"
```

## Impact

A single hostile `find`/`rfind` call aborts the interpreter — a denial of service on any code
that exposes `mmap.find` to untrusted bounds.

## Prior art

No hit in the RustPython tracker. Appears unreported. Not in the fuzzing catalog.
