# RPYR-0007 — `seq * n` aborts (SIGABRT) on an unallocatable-but-in-range size

The shared `SequenceExt::mul` guard converts an *overflowing* repeat (`> isize::MAX` bytes)
into a Python `MemoryError`, but it has a hole: a merely **unallocatable** size that is still
under the byte ceiling (e.g. 8 TB) passes the guard and then hits `Vec::with_capacity`'s
allocation-failure abort. Because `mul` is shared, this affects `tuple`, `list`, `bytes`, and
`bytearray`.

## Reproducer

```python
(1,) * (10**12)          # or: [0] * (10**12)
```

```
memory allocation of 8000000000000 bytes failed
```

(SIGABRT, exit 134.) The boundary confirms the guard's intent and its hole:
`(1,) * sys.maxsize` (over the byte ceiling) raises `MemoryError` cleanly; `(1,) * (10**12)`
(8 TB, under `isize::MAX` bytes) aborts.

## Root cause

`crates/vm/src/sequence.rs`, `SequenceExt::mul`:

```rust
fn mul(&self, vm: &VirtualMachine, n: isize) -> PyResult<Vec<T>> {
    let n = vm.check_repeat_or_overflow_error(self.as_ref().len(), n)?;
    // guard (L103): rejects size_of_val(elements) >= MAX_MEMORY_SIZE / n
    //   where MAX_MEMORY_SIZE = isize::MAX -> only totals over ~9.2 EB become MemoryError
    let mut v = Vec::with_capacity(n * self.as_ref().len());   // L107: 8 TB alloc -> abort
    for _ in 0..n { v.extend_from_slice(self.as_ref()); }
    Ok(v)
}
```

The guard's clear intent is to turn an oversized repeat into a Python `MemoryError`, but it
only catches sizes exceeding `isize::MAX` *bytes*. An 8 TB request is far below that ceiling
yet cannot be allocated, so `Vec::with_capacity` calls `handle_alloc_error`, which aborts.

## Divergence from CPython

CPython raises `MemoryError` for `(1,) * (10**12)`.

## Suggested fix

Use a fallible reservation and map the failure to a Python `MemoryError` — this fixes
`tuple`/`list`/`bytes`/`bytearray` at once:

```rust
let total = n.checked_mul(self.as_ref().len()).ok_or_else(|| vm.new_memory_error(String::new()))?;
let mut v = Vec::new();
v.try_reserve_exact(total).map_err(|_| vm.new_memory_error(String::new()))?;
for _ in 0..n { v.extend_from_slice(self.as_ref()); }
```

## Severity note

This is more an allocator-policy divergence than a logic error, and it is broad (any large
sequence repeat), so it is filed as an `abort` rather than a targeted `.unwrap()` bug. It is
still a Python-triggerable interpreter abort where CPython degrades gracefully.

## How the toolkit found it

Surfaced by the **panic-site-auditor**'s Phase-4 (beyond-the-scanner) hand audit while tracing
tuple's `*` path — the scanner's pattern set does not match the raw `Vec::with_capacity` abort.

## Prior art

No hit in the RustPython tracker. Appears unreported. Not in the fuzzing catalog.
