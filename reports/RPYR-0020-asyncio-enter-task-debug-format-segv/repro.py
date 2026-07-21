# RPYR-0020 — _asyncio._enter_task {:?} reaches the unsound PyAtomicRef Debug (RUSTPY-0018).
# _enter_task formats an arbitrary `task` with {:?} in its "already running" error (_asyncio.rs:2491).
# A PyFunction's `code: PyAtomicRef` is always populated, so the unsound .cast::<T>() at
# object/ext.rs:278 misreads a Py<PyCode>* -> garbage deref -> SIGSEGV.
# (A fresh coroutine's `exception` is None -> prints harmlessly -> no crash; the arg TYPE matters.)
import _asyncio
import asyncio

loop = asyncio.new_event_loop()
async def c(): pass
def g(): pass                        # populated PyAtomicRef in `code`

_asyncio._enter_task(loop, c())      # set the current task
_asyncio._enter_task(loop, g)        # formats g with {:?} -> SIGSEGV on RustPython; CPython: RuntimeError
print("no crash")                    # NOT REACHED on RustPython
