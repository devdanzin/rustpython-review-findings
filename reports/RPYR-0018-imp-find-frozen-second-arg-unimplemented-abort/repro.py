# RPYR-0018 — _imp.find_frozen 2nd-arg unimplemented!() abort (_imp.rs:329).
# The withdata guard tests `.is_some()` (presence), not the value, so ANY 2nd arg
# reaches unimplemented!() -> VM abort. CPython takes exactly 1 arg -> TypeError.
import _imp

_imp.find_frozen('_frozen_importlib', True)   # RustPython: abort (exit 101); CPython: TypeError
print("no crash")                              # NOT REACHED on RustPython
