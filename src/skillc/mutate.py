"""Mutation testing for achievability packs.

The empirical test of "does the compiler really validate goal achievability"
has two directions:

  * the PASS direction -- a real, deployed skill compacts to a pack whose
    goal is achievable (anything else is a false alarm, T1's empirical face);
  * the REFUTE direction -- if we sabotage the pack in a way that provably
    dooms the goal, the compiler must notice, and must name the wound.

These mutators produce semantically doomed variants with a known expected
verdict, so the refute direction can be tested mechanically on packs produced
from real skills (deterministic or LLM compaction alike).
"""
from __future__ import annotations

import copy
from typing import Any, Optional

from .formula import atoms


def _acts(steps: list[dict]) -> list[str]:
    out = []
    for s in steps:
        if "act" in s:
            out.append(s["act"]["cap"])
        if "choice" in s:
            for br in s["choice"]["branches"].values():
                out.extend(_acts(br))
        if "rec" in s:
            out.extend(_acts(s["rec"]["body"]))
    return out


def drop_invoked_capability(pack: dict) -> Optional[tuple[dict, str]]:
    """Remove a capability the protocol actually invokes.

    Expected verdict on the mutant: IMPOSSIBLE / MISSING_CAPABILITY with the
    dropped tool in the frontier (hallucinated planning, manufactured)."""
    invoked = [c for c in _acts(pack["protocol"]) if c in pack["capabilities"]]
    if not invoked:
        return None
    victim = sorted(invoked)[0]
    mutant = copy.deepcopy(pack)
    del mutant["capabilities"][victim]
    mutant["name"] = pack.get("name", "pack") + f"__drop_{victim}"
    return mutant, victim


def strip_goal_establisher(pack: dict) -> Optional[tuple[dict, str]]:
    """Strip a goal atom from the add-list of every capability establishing
    it (the tools stop delivering that effect).

    Expected verdict on the mutant: IMPOSSIBLE / GOAL_UNSAT via the
    protocol-independent establisher-closure certificate -- provided the atom
    is conjunctively required; the caller should skip disjunctive goals."""
    init = set(pack.get("init_true", []))
    for atom in sorted(atoms(pack["goal"])):
        if atom in init:
            continue
        establishers = [n for n, c in pack["capabilities"].items()
                        if atom in c.get("add", [])]
        if not establishers:
            continue
        mutant = copy.deepcopy(pack)
        for n in establishers:
            mutant["capabilities"][n]["add"] = [
                a for a in mutant["capabilities"][n]["add"] if a != atom]
        mutant["name"] = pack.get("name", "pack") + f"__strip_{atom}"
        return mutant, atom
    return None


def is_conjunctive(goal: Any) -> bool:
    """True when the goal is an and/atom tree (no or), so stripping any goal
    atom's establishers must doom it."""
    if isinstance(goal, str) or goal in (True, False):
        return True
    if isinstance(goal, dict):
        if "and" in goal:
            return all(is_conjunctive(x) for x in goal["and"])
        if "cmp" in goal:
            return True
    return False
