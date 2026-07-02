"""Semantic validation: mutation testing on packs, and (opt-in, live) the
full loop on a real skill -- LLM compaction, then seeded-fault detection.

The mutation machinery itself is deterministic and always tested; only the
LLM compaction of the real skill is env-gated.
"""
import os
from pathlib import Path

import pytest

from skillc import check
from skillc.evaluate import load_corpus
from skillc.mutate import (drop_invoked_capability, is_conjunctive,
                           strip_goal_establisher)

SKILLS_DIR = Path(os.environ.get("SKILLC_SKILLS_DIR", "/mnt/skills"))


def corpus_packs():
    return [(c["id"], c["pack"]) for c in load_corpus()]


def test_drop_capability_mutants_are_always_caught():
    hit = 0
    for cid, pack in corpus_packs():
        m = drop_invoked_capability(pack)
        if not m:
            continue
        mutant, victim = m
        v = check(mutant)
        assert not v.achievable, f"{cid}: dropped {victim}, still achievable"
        assert v.reason == "MISSING_CAPABILITY" and victim in v.frontier, cid
        hit += 1
    assert hit >= 10


def test_strip_establisher_mutants_are_caught_on_conjunctive_goals():
    hit = 0
    for cid, pack in corpus_packs():
        if not is_conjunctive(pack["goal"]) or not check(pack).achievable:
            continue
        m = strip_goal_establisher(pack)
        if not m:
            continue
        mutant, atom = m
        v = check(mutant)
        assert not v.achievable, f"{cid}: stripped {atom}, still achievable"
        assert v.reason == "GOAL_UNSAT" and atom in v.frontier, cid
        hit += 1
    assert hit >= 4


def test_mutants_of_fixture_pack():
    from skillc.frontend.markdown import compile_file
    from skillc.profiles import load_profile
    res = compile_file(Path(__file__).parent / "fixtures/embedded-pack/SKILL.md",
                       load_profile("none"))
    m = strip_goal_establisher(res.pack)
    assert m is not None
    v = check(m[0])
    assert not v.achievable and v.reason == "GOAL_UNSAT"


@pytest.mark.skipif(
    not (os.environ.get("SKILLC_LIVE_LLM") and os.environ.get("ANTHROPIC_API_KEY")
         and (SKILLS_DIR / "examples/call-to-book/SKILL.md").exists()),
    reason="live semantic validation is opt-in (SKILLC_LIVE_LLM=1 + API key + corpus)")
def test_live_semantic_loop_on_a_real_skill():
    """The full paper pipeline on a real deployed skill: prose -> untrusted
    LLM compaction -> schema gate -> trusted checker, then two seeded
    semantic faults that must be refuted with the wound named."""
    from skillc.frontend.llm import CONSUMER_ABILITIES, compact_with_repair
    text = (SKILLS_DIR / "examples/call-to-book/SKILL.md").read_text()
    pack, _ = compact_with_repair(text, runtime_abilities=CONSUMER_ABILITIES)
    assert check(pack).achievable          # deployed skill: no false alarm

    mutant, victim = drop_invoked_capability(pack)
    v = check(mutant)
    assert not v.achievable and v.reason == "MISSING_CAPABILITY"
    assert victim in v.frontier

    if is_conjunctive(pack["goal"]):
        m = strip_goal_establisher(pack)
        if m:
            mutant, atom = m
            v = check(mutant)
            assert not v.achievable and v.reason == "GOAL_UNSAT"
            assert atom in v.frontier
