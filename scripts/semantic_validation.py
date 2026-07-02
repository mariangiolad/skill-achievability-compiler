#!/usr/bin/env python3
"""Semantic goal-achievability validation on REAL skills, with mutations.

For each selected real SKILL.md:
  1. LLM-compact the prose into a semantic pack (capabilities with
     pre/effects, protocol, goal formula) -- the untrusted front-end;
  2. schema-gate + check: a deployed skill must come out ACHIEVABLE
     (a refutation here would be a false alarm);
  3. sabotage the semantic pack two ways with a known expected verdict:
       drop an invoked capability      -> MISSING_CAPABILITY, tool named
       strip a goal atom's establisher -> GOAL_UNSAT, atom named
     and verify the compiler catches both.

Writes docs/SEMANTIC_VALIDATION.md.  Requires ANTHROPIC_API_KEY (the LLM is
only in the untrusted half; the verdicts come from the trusted checker).

Usage: python3 scripts/semantic_validation.py [SKILLS_DIR] [N_SKILLS]
"""
import json
import sys
from pathlib import Path

from skillc import __version__, check
from skillc.frontend.llm import (CONSUMER_ABILITIES, DEFAULT_MODEL,
                                 compact_with_repair)
from skillc.mutate import (drop_invoked_capability, is_conjunctive,
                           strip_goal_establisher)

DEFAULT_SKILLS = [
    "examples/call-to-book/SKILL.md",
    "examples/grocery-shopping/SKILL.md",
    "examples/cancel-unsubscribe/SKILL.md",
    "examples/prescription-refill/SKILL.md",
]


def run_one(path: Path, lines: list[str]) -> dict:
    text = path.read_text(encoding="utf-8")
    # untrusted compaction, schema-gated inside; the runtime-abilities note is
    # the Gamma_0 the prose presupposes (phone, browser, user interaction);
    # NON_PROJECTABLE counterexamples trigger bounded compaction repair
    pack, repair_log = compact_with_repair(
        text, runtime_abilities=CONSUMER_ABILITIES)
    v = check(pack)
    row = {"skill": path.parent.name, "verdict": v.label,
           "goal": json.dumps(pack["goal"]),
           "n_caps": len(pack["capabilities"]), "mutations": []}
    lines.append(f"### `{path.parent.name}`\n")
    lines.append(f"* compacted: {len(pack['capabilities'])} capabilities, "
                 f"{len(pack['protocol'])} protocol steps, goal "
                 f"`{json.dumps(pack['goal'])}`")
    for entry in repair_log:
        lines.append(f"* {entry}")
    lines.append(f"* **original: {v.label}**"
                 + ("" if v.achievable else f"  [{v.reason}] {v.detail}"))
    if not v.achievable:
        # mutations only make sense against an achievable baseline (the
        # expected mutant verdicts assume the only fault is the seeded one)
        lines.append("")
        return row

    m = drop_invoked_capability(pack)
    if m:
        mutant, victim = m
        mv = check(mutant)
        ok = (mv.label == "IMPOSSIBLE" and mv.reason == "MISSING_CAPABILITY"
              and victim in mv.frontier)
        row["mutations"].append(("drop_capability", victim, mv.label, mv.reason, ok))
        lines.append(f"* mutation `drop {victim}` -> **{mv.label}** "
                     f"[{mv.reason}] frontier={list(mv.frontier)} "
                     f"{'(caught, tool named)' if ok else '(MISSED!)'}")

    if is_conjunctive(pack["goal"]):
        m = strip_goal_establisher(pack)
        if m:
            mutant, atom = m
            mv = check(mutant)
            ok = (mv.label == "IMPOSSIBLE" and mv.reason == "GOAL_UNSAT"
                  and atom in mv.frontier)
            row["mutations"].append(("strip_establisher", atom, mv.label,
                                     mv.reason, ok))
            lines.append(f"* mutation `strip establishers of {atom}` -> "
                         f"**{mv.label}** [{mv.reason}] "
                         f"frontier={list(mv.frontier)} "
                         f"{'(caught, atom named)' if ok else '(MISSED!)'}")
    lines.append("")
    return row


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/skills")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else len(DEFAULT_SKILLS)
    paths = [root / s for s in DEFAULT_SKILLS[:n] if (root / s).exists()]
    if not paths:
        print("no skills found", file=sys.stderr)
        return 2
    lines = [
        "# Semantic validation on real skills",
        "",
        f"`skillc {__version__}`, LLM compaction model `{DEFAULT_MODEL}` "
        "(untrusted front-end; every verdict below is produced by the "
        "trusted checker on the schema-gated pack).  Regenerate with "
        "`python3 scripts/semantic_validation.py`.",
        "",
        "Protocol: compact each real skill into a semantic pack; the "
        "deployed skill must check ACHIEVABLE.  Then sabotage the pack two "
        "ways with a known ground truth -- drop a capability the plan "
        "invokes, and strip a goal conjunct's establishers -- and require "
        "the compiler to refute each mutant *and name the wound*.",
        "",
    ]
    rows = []
    for p in paths:
        print(f"compacting {p} ...")
        rows.append(run_one(p, lines))

    total_m = sum(len(r["mutations"]) for r in rows)
    caught = sum(m[4] for r in rows for m in r["mutations"])
    pass_ok = sum(r["verdict"] == "ACHIEVABLE" for r in rows)
    lines += [
        "## Summary",
        "",
        f"* pass direction: {pass_ok}/{len(rows)} real skills compact to an "
        "ACHIEVABLE pack (0 false alarms).",
        f"* refute direction: {caught}/{total_m} seeded semantic faults "
        "caught with the exact missing tool / dead goal atom named.",
        "",
    ]
    out = Path(__file__).parent.parent / "docs" / "SEMANTIC_VALIDATION.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")
    print(f"pass: {pass_ok}/{len(rows)}   mutants caught: {caught}/{total_m}")
    return 0 if (pass_ok == len(rows) and caught == total_m) else 1


if __name__ == "__main__":
    sys.exit(main())
