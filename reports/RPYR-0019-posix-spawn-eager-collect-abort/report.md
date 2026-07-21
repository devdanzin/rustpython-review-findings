# RPYR-0019 — `os.posix_spawn` eager-collect → SIGABRT (unprivileged)

`os.posix_spawn` binds three of its parameters — `argv`, `setsigdef`, `setsigmask` — as eager
`ArgIterable` and materializes each fully **before** validating it (`crates/vm/src/stdlib/posix.rs`,
`#[derive(FromArgs)] struct PosixSpawnArgs`). An infinite or huge iterable therefore balloons RustPython to
OOM → **SIGABRT**, where CPython rejects it in O(1). Unlike the confirmed `setgroups` gap (RUSTPY-0016,
root-only), `posix_spawn` needs **no privilege**, so it's the more weaponizable member of the class.

Same class as **RPYR-0011** (math.sumprod) and the RPYR-0012…0016 eager-collect-parity gaps.

## Reproducer

```python
import os, itertools
os.posix_spawn('/bin/true', map(str, itertools.count()), os.environ)   # RustPython: OOM -> SIGABRT
#                                                                       # CPython: TypeError in ~0.1s
```

## Evidence (differential)

| input | RustPython 0.5.0 | CPython 3.14.4 |
|---|---|---|
| argv = finite generator `(str(x) for x in range(3))` | **accepted, materialized, ran** | `TypeError: posix_spawn: argv must be a tuple or list` (O(1)) |
| argv = `map(str, itertools.count())` | **OOM → SIGABRT** | TypeError ~0.1s |
| `setsigdef = itertools.count()` | collects-then-validates → SIGABRT | `ValueError: signal number 0 out of range` at element 0 (O(1)) |

RustPython *accepts* a generator argv and materializes it (confirmed with a tiny finite generator that ran
to completion); on an infinite one that materialization never terminates. CPython rejects the argv type
before touching the iterable.

## Root cause

`PosixSpawnArgs` (a `#[derive(FromArgs)]` struct, invisible to the eager-collect scanner) types argv as
`ArgIterable<OsPath>` (bound `posix.rs:1403`, collected ~`:1525`) and setsigdef/setsigmask as
`ArgIterable<i32>` (`:1409`/`:1417`, collected ~`:1484`/`:1513`). Each is collected into a `Vec` up front,
then validated.

## Suggested fix

- **argv:** type it as `Either<PyListRef, PyTupleRef>` — an O(1) type reject that matches CPython's argv
  contract *and* the sibling `execv`/`execve` in the same file (the in-file twin).
- **setsigdef/setsigmask:** validate each signal while streaming (the sigset is fixed-size) instead of
  collect-then-check, so a bad or infinite input is rejected in O(1).

## Impact

An unprivileged one-line `os.posix_spawn` call with an infinite iterable argument aborts the interpreter via
OOM (SIGABRT). CPython treats all three as O(1) rejections.

## Provenance

Surfaced by the eager-collect-parity auditor in the informed explore — 3 new gaps inside the
`#[derive(FromArgs)]` struct the scanner can't see, reproduced live. Class sibling of [[RPYR-0011]];
fuzzer RUSTPY-0016 (setgroups) is the privileged cousin. The both-balloon `file_actions` case (Class J) is
correctly out of scope.
