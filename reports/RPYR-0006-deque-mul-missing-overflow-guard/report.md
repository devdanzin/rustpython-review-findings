# RPYR-0006 — `collections.deque(...) * n` aborts on a capacity overflow

Every repeatable sequence in RustPython (`list`, `tuple`, `str`, `bytes`, `array`) routes its
`*`/`*=` through the guarded trait methods `SequenceExt::mul` / `SequenceMutExt::imul`, which
reject an oversized result. `deque` is the lone exception: it hand-rolls `_mul` and applies
only the `isize`-overflow check, not the memory-size guard — so a large multiplier aborts the
interpreter.

## Reproducer

```python
import sys
from collections import deque
deque([0]) * sys.maxsize          # (or: d = deque([0]); d *= sys.maxsize)
```

```
thread 'main' panicked at .../library/alloc/src/raw_vec/mod.rs:28:5:
capacity overflow
```

The guarded twins raise cleanly: `[0] * sys.maxsize` and `(0,) * sys.maxsize` both raise
`MemoryError`. Only `deque` panics.

## Root cause

`crates/vm/src/stdlib/_collections.rs`, `PyDeque::_mul`:

```rust
let mul_len = check_repeat_or_overflow_error(len, n)?;    // only the isize guard
// ... for an unbounded deque (maxlen == None):
deque.iter().cycle().take(mul_len).collect::<VecDeque<_>>()   // pre-allocs from size-hint
```

`check_repeat_or_overflow_error(len, n)` guards `len * n` against `isize` overflow, but a
small `len` with a huge `n` passes it (`len == 1`, `n == sys.maxsize` → `MAX / n == 1`,
`1 > 1` is false). Then `.take(mul_len).collect::<VecDeque>()` pre-allocates capacity from the
iterator's lower size-hint (`mul_len`), and `mul_len * size_of::<PyObjectRef>()` overflows
`isize::MAX` → `VecDeque`'s capacity-overflow path → panic.

## Divergence from CPython

CPython raises `MemoryError` for `deque([0]) * sys.maxsize`.

## Suggested fix

Apply the same guard the sibling sequences use, before building the iterator:

```rust
if n > 1 && deque.len().saturating_mul(size_of::<PyObjectRef>()) >= MAX_MEMORY_SIZE / n {
    return Err(vm.new_memory_error(String::new()));
}
```

## The guarded twin (fix pattern already in the tree)

`crates/vm/src/sequence.rs`'s `mul`/`imul` carry the `n > 1 && size_of_val >= MAX_MEMORY_SIZE / n`
guard, and RustPython PR **#8270** ("Fix overflow handling for inplace sequence repetition")
added exactly this guard to `SequenceMutExt::imul` **four days before the reviewed commit**.
`deque` never adopted it.

## How the toolkit found it — and why the scanner alone couldn't

The abort originates inside `std`'s allocator (`raw_vec`), with no `.unwrap()`/`panic!` token
in RustPython's own source, so the pattern scanner cannot see it. The **git-history-analyzer**
caught it: its similar-bug detection took the fresh seed fix (#8270, 4 days old) and found the
one sequence that never got the guard.

## Prior art

The *sibling* fix is RustPython PR #8270; this `deque` instance appears unreported. Not in the
fuzzing catalog.
