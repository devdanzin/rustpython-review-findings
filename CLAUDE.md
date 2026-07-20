# CLAUDE.md — rustpython-review-findings operational hub

The single place that says how this repo works, so a fresh session can pick it up.

## What this repo is

A catalog of soundness/crash bugs in **RustPython's own Rust source**, found by static review
with [rustpy-review-toolkit](https://github.com/devdanzin/rustpy-review-toolkit) and reproduced
on the interpreter. One `reports/RPYR-####-<slug>/` dir per bug. It is the static-review
complement to the fuzzing repo `rustpython-findings` (`RUSTPY-*`); the two bug sets are
disjoint. This repo accumulates findings over time; a comprehensive upstream report is
generated from it when a batch is ready.

## Current state (keep this updated)

- **7 reproduced** (RPYR-0001…0007) + **1 lead** (RPYR-0008, `new_invalid_state_error`, needs a
  trigger). All reproduced on `rustpython 0.5.0` (`~/.cargo/bin/rustpython`, built from
  `a9c2c529b`); static review done against the source tree at `3290f287f`.
- None filed upstream yet — all `status: confirmed` / `lead`.
- The toolkit lives at `~/projects/rustpy-review-toolkit` (published
  `devdanzin/rustpy-review-toolkit`); the RustPython source at `~/projects/RustPython`.

## Repo layout

```
reports/RPYR-####-<slug>/   report.md · repro.py · panic.txt · meta.json   (one per bug)
catalog/
    SUMMARY.md              human snapshot (regenerate/update by hand)
    known_panics.tsv        GENERATED — scripts/gen_known_panics.py (the toolkit contract)
    non_bugs.md             the toolkit's false-positive taxonomy (from the meta-evaluations)
INDEX.md                    GENERATED — scripts/gen_index.py (the table)
scripts/                    gen_index.py · gen_known_panics.py
```

Source of truth is `reports/*/meta.json`. `INDEX.md` and `catalog/known_panics.tsv` are
generated — never hand-edit them; edit the meta.json and re-run the scripts.

## meta.json schema

```jsonc
{
  "id": "RPYR-0001",                 // sequential
  "slug": "importerror-...",         // dir suffix
  "title": "...",                    // full title (report H1)
  "short_title": "...",              // compact, for the INDEX table
  "kind": "panic",                   // panic | abort | segv
  "signatures": ["crates/.../x.rs:1872"],  // file:line panic sites (may be several per bug)
  "one_line_repro": "...",
  "repro": "repro.py", "panic_output": "panic.txt",
  "status": "confirmed",             // confirmed | reported:<issue#> | fixed:<commit> | lead | folded
  "reviewed_commit": "3290f287f",    // the source tree the review + line numbers are against
  "confirmed_build": "rustpython 0.5.0 (a9c2c529b, ...)",
  "found_by": ["panic-site-auditor (...)", "git-history-analyzer"],  // the toolkit agent(s) — ENHANCEMENT
  "toolkit_class": "python-reachable-panic",   // the toolkit's finding class
  "cpython_behavior": "returns (ImportError, ())",   // the divergence — ENHANCEMENT
  "guarded_twin": "OSError.__reduce__ guards with args.len() >= 2",  // the fix pattern next door — ENHANCEMENT
  "affected": ["ImportError", "ModuleNotFoundError"],
  "prior_art": "unreported",
  "notes": "..."
}
```

The three ENHANCEMENT fields over the fuzzing repo's schema are what make this a *toolkit*
findings repo: `found_by` (which agent/calibration surfaced it — the toolkit-quality signal),
`cpython_behavior` (the divergence, ready for the upstream report), and `guarded_twin` (the
fix pattern that, in this codebase, is almost always already present in the same file).

## Mint / confirm a finding (lifecycle)

1. Toolkit run surfaces a candidate (see the toolkit's `explore`/`hotspots`, or a per-file
   agent deep-dive). The agent triages and, for a real bug, gives a trigger.
2. **Reproduce** on `~/.cargo/bin/rustpython` (a plain `.py` file; avoid stdin `-` for indented
   code — RustPython's line mode mis-parses it). Capture stderr to `panic.txt`.
3. Create `reports/RPYR-####-<slug>/` with `repro.py`, `panic.txt`, `meta.json`, `report.md`.
   Assign the next free id. Group faces of one root cause under a single id with multiple
   `signatures` (e.g. RPYR-0004 = find + rfind).
4. Fill `found_by`, `guarded_twin`, `cpython_behavior` — verify the CPython behaviour against
   `python3` before writing it.
5. `python3 scripts/gen_known_panics.py && python3 scripts/gen_index.py`, commit.
6. A `lead` (reasoned, not reproduced) is fine to record — set `status: lead`; it is excluded
   from `known_panics.tsv` until reproduced. If a candidate turns out sound, record it in
   `catalog/non_bugs.md` instead.

## Line drift

RustPython's object model churns; `file:line` signatures drift between checkouts (the
`a9c2c529b` binary and the `3290f287f` source tree differ by ~90 lines in `exceptions.rs`).
Record both the `reviewed_commit` and `confirmed_build`; the toolkit's `known-issues` command
is drift-tolerant (present / line-drifted / absent) and consumes this repo's `known_panics.tsv`.

## The toolkit feedback loop

`catalog/known_panics.tsv` is the cross-repo contract: same `<bug_id>\t<signature>` format the
toolkit's `known-issues` command reads. `cp catalog/known_panics.tsv` into
`rustpy-review-toolkit/plugins/rustpy-review-toolkit/data/` (or merge with the fuzzing catalog
already there) to fold these bugs into the toolkit's regression baseline. `non_bugs.md` records
the false-positive classes the meta-evaluations found — feed those back as toolkit calibrations
(several already are: the invariant-downcast, owner-downcast, and guarded-arity down-ranks).

## Commits

Conventional, one logical change per commit. Regenerate `INDEX.md` + `known_panics.tsv` in the
same commit as the meta.json change that drives them. End commit messages with the standard
Co-Authored-By / Claude-Session trailers.
