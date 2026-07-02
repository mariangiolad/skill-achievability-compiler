import pytest

from skillc.evaluate import load_corpus
from skillc.pack import Pack, PackError, validate_pack

MINIMAL = {
    "name": "m",
    "capabilities": {"a": {"add": ["done"]}},
    "protocol": [{"act": {"cap": "a", "by": "agent"}}],
    "goal": "done",
}


def test_minimal_pack_passes_gate():
    validate_pack(MINIMAL)
    p = Pack.load(MINIMAL)
    assert p.capabilities["a"].add == ["done"]


@pytest.mark.parametrize("mutate,exc_fragment", [
    (lambda d: d.pop("goal"), "missing top-level key"),
    (lambda d: d.pop("capabilities"), "missing top-level key"),
    (lambda d: d.update(protocol=[{"act": {"cap": "a"}}]), "act needs cap+by"),
    (lambda d: d.update(protocol=[{"jump": {}}]), "unknown step kind"),
    (lambda d: d.update(protocol=[{"msg": {"from": "a", "to": "b"}}]), "msg needs"),
    (lambda d: d.update(goal={"cmp": ["x", "~", 1]}), "bad cmp"),
    (lambda d: d.update(capabilities={"a": {"pre": {"nand": []}}}), "bad formula"),
    (lambda d: d.update(protocol=[{"choice": {"by": "r", "branches": {}}}]),
     "at least one branch"),
    (lambda d: d.update(init_true="oops"), "init_true"),
])
def test_gate_rejects(mutate, exc_fragment):
    d = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
         for k, v in MINIMAL.items()}
    mutate(d)
    import re
    with pytest.raises(PackError, match=re.escape(exc_fragment)):
        validate_pack(d)


def test_undeclared_cap_passes_gate():
    # The gate deliberately lets undeclared caps through: the CHECKER reports
    # them as MISSING_CAPABILITY (that is the hallucinated-planning signal).
    d = dict(MINIMAL, protocol=[{"act": {"cap": "ghost_tool", "by": "agent"}}])
    validate_pack(d)


def test_all_reference_compactions_are_well_formed():
    corpus = load_corpus()
    assert len(corpus) == 15
    for c in corpus:
        validate_pack(c["pack"])
