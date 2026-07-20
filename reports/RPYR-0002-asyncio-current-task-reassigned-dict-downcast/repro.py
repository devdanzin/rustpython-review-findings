# RPYR-0002 — _asyncio.current_task() aborts when _current_tasks is rebound.
# downcast::<PyDict>().unwrap() on a Python-reassignable module attribute
# (_asyncio.rs:2408). The guarded twins _enter_task/_leave_task/_swap_current_task
# use `if let Ok(..)`; only current_task unwraps.
import _asyncio
_asyncio._current_tasks = 42               # rebind the internal dict to a non-dict
_asyncio.current_task(loop=object())       # no running loop + explicit loop -> slow path -> panic
