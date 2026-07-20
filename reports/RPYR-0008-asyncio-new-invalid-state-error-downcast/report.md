# RPYR-0008 (lead) — `new_invalid_state_error` downcasts a called-type result

> **Status: lead — reasoned from the code, not yet reproduced end-to-end.** The crash path is
> analysed below; a working trigger (routing through the pending-future "not ready" path with
> a monkeypatched `InvalidStateError`) has not yet been isolated. It is **not** contributed to
> `known_panics.tsv` until reproduced.

`new_invalid_state_error` builds the `InvalidStateError` that `Future.result()` /
`Future.exception()` raise when the future is not done. It resolves the `InvalidStateError`
type from `asyncio.exceptions`, calls it, and then `downcast().unwrap()`s the result — but it
handles *every other* failure path defensively. If `asyncio.exceptions.InvalidStateError` is
rebound to a callable that returns a non-`BaseException`, the success branch's `.unwrap()`
would abort the interpreter.

## Intended reproducer (to be completed)

```python
import _asyncio
f = _asyncio.Future(loop=object())
# TODO: monkeypatch asyncio.exceptions.InvalidStateError to a factory returning a
#       non-exception, then f.result() on the still-pending future.
f.result()
```

## Root cause (analysis)

`crates/stdlib/src/_asyncio.rs`, `new_invalid_state_error` (L2737):

```rust
match /* resolve + call InvalidStateError */ {
    Ok(exc) => exc.downcast().unwrap(),                 // <-- panics if the call returned non-exc
    Err(_)  => vm.new_runtime_error("...".to_owned()),  // defensive
    _       => vm.new_runtime_error("...".to_owned()),  // defensive
}
```

The function is defensive when the type is missing or the call fails, but the success branch
assumes the returned object is a `BaseException`. This is the **same shape as RPYR-0003** — a
`downcast().unwrap()` on the result of calling a Python-resolved type, which `__new__` can
subvert.

## Divergence from CPython

CPython raises `InvalidStateError` ("Result is not set" / "Exception is not set") — a normal
exception, not a crash.

## Why it is a lead, not confirmed

- `new_invalid_state_error` is an **internal-tier** free helper (not `#[pyfunction]`/`#[pymethod]`),
  so the panic scanner default-silences it. The **git-history-analyzer** surfaced it by
  pattern-matching the downcast-of-called-type shape and noting it backs the common
  "not ready" path (so its blast radius is larger than any single method).
- The end-to-end trigger requires reaching this helper via `Future.result()`/`exception()` on
  a *pending* future while `InvalidStateError` is monkeypatched — that routing has not yet been
  reduced to a one-liner.

## Next step

Build the trigger, capture the panic, flip `status` to `confirmed`, and add the signature to
`known_panics.tsv`. If it proves unreachable in practice, record it in `catalog/non_bugs.md`
with the reason.

## Prior art

No hit in the RustPython tracker. Not in the fuzzing catalog.
