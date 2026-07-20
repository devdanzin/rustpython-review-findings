# RPYR-0010 — collections.deque / collections.defaultdict leak reference cycles.
# Their RustPython payloads (_collections.rs:33 deque, :759 defaultdict) own Python
# refs but declare no GC `Traverse`, so the cycle collector cannot trace through them
# and a cycle routed through either object is uncollectable. CPython collects them.
#
# Weakref-strength differential: an object still alive after `del` + gc.collect() leaked.
# The user-class control and list/dict baselines collect on both interpreters (harness sound).
import gc
import weakref
from collections import deque, defaultdict


class Node:  # weakref-able, has traverse
    pass


def probe(build, name):
    root, w = build()          # build() -> (root, weakref to a node inside the cycle)
    del root
    gc.collect()
    alive = w() is not None
    print(f"  {name:24} alive_after_collect={str(alive):5} -> {'LEAKED' if alive else 'collected'}")


def ctrl():                    # user-class self-cycle (has traverse) — positive control
    n = Node(); n.self = n; return n, weakref.ref(n)

def deque_self():              # deque self-cycle; weakref the deque directly (HAS_WEAKREF)
    d = deque(); d.append(d); return d, weakref.ref(d)

def deque_embed():             # deque -> node -> deque
    d = deque(); n = Node(); n.ref = d; d.append(n); return d, weakref.ref(n)

def defaultdict_embed():       # defaultdict -> node -> defaultdict (defaultdict is not weakref-able)
    d = defaultdict(int); n = Node(); n.ref = d; d["x"] = n; return d, weakref.ref(n)


gc.collect()
probe(ctrl, "user-class(ctrl)")
probe(deque_self, "deque(self-cycle)")
probe(deque_embed, "deque(embedded node)")
probe(defaultdict_embed, "defaultdict(embed node)")
# RustPython: deque + defaultdict rows report LEAKED; control collected.
# CPython:    every row reports collected.
