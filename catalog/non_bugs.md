# The toolkit's false-positive taxonomy (from the meta-evaluations)

Running the full [rustpy-review-toolkit](https://github.com/devdanzin/rustpy-review-toolkit)
agent panel on each hot file, then grading the scanner's FIX list against agent triage +
binary reproduction, mapped the recurring **false-positive classes** on RustPython. Recording
them here serves two purposes: it stops a future reviewer re-investigating the same dismissed
shapes, and it is the direct feedback that drives the toolkit's scanner calibrations. Several
of these are now scanner down-ranks (noted inline).

Precision trajectory of the panic-site scanner's FIX list, as each class was calibrated out:
`exceptions.rs` **0/14** real → `_asyncio.rs` **2/9** (both real after calibration) →
`mmap.rs` **2/5** → `tuple.rs` **0/1**. The raw FIX count is a triage queue, not a bug count.

## Panic-site false-positive classes

### 1. Guarded arity index — `args[N]` inside a length guard
`exceptions.rs` had 14 scanner-FIX `args.args[N]` indices, **all** guarded by a `match args.len()`
arm or an `if (2..=5).contains(&len)` block the intra-procedural scanner couldn't see. Zero were
real. → **Calibrated**: down-rank a fallible-value panic inside a length/arity guard
(`_LENGTH_GUARD_RE`, 16-line lookback). An *unguarded* arity index (the `_typing._idfunc` shape,
`RUSTPY-0005` in the fuzzing repo) stays FIX.

### 2. Invariant-protected downcast — private field / same-variable gate
`_asyncio.rs` had 7 scanner-FIX `X.downcast().unwrap()` that cannot fail: the subject was read
from a private `PyRwLock` payload field (`self.fut_exception.read()` — the type is an internal
invariant), or the **same variable** was `fast_isinstance`-gated just above. → **Calibrated**:
`downcast_guarded` down-rank. A downcast of a *distinct* Python-controllable value stays FIX —
which correctly kept RPYR-0002 (a module attribute) and RPYR-0003 (a `.call()` result whose gate
was on a *different* variable) as real FIXes.

### 3. Owner-type downcast — a protocol slot downcasting to its own type
`tuple.rs` `as_number` L488 (`number.obj.downcast::<PyTuple>().unwrap()` inside
`impl AsNumber for PyTuple`) is guaranteed by the slot-wrapper's `fast_isinstance(owner)` check —
a builtin's subclasses share its Rust payload. → **Calibrated**: down-rank when the downcast
target type equals the enclosing `impl`'s Self type. The genuine mismatch bugs (RUSTPY-0009/0011
staticmethod/classmethod `repr`, in the fuzzing repo) are where the downcast target *differs*
from the slot owner or subclasses do not share the payload.

### 4. Dead abort-macro stub — a shadowed default method
`init`/`py_new` bodies that are a single `unreachable!("slot_init is defined")` /
`unimplemented!("use slot_new")` are shadowed by a sibling `slot_*` form and never called
(10+ in `exceptions.rs`). → **Calibrated**: a pure `unreachable!`/`unimplemented!` body →
ACCEPTABLE. (`todo!` is excluded — genuinely unimplemented work stays CONSIDER.)

## Unsafe-soundness: correctly-dismissed real findings

### 5. `repr(transparent)` handle transmute
`tuple.rs`'s 3 `PyTuple`↔`PyTupleTyped` transmutes (`new_ref_typed`, `into_untyped`, `as_untyped`)
are sound: both handle types are `#[repr(transparent)]` single pointers, and the conversions are
*widening*/by-construction (no runtime check needed). The disciplined narrowing site
`try_into_typed` runs `TransmuteFromObject::check` per element and the scanner correctly does not
flag it. The scanner emits these as CONSIDER/LOW (it can't see cross-module type defs); the agent
resolves them ACCEPTABLE by tracing the transparency. A prose `// SAFETY:` sub-signal was added to
point that trace faster. **This is the correct two-stage behaviour, not a defect** — do not
down-rank documented-transparent transmutes at the scanner level (that would mean trusting an
unverified prose comment).

## GC-traverse: correctly-quiet surfaces

### 6. `#[pyexception]` transparent-newtype subtypes are not payloads
~55 exception subtypes are `#[repr(transparent)] struct PyKeyError(PyLookupError)` — they reuse
the base's `PyBaseException` payload and correctly declare no `traverse`. → **Calibrated**: the
mapper/gc auditor now recognizes `#[pyexception]` and treats tuple-struct newtypes (empty
named-field list) as non-payloads, so they produce no `missing_traverse` false positive — while a
*future* custom exception payload that adds a ref field and forgets its manual `Traverse` is now
caught.

### 7. Leaf payloads own no Python refs
`PyMmap` owns an mmap/fd/handle (OS resources, not Python refs) → a graph leaf, correctly no
`traverse`. Owning a raw resource is not owning a `PyObjectRef`.

## Cross-cutting observations

- **Complexity does not localize panics.** Across 4 files, the complexity hotspots and the panic
  sites were disjoint (4/4 orthogonal) — sometimes anti-correlated (the panic sites are the
  *simple* one-line accessors that skip bounds checks). Do not triage panic risk with a
  complexity scanner.
- **The pattern-set gap.** The scanner matches `.unwrap()`/`.expect()`/`panic!`/`.args[` — not
  generic slice indexing or arithmetic underflow. RPYR-0005/0006/0007 are exactly that class and
  were found by the history agent's similar-bug detection, not the scanner. This is a deliberate
  precision/recall tradeoff (a generic `[i]` pattern would flood); the history agent covers it.
