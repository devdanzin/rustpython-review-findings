# RPYR-0013 — tuple.__hash__ recurses without a recursion guard.
#
# RustPython `tuple_hash` (crates/vm/src/builtins/tuple.rs:682) maps `val.hash(vm)`
# over the elements (tuple.rs:683) with no `vm.with_recursion(...)`. A deeply
# nested tuple recurses one native frame per level and overflows the stack
# (SIGSEGV) instead of raising RecursionError.
#
# The crash needs no explicit hash() call — using the tuple as a dict key or set
# member hashes it on insertion and crashes identically.
#
# Guarded twin (SAME file): `repr` enters a ReprGuard (tuple.rs:535) and `==` is
# depth-guarded, so both degrade to a clean RecursionError at this depth; only
# `hash` is unguarded. Shared with CPython (Objects/tupleobject.c:385) — filed as
# CPython #154318 (which also covers the copied-code frozendict_hash, main only).
#
# Run each stanza SEPARATELY: the SIGSEGV kills the interpreter.

DEPTH = 300_000  # stack-size dependent; ~200-300k on a default 8 MB stack

t = ()
for _ in range(DEPTH):
    t = (t,)

# --- the crash (pick one) ---
hash(t)              # SIGSEGV
# {t: 1}             # SIGSEGV  (dict key — insertion hashes it)
# {t}                # SIGSEGV  (set member)
# frozenset({t})     # SIGSEGV

print("NOT REACHED")

# --- guarded twins, for contrast (do NOT crash — clean RecursionError) ---
#   repr(t)          # RecursionError: maximum recursion depth
#   t == t           # RecursionError: maximum recursion depth
