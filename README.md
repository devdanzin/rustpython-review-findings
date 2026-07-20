# rustpython-review-findings

A catalog of **soundness and crash bugs in the [RustPython](https://github.com/RustPython/RustPython)
interpreter's own Rust source**, found by *static review* with
[**rustpy-review-toolkit**](https://github.com/devdanzin/rustpy-review-toolkit) and then
reproduced on the interpreter. One directory per bug, each with a minimal Python reproducer,
the captured Rust panic/abort output, a root-cause analysis, and a suggested fix.

The idea: RustPython is a Python interpreter written in Rust, so a `.unwrap()` on a `None`, an
out-of-bounds slice, or an unclamped integer arithmetic on Python input doesn't corrupt memory
— it **aborts the interpreter**. Any Python program that reaches that line crashes the whole
VM (a denial of service). The toolkit finds these statically; this repo turns each into a
deduped, reproduced, root-caused report that accumulates over time toward an upstream report.

## The findings

- **7 reproduced bugs** (`RPYR-0001` … `RPYR-0007`) + **1 lead** (`RPYR-0008`), each with a
  deterministic, standard-library-only reproducer and the exact panic output.
- **[INDEX.md](INDEX.md)** is the table — one row per bug, with the **toolkit agent that found
  it** and its status.
- Every bug is a **latent DoS in never-bug-fixed code, and every one has a correctly-guarded
  twin in the same file** — the fix pattern already exists next door. That recurring shape is
  the single strongest signal a static reviewer has here.

These are **disjoint from** the fuzzing catalog in
[`rustpython-findings`](https://github.com/devdanzin/rustpython-findings) (`RUSTPY-*`, found
with the `fusil` fuzzer + a CPython differential oracle) — none of the bugs here appear there.
Static review and fuzzing cover different surfaces; this repo is the static-review complement.

## What's in each report

```
reports/RPYR-####-<slug>/
    report.md    the analysis: reproducer, panic output, root cause, CPython divergence, fix, the guarded twin
    repro.py     a minimal, deterministic, standard-library-only Python reproducer
    panic.txt    the captured Rust panic / abort output
    meta.json    structured metadata (sites, status, found-by agent, guarded twin, CPython behaviour)
```

## Reproducing a bug

The reproducers are plain Python and run on a stock RustPython build:

```bash
rustpython reports/RPYR-0001-importerror-reduce-empty-args-unwrap/repro.py
```

A confirmed finding aborts the interpreter (`thread 'main' panicked …`, exit 101, or SIGABRT
for the allocator cases). The reviewed source tree and the reproduced binary are recorded in
each `meta.json`; because RustPython's object model is under active upstream churn, `file:line`
signatures drift between checkouts (the reports note it where it happens).

## How they were found

Static review with [rustpy-review-toolkit](https://github.com/devdanzin/rustpy-review-toolkit)
— tree-sitter-rust scanners that find candidates, and per-aspect agents that triage each by
reading the real code, ranking Python-reachability, and reproducing on the binary. The
**Found by** column in [INDEX.md](INDEX.md) records which agent surfaced each bug; notably, the
**history agent's similar-bug detection** caught three (`move`, `deque`, `mul`) that the
pattern scanner structurally cannot see (they are arithmetic/allocation panics with no
`.unwrap()` token). The toolkit workflow, the false-positive taxonomy, and the feedback loop
are documented in [`CLAUDE.md`](CLAUDE.md) and [`catalog/non_bugs.md`](catalog/non_bugs.md).

## The feedback loop

`scripts/gen_known_panics.py` emits `catalog/known_panics.tsv` in the exact format
rustpy-review-toolkit's `known-issues` command consumes — drop it into the toolkit's `data/`
and these review-found bugs become part of its regression baseline, the same way it already
imports the fuzzing catalog. Toolkit finds bugs → this repo → regression data → toolkit.

## Credit & a note on AI assistance

The static review, the reduced reproducers, and the root-cause write-ups were produced with
[**Claude Code**](https://claude.com/claude-code) working alongside the maintainer, who reviews
and re-reproduces every finding before it is disclosed. Any upstream report will carry an
explicit disclaimer.

## More

- [`INDEX.md`](INDEX.md) — the table · [`catalog/SUMMARY.md`](catalog/SUMMARY.md) — snapshot
- [`catalog/non_bugs.md`](catalog/non_bugs.md) — the toolkit's false-positive taxonomy (from the meta-evaluations)
- [`CLAUDE.md`](CLAUDE.md) — operational hub (lifecycle, meta.json schema, the toolkit loop)
