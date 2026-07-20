# RPYR-0012 — itertools.cycle (and the whole itertools iterator cluster) leak
# reference cycles. PyItertoolsCycle (itertools.rs:242) owns iter: PyIter +
# saved: PyRwLock<Vec<PyObjectRef>> but declares no GC Traverse, so a cycle
# routed through it is uncollectable. CPython's cycle has tp_traverse -> collects.
#
# cycle is the exemplar: `saved` accumulates yielded items POST-construction
# (itertools.rs:268), so a self-cycle is injectable after the object exists.
import gc
import weakref
import itertools


class Node:  # weakref-able, has traverse
    pass


def probe(build, name):
    root, w = build()          # build() -> (root, weakref to a node inside the cycle)
    del root
    gc.collect()
    alive = w() is not None
    print(f"  {name:28} node_alive_after_collect={str(alive):5} -> {'LEAKED' if alive else 'collected'}")


def ctrl():                    # user-class self-cycle (has traverse) — positive control
    n = Node(); n.self = n; return n, weakref.ref(n)

def cycle_embed():             # itertools.cycle -> saved -> node -> cycle
    d = []
    c = itertools.cycle(d)
    n = Node(); n.c = c
    d.append(n)
    next(c)                    # c.saved = [n]  => c <-> n cycle
    return c, weakref.ref(n)


gc.collect()
probe(ctrl, "user-class(ctrl)")
probe(cycle_embed, "itertools.cycle")
# RustPython: itertools.cycle row reports LEAKED; control collected.
# CPython:    both collected.
