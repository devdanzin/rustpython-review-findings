# RustPython review findings — index

Soundness and crash bugs in the **RustPython interpreter's own Rust source**, found by static review with [**rustpy-review-toolkit**](https://github.com/devdanzin/rustpy-review-toolkit) and then reproduced on the interpreter. Each row links to a self-contained report (root cause, minimal Python reproducer, the Rust panic output, and a suggested fix).

_7 reproduced bug(s) + 1 lead(s). Generated 2026-07-20._

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

## Aborts (SIGABRT)

| Report | Title | Site | Found by | Status |
|---|---|---|---|---|
| [RPYR-0007](reports/RPYR-0007-sequence-mul-guard-hole-abort/report.md) | shared `mul` guard-hole → SIGABRT | `sequence.rs:107` | panic-site-auditor | confirmed (reproduced) |
