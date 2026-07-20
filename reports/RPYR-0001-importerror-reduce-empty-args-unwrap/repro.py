# RPYR-0001 — ImportError().__reduce__() aborts the interpreter.
# get_arg(0).unwrap() on an empty args tuple (exceptions.rs, __reduce__).
# CPython returns (ImportError, ()); RustPython panics.
import pickle
pickle.dumps(ImportError())        # -> panic: exceptions.rs __reduce__ get_arg(0).unwrap()
# ImportError().__reduce__()       # the direct path; inherited by ModuleNotFoundError
