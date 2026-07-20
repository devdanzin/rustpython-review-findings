# RPYR-0003 — Future.__await__().throw(E) aborts when E.__new__ returns a
# non-exception. downcast().unwrap() on the exc_type.call(()) result
# (_asyncio.rs:1081). The gate checks exc_type is a BaseException subclass, but
# __new__ can return anything. CPython raises TypeError.
import _asyncio
f = _asyncio.Future(loop=object())
class E(Exception):
    def __new__(cls, *a):
        return 42
f.__await__().throw(E)                     # -> panic: exc.downcast().unwrap() on PyInt 42
