# RPYR-0004 — mmap.find/rfind slice-panic when start > end.
# get_find_range clamps each bound with saturated_at(size) but never enforces
# start <= end, so slice[start..end] panics (mmap.rs:795 find / :812 rfind).
# CPython returns -1 for an inverted range.
import mmap
mmap.mmap(-1, 10).find(b"x", 5, 2)         # -> panic: mmap.rs:795 slice starts at 5 ends at 2
# mmap.mmap(-1, 10).rfind(b"x", 8, 3)      # same root cause, mmap.rs:812
