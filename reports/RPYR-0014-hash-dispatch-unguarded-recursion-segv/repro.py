# RPYR-0014 — hash dispatch unguarded (protocol/object.rs:695).
# Any element-wise __hash__ overflows the native stack -> SIGSEGV, because the hash
# dispatch lacks the with_recursion guard that repr(:383) and compare(:291) have.
# Run each stanza separately: the SIGSEGV kills the interpreter.

# --- GenericAlias.__hash__ (genericalias.rs:632) ---
x = int
for _ in range(400_000):
    x = list[x]
hash(x)              # SIGSEGV  (also SIGSEGV on CPython via tuple_hash -> #154318)

# --- slice.__hash__ (slice.rs:270; hashable since 3.12) ---
#   s = slice(0)
#   for _ in range(2_000_000): s = slice(s)
#   hash(s)          # SIGSEGV

# --- guarded twins (do NOT crash — clean RecursionError) ---
#   repr(x)          # RecursionError (object.rs:383 guards repr dispatch)
#   x == x           # RecursionError (object.rs:291 guards compare dispatch)
