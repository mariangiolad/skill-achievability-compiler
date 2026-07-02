"""Extended corpus: the decidable-fragment boundary and conformance.

The headline 15-spec corpus reproduces the paper's confusion matrix; this
extended set exercises what the paper's sections 5-6 additionally require of
the compiler: tail-recursive loops (Theorem 4), UNKNOWN degradation under
dynamic spawning (Theorem 5), refutation that survives autonomy, and the
conformance premise S_p <= G|p.
"""
import json
from importlib import resources

import pytest

from skillc import check
from skillc.pack import validate_pack


def load_extended():
    data = resources.files("skillc").joinpath(
        "data/corpus_extended.json").read_text(encoding="utf-8")
    return json.loads(data)


CORPUS = load_extended()
EXPECTED_REASONS = {
    "spin_forever": "GOAL_UNSAT",
    "spawn_with_ghost_tool": "MISSING_CAPABILITY",
    "nonconformant_handler": "NON_CONFORMANT",
}


def test_extended_corpus_well_formed():
    assert len(CORPUS) == 6
    for c in CORPUS:
        validate_pack(c["pack"])


@pytest.mark.parametrize("case", CORPUS, ids=lambda c: c["id"])
def test_extended_verdicts_match_ground_truth(case):
    v = check(case["pack"])
    assert v.label == case["ground_truth"], (
        f"{case['id']}: expected {case['ground_truth']}, got {v.label} "
        f"[{v.reason}] {v.detail}")
    expected_reason = EXPECTED_REASONS.get(case["id"])
    if expected_reason:
        assert v.reason == expected_reason


def test_soundness_over_extended_corpus():
    """T1 over the extended set: nothing truly achievable is refuted, and
    nothing outside the fragment is answered definitively."""
    for c in CORPUS:
        v = check(c["pack"])
        if c["ground_truth"] == "ACHIEVABLE":
            assert v.achievable, f"false refutation on {c['id']}"
        if c["ground_truth"] == "UNKNOWN":
            assert v.unknown, f"{c['id']}: claimed {v.label} outside the fragment"
