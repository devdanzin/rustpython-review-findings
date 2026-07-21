# RPYR-0015 — genericalias make_parameters eager unguarded recursion.
# RustPython computes __parameters__ eagerly at subscript and recurses into nested
# list/tuple args with no guard (genericalias.rs:329) -> native stack overflow -> SIGSEGV.
# RustPython-only: CPython computes __parameters__ lazily, so `list[L]` alone is fine there.

L = []
L.append(L)          # self-referential
list[L]              # SIGSEGV on RustPython (CPython: fine — lazy params; crashes only on .__parameters__ = #154275)

# non-cyclic variant (unguarded depth, not cycle-specific):
#   x = [0]
#   for _ in range(300_000): x = [x]
#   list[x]          # SIGSEGV
