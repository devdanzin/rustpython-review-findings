# RPYR-0007 — seq * n aborts (SIGABRT) on an unallocatable-but-in-range size.
# SequenceExt::mul (sequence.rs) rejects totals > isize::MAX BYTES (-> MemoryError)
# but an 8 TB request (10**12 * 8 bytes < isize::MAX) passes the guard, then
# Vec::with_capacity hits handle_alloc_error -> abort. Affects tuple/list/bytes/bytearray.
# CPython raises MemoryError.
(1,) * (10**12)                            # -> abort: memory allocation of 8000000000000 bytes failed
# [0] * (10**12)                           # same shared mul path
