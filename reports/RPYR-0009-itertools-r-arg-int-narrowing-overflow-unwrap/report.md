# RPYR-0009 — `itertools.combinations`/`combinations_with_replacement`/`permutations` panic on an oversized `r`

Three `itertools` constructors accept a Python integer `r` and reject a **negative** `r` with a
clean `ValueError`, but never reject an `r` that is **too large to fit a `usize`**. Immediately
after the negative check they narrow with `r.to_usize().unwrap()`. A Python int is unbounded, so
`r = 2**64` passes the negative guard, `to_usize()` returns `None`, and the `.unwrap()` panics —
aborting the whole interpreter. This is one root cause reproduced in three sibling functions.

## Reproducer

```python
import itertools
itertools.combinations(range(5), 2**64)                    # itertools.rs:1205
itertools.combinations_with_replacement(range(5), 2**64)   # itertools.rs:1306
itertools.permutations(range(5), 2**64)                    # itertools.rs:1412
```

Each line, run alone, aborts the VM:

```
thread 'main' panicked at crates/vm/src/stdlib/itertools.rs:1205:34:
called `Option::unwrap()` on a `None` value
```

(`combinations_with_replacement` → `:1306:34`, `permutations` → `:1412:36`; identical message.)

## Root cause

`crates/vm/src/stdlib/itertools.rs` — the same shape in all three `Constructor::py_new`:

```rust
// combinations (:1201) / combinations_with_replacement (:1302)
let r = r.as_bigint();
if r.is_negative() {
    return Err(vm.new_value_error("r must be non-negative"));   // negative side guarded
}
let r = r.to_usize().unwrap();                                  // too-large side NOT guarded -> panic

// permutations (:1409), inside `match r.flatten() { Some(r) => { ... } }`
if val.is_negative() {
    return Err(vm.new_value_error("r must be non-negative"));
}
val.to_usize().unwrap()                                         // same hole
```

`to_usize()` (`num_traits::ToPrimitive` on `BigInt`) returns `None` whenever the value does not
fit the target width. The negative branch is handled; the overflow branch reaches `unwrap()`.

## Divergence from CPython

CPython 3.14.4 raises, in all three cases:

```
OverflowError: Python int too large to convert to C ssize_t
```

RustPython should raise the same (an `OverflowError`), not abort.

## Suggested fix

Replace each `.to_usize().unwrap()` with a fallible conversion that surfaces the overflow as a
Python exception — the same idiom every other `to_usize()` in stdlib already uses:

```rust
let r = r.to_usize()
    .ok_or_else(|| vm.new_overflow_error("r too large".to_owned()))?;
```

## Impact

A single hostile call to any of the three constructors aborts the interpreter — a denial of
service on any code path that forwards an untrusted count into `itertools`.

## Why one report, three signatures

Identical mechanism (negative-only guard + `to_usize().unwrap()`), identical trigger (`2**64`),
identical CPython divergence (`OverflowError`), identical fix. Grouped as one root cause with
three Python-facing signatures — mirroring RPYR-0004 (mmap `find`/`rfind`).

## Provenance & prior art

Surfaced by the whole-tree `panic-site-auditor` run (int-narrowing signal). The
`git-history-analyzer` overlay established three corroborating facts:

- **These three are the complete population** — a tree-wide sweep for
  `to_usize()/to_u32()/to_u64().unwrap()` on Python-controlled ints returns *exactly* these
  sites; every other `to_usize()` in stdlib discharges the `Option` safely.
- **A maintainer-fixed twin of the same class exists** — #6561 (7b36c9e, 2025-12-28) "Handle
  oversized `__hash__` results without panicking" and #7633 (71380be) "Fix process abort on
  large float format precision". The maintainers already treat this int-narrowing-abort shape
  as a bug; `itertools` was simply missed.
- **The bodies are long latent** — `combinations` and `permutations` last touched 2020-04-27
  (~6 years).

No hit in the RustPython issue tracker; appears unreported. Same class as fuzzing-catalog
`RUSTPY-0017` (`_ctypes` int-too-large) but a distinct, previously-unrecorded location.
