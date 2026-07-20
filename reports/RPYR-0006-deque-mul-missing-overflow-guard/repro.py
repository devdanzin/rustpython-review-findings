# RPYR-0006 — collections.deque(...) * n aborts on a capacity overflow.
# deque._mul only calls check_repeat_or_overflow_error (the isize guard); it is
# missing the size_of_val >= MAX_MEMORY_SIZE / n guard that every other sequence
# has (list/tuple/str/bytes/array route through SequenceExt::mul). The twin guard
# landed in sequence.rs 4 days before the reviewed commit (RustPython #8270).
# CPython raises MemoryError.
import sys
from collections import deque
deque([0]) * sys.maxsize                   # -> panic: raw_vec capacity overflow (_collections.rs _mul)
