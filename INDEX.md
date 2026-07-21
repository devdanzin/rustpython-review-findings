# RustPython review findings — index

Soundness and crash bugs in the **RustPython interpreter's own Rust source**, found by static review with [**rustpy-review-toolkit**](https://github.com/devdanzin/rustpy-review-toolkit) and then reproduced on the interpreter. Each row links to a self-contained report (root cause, minimal Python reproducer, the Rust panic output, and a suggested fix).

_19 reproduced bug(s) + 1 lead(s). Generated 2026-07-20._

These are **disjoint from** and complementary to the fuzzing catalog in [`rustpython-findings`](https://github.com/devdanzin/rustpython-findings) (`RUSTPY-*`) — none of the bugs below appear there. The **Found by** column records which toolkit agent surfaced each one.

Status: `confirmed` (reproduced on the binary) · `#N` (RustPython issue open) · **FIXED** `commit` · `lead` (traced, not yet reproduced).


## Python-reachable panics

| Report | Title | Site | Found by | Status |
|---|---|---|---|---|
| [RPYR-0001](reports/RPYR-0001-importerror-reduce-empty-args-unwrap/report.md) | `ImportError().__reduce__()` unwraps empty args | `exceptions.rs:1872` | panic-site-auditor | confirmed (reproduced) |
| [RPYR-0002](reports/RPYR-0002-asyncio-current-task-reassigned-dict-downcast/report.md) | `asyncio.current_task()` downcasts a reassignable module attr | `_asyncio.rs:2408` | panic-site-auditor, git-history-analyzer | confirmed (reproduced) |
| [RPYR-0003](reports/RPYR-0003-asyncio-futureiter-throw-new-foreign-downcast/report.md) | `FutureIter.throw()` downcasts a `__new__`-controlled result | `_asyncio.rs:1081` | scan_panic_sites.py, git-history-analyzer | confirmed (reproduced) |
| [RPYR-0004](reports/RPYR-0004-mmap-find-rfind-start-gt-end-slice/report.md) | `mmap.find(start>end)` slice panic | `mmap.rs:795 mmap.rs:812` | panic-site-auditor | confirmed (reproduced) |
| [RPYR-0005](reports/RPYR-0005-mmap-move-dest-underflow-oob/report.md) | `mmap.move(dest>size)` underflow → OOB | `mmap.rs:903` | git-history-analyzer | confirmed (reproduced) |
| [RPYR-0006](reports/RPYR-0006-deque-mul-missing-overflow-guard/report.md) | `deque * n` missing overflow guard | `_collections.rs:317` | git-history-analyzer | confirmed (reproduced) |
| [RPYR-0008](reports/RPYR-0008-asyncio-new-invalid-state-error-downcast/report.md) | `new_invalid_state_error` downcasts a `.call()` result (lead) | `_asyncio.rs:2737` | git-history-analyzer | lead (not yet reproduced) |
| [RPYR-0009](reports/RPYR-0009-itertools-r-arg-int-narrowing-overflow-unwrap/report.md) | `itertools.combinations(range(5), 2**64)` panic | `itertools.rs:1205 itertools.rs:1306 itertools.rs:1412` | panic-site-auditor, git-history-analyzer | confirmed (reproduced) |

## Aborts (SIGABRT)

| Report | Title | Site | Found by | Status |
|---|---|---|---|---|
| [RPYR-0007](reports/RPYR-0007-sequence-mul-guard-hole-abort/report.md) | shared `mul` guard-hole → SIGABRT | `sequence.rs:107` | panic-site-auditor | confirmed (reproduced) |
| [RPYR-0011](reports/RPYR-0011-math-sumprod-generic-path-eager-collect-oom/report.md) | `math.sumprod(count(),count())` OOM-abort | `math.rs:733 math.rs:735` | eager-collect-parity | confirmed (reproduced) |
| [RPYR-0017](reports/RPYR-0017-ctypes-pointer-setitem-int-narrow-abort/report.md) | ctypes `Pointer.__setitem__` int-narrow → panic-abort | `pointer.rs:692` | ctypes-ffi-auditor, panic-site-auditor | confirmed (reproduced) |
| [RPYR-0018](reports/RPYR-0018-imp-find-frozen-second-arg-unimplemented-abort/report.md) | `_imp.find_frozen` 2nd-arg → `unimplemented!()` abort | `_imp.rs:329` | panic-site-auditor | confirmed (reproduced) |
| [RPYR-0019](reports/RPYR-0019-posix-spawn-eager-collect-abort/report.md) | `os.posix_spawn` eager-collect (argv/setsigdef/setsigmask) → SIGABRT | `posix.rs:1403 posix.rs:1409 posix.rs:1417` | eager-collect-parity | confirmed (reproduced) |

## Segfaults

| Report | Title | Site | Found by | Status |
|---|---|---|---|---|
| [RPYR-0013](reports/RPYR-0013-tuple-hash-unguarded-recursion-segv/report.md) | `tuple.__hash__` unguarded recursion → SIGSEGV | `tuple.rs:683 tuple.rs:499` | recursion-guard-auditor, CPython differential / shared-crash ledger | confirmed (reproduced) |
| [RPYR-0014](reports/RPYR-0014-hash-dispatch-unguarded-recursion-segv/report.md) | hash dispatch unguarded (object.rs:695) → container `__hash__` SIGSEGV | `object.rs:695 genericalias.rs:632 slice.rs:270` | recursion-guard-auditor, git-history-analyzer | confirmed (reproduced) |
| [RPYR-0015](reports/RPYR-0015-genericalias-make-parameters-eager-recursion-segv/report.md) | genericalias `make_parameters` eager unguarded recursion → SIGSEGV (RustPy-only) | `genericalias.rs:329 genericalias.rs:295 union.rs:236` | recursion-guard-auditor | confirmed (reproduced) |
| [RPYR-0020](reports/RPYR-0020-asyncio-enter-task-debug-format-segv/report.md) | `_asyncio._enter_task` `{:?}` reaches the RUSTPY-0018 unsound Debug → SIGSEGV | `_asyncio.rs:2491 ext.rs:278` | debug-format-auditor, unsafe-soundness-auditor | confirmed (reproduced) |

## Uncollectable-cycle leaks (missing GC traverse)

| Report | Title | Site | Found by | Status |
|---|---|---|---|---|
| [RPYR-0010](reports/RPYR-0010-collections-deque-defaultdict-missing-gc-traverse/report.md) | `deque`/`defaultdict` cycle leak (no GC traverse) | `_collections.rs:33 _collections.rs:759` | gc-traverse-auditor, git-history-analyzer | confirmed (reproduced) |
| [RPYR-0012](reports/RPYR-0012-itertools-cycle-missing-gc-traverse/report.md) | `itertools.cycle` self-cycle leak (no GC traverse) | `itertools.rs:242` | gc-traverse-auditor, git-history-analyzer | confirmed (reproduced) |
| [RPYR-0016](reports/RPYR-0016-classmethod-missing-gc-traverse-leak/report.md) | `classmethod` missing GC traverse → cycle leak (staticmethod has it) | `classmethod.rs:30` | git-history-analyzer, gc-traverse-auditor | confirmed (reproduced) |
