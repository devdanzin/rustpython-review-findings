# RPYR-0005 — `mmap.move(dest, src, count)` aborts on an unclamped subtraction

`mmap.move` takes three Python-supplied integers and its bounds guard uses **unsigned
subtraction** without first checking the high side: `if size - dest < cnt || size - src < cnt`.
When `dest > size` (or `src > size`), `size - dest` underflows, the guard is bypassed, and the
subsequent slice write goes out of bounds and aborts the interpreter.

## Reproducer

```python
import mmap
mmap.mmap(-1, 10).move(20, 0, 1)
```

```
thread 'main' panicked at crates/stdlib/src/mmap.rs:903:27:
range start index 20 out of range for slice of length 10
```

## Root cause

`crates/stdlib/src/mmap.rs`, `PyMmap::move_`:

```rust
// dest/src/cnt come from try_to_primitive::<usize>() (only the negative case is rejected)
if size - dest < cnt || size - src < cnt {   // size - dest UNDERFLOWS when dest > size
    return Err(vm.new_value_error(...));
}
// ...
// then a slice move indexes at `dest` -> OOB (mmap.rs:903)
```

- **Debug build** (dev profile, `overflow-checks = on`): `10 - 20` panics with
  `attempt to subtract with overflow`.
- **Release build**: `10 - 20` wraps to `usize::MAX - 9`, the `< cnt` comparison is false, the
  guard passes, and the slice write at `dest = 20` on a length-10 map hits the OOB slice at
  `mmap.rs:903`.

Either way, one call aborts the interpreter.

## Divergence from CPython

CPython raises `ValueError` for a move whose source/dest/count exceed the map.

## Suggested fix

Guard the high side first, exactly as `write()` already does in the same file:

```rust
if dest > size || src > size || size - dest < cnt || size - src < cnt {
    return Err(vm.new_value_error("data out of range".to_owned()));
}
```

## The guarded twin (fix pattern already in the file)

`write()` (mmap.rs:1150) checks `pos > size || size - pos < data.len()` — high side first —
and `flush()`'s `FlushOptions::values` uses `len.checked_sub(offset)?`. `move_` is the one
accessor that uses the raw subtraction.

## How the toolkit found it — and why the scanner alone couldn't

`move()` is a `#[pymethod]` (directly `py`-tier), but it carries **no** `.unwrap()` / `panic!`
/ `.args[` token on the offending line — the panic is an arithmetic underflow followed by a
generic slice index, neither of which is in the pattern scanner's set (a deliberate choice to
avoid false-positive flooding). The **git-history-analyzer** caught it via similar-bug
detection, keyed on the guard-idiom asymmetry (`write()` guards, `move_` does not) and the
recently-fixed sibling overflow class in `sequence.rs`. This is one of three bugs in this
catalog found by the history agent rather than the scanner — the class it structurally covers.

## Prior art

No hit in the RustPython tracker. Appears unreported. Not in the fuzzing catalog.
