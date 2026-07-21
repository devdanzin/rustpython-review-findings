# RPYR-0019 — os.posix_spawn eager-collect abort (posix.rs:1403/1409/1417).
# posix_spawn binds argv/setsigdef/setsigmask as eager ArgIterable and materializes
# before validating -> an infinite iterable OOMs RustPython (SIGABRT); CPython rejects O(1).
# UNPRIVILEGED (unlike setgroups/RUSTPY-0016).
import os
import itertools

# argv: RustPython materializes the whole thing -> OOM -> SIGABRT.
# CPython: TypeError "posix_spawn: argv must be a tuple or list" in ~0.1s.
os.posix_spawn('/bin/true', map(str, itertools.count()), os.environ)

# --- cheap type-divergence check (safe, no OOM) ---
#   a finite generator argv is ACCEPTED + materialized by RustPython (runs),
#   but CPython rejects the type immediately:
#   os.posix_spawn('/bin/true', (str(x) for x in range(3)), os.environ)
#
# --- setsigdef / setsigmask collect-then-validate ---
#   os.posix_spawn('/bin/true', ['true'], os.environ, setsigdef=itertools.count())
#     RustPython: SIGABRT;  CPython: ValueError "signal number 0 out of range" at element 0
