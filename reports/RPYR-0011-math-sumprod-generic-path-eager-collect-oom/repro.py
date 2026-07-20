# RPYR-0011 — math.sumprod eager-collect OOM (big-int generic path).
# sumprod's generic path (math.rs:733/735) collects both remaining iterables into
# Vecs before multiplying, once an operand exceeds i64::MAX. CPython streams O(1).
#
# Unbounded form (uncatchable SIGABRT on RustPython; CPython streams forever at O(1)):
import math
import itertools

# count(10**19) yields ints always > i64::MAX -> forces the big-int generic path.
math.sumprod(itertools.count(10**19), itertools.count(10**19))
# RustPython: "memory allocation ... failed" -> SIGABRT (exit 134)
# CPython 3.14.4: streams, O(1) memory, runs forever (no OOM)

# --- Finite O(N)-vs-O(1) proof (run separately, e.g. N=8_000_000): ---
# import resource
# N = 8_000_000; big = 10**19
# def gen():
#     for _ in range(N):
#         yield big
# math.sumprod(gen(), gen())
# print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, "MB")
# RustPython grows ~16 MB/million (146 MB @ 8M); CPython flat ~11 MB.
