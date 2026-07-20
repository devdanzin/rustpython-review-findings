#!/usr/bin/env python3
"""Generate INDEX.md from the per-finding meta.json files.

Source of truth is ``reports/*/meta.json``. Run after any finding changes. One
row per finding: Report | Title | Site | Found by (which toolkit agent) |
Status, grouped by crash kind. Mirrors ``cpython-oom-findings/scripts/gen_index.py``.
"""

import datetime
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

KIND_ORDER = ["panic", "abort", "segv", "leak"]
KIND_TITLE = {
    "panic": "Python-reachable panics",
    "abort": "Aborts (SIGABRT)",
    "segv": "Segfaults",
    "leak": "Uncollectable-cycle leaks (missing GC traverse)",
}
# A finding stamped GENERATED_AT must be passed in via args to keep runs
# deterministic; the module avoids Date.now-style nondeterminism only for the
# workflow harness, so here (a plain script) today() is fine.


def _short_site(sig: str) -> str:
    """`crates/vm/src/builtins/exceptions.rs:1872` -> `exceptions.rs:1872`."""
    head, _, line = sig.rpartition(":")
    return f"{head.rsplit('/', 1)[-1]}:{line}" if line else sig


def status_cell(d: dict) -> str:
    s = str(d.get("status", "draft"))
    kind, _, rest = s.partition(":")
    if kind == "reported" and rest:
        return f"[#{rest}](https://github.com/RustPython/RustPython/issues/{rest})"
    if kind == "fixed":
        return f"**FIXED** {rest}".strip()
    if kind == "confirmed":
        return "confirmed (reproduced)"
    if kind == "lead":
        return "lead (not yet reproduced)"
    if kind == "folded":
        return f"🔁 dup of {d.get('folded_into', '?')}"
    return s


def main() -> None:
    metas = sorted(
        (json.loads(p.read_text()) for p in REPORTS.glob("*/meta.json")),
        key=lambda d: d["id"],
    )
    confirmed = [m for m in metas if str(m.get("status", "")).startswith(("confirmed", "reported", "fixed"))]
    leads = [m for m in metas if str(m.get("status", "")).startswith(("lead", "draft"))]

    out: list[str] = []
    out.append("# RustPython review findings — index\n")
    out.append(
        "Soundness and crash bugs in the **RustPython interpreter's own Rust "
        "source**, found by static review with "
        "[**rustpy-review-toolkit**](https://github.com/devdanzin/rustpy-review-toolkit) "
        "and then reproduced on the interpreter. Each row links to a "
        "self-contained report (root cause, minimal Python reproducer, the Rust "
        "panic output, and a suggested fix).\n"
    )
    out.append(
        f"_{len(confirmed)} reproduced bug(s)"
        + (f" + {len(leads)} lead(s)" if leads else "")
        + f". Generated {datetime.date.today().isoformat()}._\n"
    )
    out.append(
        "These are **disjoint from** and complementary to the fuzzing catalog in "
        "[`rustpython-findings`](https://github.com/devdanzin/rustpython-findings) "
        "(`RUSTPY-*`) — none of the bugs below appear there. The **Found by** "
        "column records which toolkit agent surfaced each one.\n"
    )
    out.append(
        "Status: `confirmed` (reproduced on the binary) · `#N` (RustPython issue "
        "open) · **FIXED** `commit` · `lead` (traced, not yet reproduced).\n"
    )

    by_kind: dict[str, list[dict]] = {}
    for m in metas:
        by_kind.setdefault(m.get("kind", "panic"), []).append(m)

    for kind in KIND_ORDER:
        rows = by_kind.get(kind)
        if not rows:
            continue
        out.append(f"\n## {KIND_TITLE.get(kind, kind)}\n")
        out.append("| Report | Title | Site | Found by | Status |")
        out.append("|---|---|---|---|---|")
        for d in rows:
            rid = d["id"]
            link = f"[{rid}](reports/{rid}-{d['slug']}/report.md)"
            title = d.get("short_title", d.get("title", "")).replace("|", "\\|")
            sites = " ".join(_short_site(s) for s in d.get("signatures", [])) or "—"
            found = ", ".join(d.get("found_by", [])) or "—"
            # keep the agent name only (drop the parenthetical) for a tidy column
            found = ", ".join(f.split(" (")[0] for f in d.get("found_by", [])) or "—"
            out.append(
                f"| {link} | {title} | `{sites}` | {found} | {status_cell(d)} |"
            )

    out.append("")
    (ROOT / "INDEX.md").write_text("\n".join(out))
    print(f"wrote INDEX.md: {len(confirmed)} confirmed, {len(leads)} lead(s)")


if __name__ == "__main__":
    main()
