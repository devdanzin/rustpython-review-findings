#!/usr/bin/env python3
"""Generate catalog/known_panics.tsv from the per-finding meta.json files.

The canonical source of truth is ``reports/*/meta.json``. This flat snapshot is
the cross-repo contract with **rustpy-review-toolkit**: its ``known-issues``
command reads a ``known_panics.tsv`` of the same shape
(``<bug_id>\\t<signature>`` where the signature is a ``crates/<path>.rs:<line>``
panic-site key) to cross-reference a fresh scan against confirmed crashes. Drop
this file into the toolkit's ``data/`` to fold these review-found bugs into the
toolkit's regression baseline — the same way it already imports the fuzzing
campaign's catalog.

Only ``confirmed`` findings **that crash the interpreter** contribute rows
(``kind`` in {panic, abort, segv}). A ``lead``/``draft`` finding is not yet a
reproduced crash; a ``folded`` retired id is skipped; and a non-crash ``kind``
such as ``leak`` (an uncollectable-cycle finding from the gc-traverse auditor)
is skipped too — its signature is a missing-traverse *site*, not a panic site,
so it must not enter the panic cross-ref (it would read as "absent" against a
fresh panic scan). Such findings belong in a future ``known_traverse_gaps.tsv``
for the gc auditor. A finding may carry several signatures (e.g. mmap ``find`` +
``rfind`` share one root cause across two lines); each becomes a row.

Mirrors ``rustpython-findings/scripts/gen_known_panics.py`` and
``cpython-tsan-findings/scripts/gen_known_races.py``.
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
OUT = ROOT / "catalog" / "known_panics.tsv"

_CONTRIBUTING = {"confirmed", "reported", "fixed"}
_CRASH_KINDS = {"panic", "abort", "segv"}


def main() -> None:
    rows: set[tuple[str, str]] = set()
    ids: set[str] = set()
    skipped: list[tuple[str, str]] = []
    for meta in sorted(REPORTS.glob("*/meta.json")):
        d = json.loads(meta.read_text())
        status = str(d.get("status", "")).split(":", 1)[0]
        rid = d["id"]
        kind = str(d.get("kind", "panic"))
        sigs = [s.strip() for s in d.get("signatures", []) if s.strip()]
        if status not in _CONTRIBUTING:
            skipped.append((rid, status))
            continue
        if kind not in _CRASH_KINDS:
            skipped.append((rid, f"non-crash:{kind}"))
            continue
        ids.add(rid)
        for sig in sigs:
            rows.add((rid, sig))
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w") as fh:
        fh.write("# bug_id\tsignature\n")
        fh.write("# rustpython-review-findings — confirmed panic sites (RPYR-*).\n")
        fh.write("# Same format as rustpython-findings/catalog/known_panics.tsv;\n")
        fh.write("# drop into rustpy-review-toolkit data/ for the known-issues cross-ref.\n")
        for rid, sig in sorted(rows):
            fh.write(f"{rid}\t{sig}\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} signatures for {len(ids)} findings")
    if skipped:
        detail = ", ".join(f"{r}({s})" for r, s in sorted(skipped))
        print(f"  (skipped {len(skipped)} non-confirmed: {detail})")


if __name__ == "__main__":
    main()
