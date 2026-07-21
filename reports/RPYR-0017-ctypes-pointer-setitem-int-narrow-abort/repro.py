# RPYR-0017 — ctypes Pointer.__setitem__ int-narrow abort (_ctypes/pointer.rs:692).
# Assigning an out-of-C-width int through a pointer panics ("int too large") -> VM abort,
# where CPython masks to the C width. Write-side face of RUSTPY-0017 (simple.rs construction side).
import ctypes

p = ctypes.pointer(ctypes.c_int(0))
p[0] = 2**64          # RustPython: panic-abort (exit 101);  CPython: stores 0 and continues
print("no crash")     # NOT REACHED on RustPython
