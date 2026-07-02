"""Tail-recursive loops (Theorem 4) and the autonomy boundary (Theorem 5):
mu-recursion with widening, and UNKNOWN degradation on dynamic spawning."""
import pytest

from skillc import check
from skillc.pack import PackError, validate_pack


def pack(**kw):
    base = {"name": "t", "roles": ["agent"], "capabilities": {},
            "protocol": [], "goal": True}
    base.update(kw)
    return base


def act(cap, by="agent"):
    return {"act": {"cap": cap, "by": by}}


# ------------------------------------------------------------ tail recursion

def test_retry_loop_with_exit_achievable():
    """The retry-until-found pattern: loop is tolerated, exit reaches goal."""
    v = check(pack(
        capabilities={"search": {"add": ["found"]},
                      "deliver": {"pre": "found", "add": ["answered"]}},
        protocol=[{"rec": {"name": "X", "body": [
            act("search"),
            {"choice": {"by": "agent", "branches": {
                "retry": [{"continue": "X"}],
                "done": []}}}]}},
            act("deliver")],
        goal="answered"))
    assert v.achievable
    assert ("act", "deliver") in v.witness


def test_loop_that_never_establishes_goal_is_refuted():
    """A loop with no exit and no establisher terminates the search via
    predicate-state saturation and refutes."""
    v = check(pack(
        capabilities={"spin": {"add": ["spun"]}},
        protocol=[{"rec": {"name": "X", "body": [
            act("spin"), {"continue": "X"}]}}],
        goal="published"))
    assert not v.achievable
    assert v.reason == "GOAL_UNSAT"


def test_goal_marker_inside_loop_body():
    v = check(pack(
        capabilities={"work": {"add": ["done"]}},
        protocol=[{"rec": {"name": "X", "body": [
            act("work"), {"goal": "done"}, {"continue": "X"}]}}],
        goal="done"))
    assert v.achievable


def test_widening_havocs_numerics_soundly():
    """A counter incremented in a loop: after widening the checker must NOT
    refute a goal that some iteration count satisfies (soundness under
    over-approximation)."""
    v = check(pack(
        capabilities={"inc": {"assigns": {"x": {"+": ["x", 1]}}, "add": ["stepped"]}},
        protocol=[{"rec": {"name": "X", "body": [
            act("inc"),
            {"choice": {"by": "agent", "branches": {
                "more": [{"continue": "X"}],
                "stop": []}}}]}}],
        goal={"and": ["stepped", {"cmp": ["x", ">=", 3]}]},
        init_constraints=[{"cmp": ["x", "==", 0]}]))
    assert v.achievable          # reachable concretely after 3 iterations


def test_blocked_guard_inside_loop():
    v = check(pack(
        capabilities={"publish": {"pre": "approved", "add": ["published"]}},
        protocol=[{"rec": {"name": "X", "body": [act("publish"),
                                                 {"continue": "X"}]}}],
        goal="published"))
    assert not v.achievable
    assert v.reason == "BLOCKED_GUARD"


def test_gate_rejects_non_tail_continue():
    with pytest.raises(PackError, match="tail position"):
        validate_pack(pack(
            capabilities={"a": {"add": ["p"]}},
            protocol=[{"rec": {"name": "X", "body": [
                {"continue": "X"}, act("a")]}}],
            goal="p"))


def test_gate_rejects_unscoped_continue():
    with pytest.raises(PackError, match="no enclosing rec"):
        validate_pack(pack(protocol=[{"continue": "X"}], goal=True))


def test_gate_rejects_duplicate_rec_names():
    with pytest.raises(PackError, match="duplicate rec name"):
        validate_pack(pack(protocol=[
            {"rec": {"name": "X", "body": []}},
            {"rec": {"name": "X", "body": []}}], goal=True))


# ---------------------------------------------------------- autonomy boundary

def test_spawn_degrades_to_unknown():
    v = check(pack(
        roles=["planner"],
        capabilities={"delegate": {"add": ["delegated"]}},
        protocol=[{"spawn": {"role": "helper"}},
                  act("delegate", "planner")],
        goal="delegated"))
    assert v.label == "UNKNOWN"
    assert v.unknown and not v.achievable
    assert v.reason == "DYNAMIC_TOPOLOGY"


def test_missing_capability_refutation_survives_autonomy():
    """Capability soundness is decided before the fragment boundary: a tool
    absent from Gamma stays absent no matter what is spawned."""
    v = check(pack(
        protocol=[{"spawn": {"role": "helper"}},
                  act("ghost_tool")],
        goal=True))
    assert v.label == "IMPOSSIBLE"
    assert v.reason == "MISSING_CAPABILITY"
    assert v.frontier == ("ghost_tool",)


def test_spawn_inside_branch_also_unknown():
    v = check(pack(
        capabilities={"a": {"add": ["p"]}},
        protocol=[{"choice": {"by": "agent", "branches": {
            "solo": [act("a")],
            "fanout": [{"spawn": {"role": "w"}}]}}}],
        goal="p"))
    assert v.label == "UNKNOWN"


# ------------------------------------------------------------- conformance

def informed(chooser="router", worker="handler"):
    return [{"choice": {"by": chooser, "branches": {
        "a": [{"msg": {"from": chooser, "to": worker, "label": "go_a"}},
              act("fix_a", worker)],
        "b": [{"msg": {"from": chooser, "to": worker, "label": "go_b"}},
              act("fix_b", worker)]}}}]


def conformance_pack(handler_skill):
    return pack(
        roles=["router", "handler"],
        capabilities={"fix_a": {"add": ["resolved"]},
                      "fix_b": {"add": ["resolved"]}},
        protocol=informed(),
        goal="resolved",
        skills={"handler": handler_skill})


def test_conformant_skill_passes():
    v = check(conformance_pack([
        {"branch": {"from": "router", "branches": {
            "go_a": [{"act": {"cap": "fix_a"}}],
            "go_b": [{"act": {"cap": "fix_b"}}]}}}]))
    assert v.achievable


def test_extra_external_choice_is_conformant():
    """Sub-Ext: offering MORE receives than the contract is safe."""
    v = check(conformance_pack([
        {"branch": {"from": "router", "branches": {
            "go_a": [{"act": {"cap": "fix_a"}}],
            "go_b": [{"act": {"cap": "fix_b"}}],
            "go_c": [{"act": {"cap": "fix_a"}}]}}}]))
    assert v.achievable


def test_missing_external_choice_is_non_conformant():
    """A handler that only handles go_a deadlocks when go_b is chosen."""
    v = check(conformance_pack([
        {"branch": {"from": "router", "branches": {
            "go_a": [{"act": {"cap": "fix_a"}}]}}}]))
    assert not v.achievable
    assert v.reason == "NON_CONFORMANT"
    assert "handler" in v.detail


def test_selector_dropping_a_branch_is_conformant():
    """Sub-Int: making FEWER internal choices than the contract is safe."""
    v = check(pack(
        roles=["router", "handler"],
        capabilities={"fix_a": {"add": ["resolved"]},
                      "fix_b": {"add": ["resolved"]}},
        protocol=informed(),
        goal="resolved",
        skills={"router": [{"select": {"branches": {
            "a": [{"send": {"to": "handler", "label": "go_a"}}]}}}]}))
    assert v.achievable


def test_selector_inventing_a_branch_is_non_conformant():
    v = check(pack(
        roles=["router", "handler"],
        capabilities={"fix_a": {"add": ["resolved"]},
                      "fix_b": {"add": ["resolved"]}},
        protocol=informed(),
        goal="resolved",
        skills={"router": [{"select": {"branches": {
            "c": [{"send": {"to": "handler", "label": "go_c"}}]}}}]}))
    assert not v.achievable
    assert v.reason == "NON_CONFORMANT"
