# tuple_hash and frozendict_hash recurse without a guard: hashing a deeply nested tuple or frozendict segfaults

<!-- Draft CPython issue. Companion to python/cpython#154275 (same class, same author).
     Post at https://github.com/python/cpython/issues/new (choose the "Crash report" template).
     Labels to expect: interpreter-core, type-crash.
     Adjust the provenance line and the python -VV output before posting. -->

# Crash report

### What happened?

`tuple.__hash__` and `frozendict.__hash__` (`frozendict` is new on `main`, gh-151722) share a bug: both hash their contents with `PyObject_Hash(...)` inside a loop that has no recursion guard (`Py_EnterRecursiveCall`). The two are the same bug rather than two coincidences — `frozendict_hash` / `frozendict_pair_hash` (`Objects/dictobject.c`) are literally commented *"Code copied from `frozenset_hash()`"* / *"Code copied from `tuple_hash()`"*, and the copy carried the missing guard along with the algorithm. So a deeply nested `tuple` or `frozendict` recurses back into the same hash function for every level until the C stack overflows (SIGSEGV) instead of raising `RecursionError`.

Both crash the same way:

```python
# tuple  (all versions)
t = ()
for _ in range(300_000):
    t = (t,)
hash(t)                          # SIGSEGV

# frozendict  (main only) — nested through VALUES
d = frozendict({0: 0})
for _ in range(300_000):
    d = frozendict({0: d})
hash(d)                          # SIGSEGV
```

Neither needs an explicit `hash()` call — ordinary use as a **dict key** or **set/frozenset element** hashes the object and crashes just the same:

```python
{t: 1}          # SIGSEGV     {t}          # SIGSEGV     frozenset({t})    # SIGSEGV
{d: 1}          # SIGSEGV     {d}          # SIGSEGV
```

No cycle is involved — these objects are immutable and merely *deeply nested*, which shows the paths are simply unguarded rather than anything cycle-specific. The exact depth is stack-size dependent (~250k on a default 8 MB stack; an ASan build overflows much sooner). `types.GenericAlias.__hash__` (`ga_hash`) hashes its `__args__` tuple, so `hash(list[list[...]])` dies in `tuple_hash` the same way.

Two things scope the bug and confirm the mechanism:

- **The sibling operations are guarded and degrade cleanly** — only hashing crashes. Tuple comparison raises `RecursionError` at *any* depth (verified to 2,000,000), never a segfault, and `repr()` has been guarded since bpo-1686386 (gh-44763):
  ```python
  a == b     # RecursionError: Stack overflow (used 16344 kB) in comparison   <- clean, catchable
  hash(a)    # SIGSEGV                                                          <- crash
  ```
- **`frozenset`, and `frozendict` nested through *keys*, are immune** — inserting an element/key requires hashing it, so those hashes are computed and cached (`ob_hash` / `entry->hash` / `ma_hash`) bottom-up at construction; the top-level `hash()` is then O(1) with no deep recursion (frozenset verified fine at depth 2,000,000). Only the positions that are *not* hashed at construction recurse at hash time: tuple elements, and frozendict **values**. This is exactly why nesting a frozendict through values crashes while nesting through keys does not.

Backtraces (ASan build, current `main`); each dies in its own hash function's unguarded self-recursion:

```
SUMMARY: AddressSanitizer: stack-overflow Objects/tupleobject.c in tuple_hash
    #0/#1/... tuple_hash  Objects/tupleobject.c:385:27   (repeats until the C stack overflows)

SUMMARY: AddressSanitizer: stack-overflow Objects/dictobject.c in frozendict_hash
    frames alternate frozendict_hash <-> frozendict_pair_hash  (repeats until the C stack overflows)
```

### Analysis

Both functions fold each contained object's hash into an accumulator with the same unguarded loop:

```c
// Objects/tupleobject.c  —  tuple_hash()                    (affects all maintained versions)
for (Py_ssize_t i = 0; i < len; i++) {
    Py_uhash_t lane = PyObject_Hash(item[i]);   // :385  <- unguarded recursion into tuple_hash
    ...
}
```

```c
// Objects/dictobject.c  —  frozendict_hash() -> frozendict_pair_hash()      (main only)
// "Code copied from frozenset_hash()" / "Code copied from tuple_hash()"
while (_PyDict_Next(op, &pos, NULL, &value, &key_hash)) {          // key_hash is cached -> keys are safe
    Py_hash_t pair_hash = frozendict_pair_hash(key_hash, value);  // :8462
    ...
}
// inside frozendict_pair_hash:
lane = PyObject_Hash(value);                    // :8427  <- unguarded recursion into frozendict_hash
```

Neither function (nor `genericaliasobject.c`) contains `Py_EnterRecursiveCall` / `Py_LeaveRecursiveCall`. `PyObject_Hash` on a nested element/value dispatches straight back into the same hash function, so the descent runs to the full nesting depth and overflows the C stack. The hash caches (`tuple->ob_hash`, `frozendict->ma_hash`) do not help: on the first hash of a freshly built nested object every level is uncached, so the whole descent still runs. `frozendict_hash` even carries a comment about *"patterns arising in nested frozendicts"*, so nested frozendicts were anticipated — just not the unbounded recursion.

This is the defect class already being fixed elsewhere by adding the guard — `_Py_make_parameters` (#154275), `_elementtree.Element.__deepcopy__` (#148801), `pyexpat` `conv_content_model` (#145986). Tuple comparison already pays for it (`do_richcompare` → `Py_EnterRecursiveCall(" in comparison")`); hashing is the one recursive path on these types that was left out — in `tuple_hash` originally, and then again in `frozendict_hash` when the code was copied.

**Fix direction (one pattern, both sites):** wrap each element/pair loop in `Py_EnterRecursiveCall(" while hashing a tuple")` / `Py_LeaveRecursiveCall()` (and the frozendict equivalent), turning the overflow into a catchable `RecursionError`, as the sibling paths do. Since the frozendict code was copied from the tuple code, fixing both together keeps them in sync and avoids the copy drifting again.

One caveat worth flagging: `tuple_hash` is a very hot path (dict/set keys), so unconditionally entering the recursion guard on every tuple hash has a measurable cost that `_Py_make_parameters` did not (`frozendict_hash` is far colder). Comparison already accepts this cost, so parity is defensible, but a benchmark should decide between the straightforward guard and a cheaper variant (e.g. only guarding when a contained object is itself a container).

I audited every `PyObject_Hash()` call site in `Objects/`, `Modules/`, and `Python/`: `tuple_hash` and `frozendict_hash` are the only two recursive hash-function loops that lack the guard. All other sites (set/dict/OrderedDict lookup and insertion, `functools.lru_cache` key hashing, frame locals) hash a single key at insertion/lookup time — they cache and do not self-recurse (lru_cache key hashing delegates to `tuple_hash`, so it shares this root cause rather than being independent).

Not free-threading- or JIT-specific: reproduces on the default and free-threaded builds, release and debug. `tuple_hash` affects all maintained versions; `frozendict_hash` affects `main` only (frozendict does not exist in 3.14/3.15).

cc @vstinner

_(Surfaced while auditing RustPython with [fusil](https://github.com/devdanzin/fusil) for unguarded C-level recursion and running the CPython differential: RustPython's tuple hash has the identical unguarded recursion — `hash((...,))` SIGSEGVs there too, at a comparable depth. Reduced and reviewed by hand; draft prepared with Claude Code.)_
