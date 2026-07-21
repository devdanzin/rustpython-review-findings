# RPYR-0016 — classmethod missing GC traverse (classmethod.rs:30).
# A cycle through a classmethod's wrapped callable is uncollectable on RustPython,
# because classmethod declares no `traverse` (its sibling staticmethod does).
import gc
import weakref


def probe(build, name):
    w = build()
    gc.collect()
    alive = w() is not None
    print(f"  {name:34s} alive_after_collect={str(alive):5} -> {'LEAKED' if alive else 'collected'}")


def control():                       # user-class self-cycle (positive control)
    class Node: pass
    n = Node(); n.self = n
    w = weakref.ref(n); del n
    return w


def classmethod_cycle():             # n -> cm -> f -> n
    class Node: pass
    n = Node()
    def f(cls): pass
    f.ref = n
    cm = classmethod(f)
    n.cm = cm
    w = weakref.ref(n); del n, f, cm
    return w


def staticmethod_cycle():            # the twin: staticmethod HAS traverse -> collects
    class Node: pass
    n = Node()
    def f(): pass
    f.ref = n
    sm = staticmethod(f)
    n.sm = sm
    w = weakref.ref(n); del n, f, sm
    return w


probe(control, "control (user self-cycle)")
probe(classmethod_cycle, "classmethod callable cycle")     # RustPython: LEAKED
probe(staticmethod_cycle, "staticmethod callable cycle")   # both: collected
