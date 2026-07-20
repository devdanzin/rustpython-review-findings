# RPYR-0008 (LEAD — not yet reproduced) — Future.result()/exception() on a
# pending future routes through new_invalid_state_error (_asyncio.rs:2737), which
# downcast().unwrap()s the result of calling the InvalidStateError type. If
# asyncio.exceptions.InvalidStateError is monkeypatched to a callable returning a
# non-BaseException, the unwrap panics. Reasoned from the code + the RPYR-0003
# shape; a working trigger still needs to route through the pending-future path.
import _asyncio
f = _asyncio.Future(loop=object())
# TODO: monkeypatch asyncio.exceptions.InvalidStateError to a non-exception
#       factory, then f.result() on the still-pending future.
f.result()
