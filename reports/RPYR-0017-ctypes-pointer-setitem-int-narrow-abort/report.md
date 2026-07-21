# RPYR-0017 — ctypes `Pointer.__setitem__` int-narrow → panic-abort

Assigning through a ctypes pointer (`p[i] = value`) narrows the written value to the pointee's C width with
`.expect("int too large")` (`crates/vm/src/stdlib/_ctypes/pointer.rs:690-693`). A Python int outside that
width panics, aborting the whole interpreter (exit 101), where CPython simply masks the value to the C
width and continues.

This is the **write-side face of RUSTPY-0017** (the ctypes int-narrowing class, whose reported sites are
the from-int *construction* path in `simple.rs`). It is a new site the 0017 report didn't cover — dual-found
by the ctypes-ffi and panic-site auditors.

## Reproducer

```python
import ctypes
p = ctypes.pointer(ctypes.c_int(0))
p[0] = 2**64          # RustPython: panic "int too large" -> abort (exit 101);  CPython: stores 0
```

## Evidence (differential)

| input | RustPython 0.5.0 | CPython 3.14.4 |
|---|---|---|
| `p[0] = 2**64` on `POINTER(c_int)` | **panic-abort** (`pointer.rs:692 'int too large'`, exit 101) | masks to 0, continues |

## Root cause

`crates/vm/src/stdlib/_ctypes/pointer.rs:690-693` — `Pointer.__setitem__` (`PyCPointer` AsMapping →
`setitem_by_index` → `write_value_at_address`) converts the assigned int with
`.to_u8()/.to_i16()/.to_i32()/.to_i64().expect("int too large")`. `.expect()` on the out-of-range `None`
panics. Every array/base/function write sibling in the same crate instead uses the silent
`.to_usize().unwrap_or(0)` variant — so the pointer path is the odd one out (aborts where the others
truncate).

## Suggested fix

Map the out-of-range conversion to a Python `OverflowError` instead of `.expect()` — ideally one shared
helper across `simple.rs` / `array.rs` / `pointer.rs`, which also fixes RUSTPY-0017 at once.

## Impact

A one-line pure-Python ctypes assignment aborts the interpreter. ctypes is already the one inherently
memory-unsafe module, but *this* is a clean, avoidable abort (a Python `OverflowError` is the correct
outcome, as CPython's masking demonstrates the value is representable-by-truncation).

## Provenance

Dual-found in the informed explore: the ctypes-ffi-auditor flagged it as the only `.expect()` narrowing
outside `simple.rs`, and the panic-site-auditor independently surfaced the same site. Sibling of fuzzer
RUSTPY-0017 (see `catalog/known_panics.tsv`). The silent `.unwrap_or(0)` ctypes sites are NOT this bug —
the differential showed they fail safe.
