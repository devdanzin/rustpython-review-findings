# RPYR-0005 — mmap.move(dest, src, count) aborts when dest/src > size.
# `size - dest` unsigned subtraction underflows (debug: overflow panic; release:
# wraps past the guard, then mmap[dest..] OOB slice at mmap.rs:903).
# The safe twin write() (same file) checks `pos > size || size - pos < len` first.
# CPython raises ValueError.
import mmap
mmap.mmap(-1, 10).move(20, 0, 1)           # -> panic: mmap.rs:903 range start 20 out of range for len 10
