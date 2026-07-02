"""Verdict-level tests of the trusted checker, one per refutation reason,
plus the tolerance behaviours and the T3 (cap monotonicity) property."""
import pytest

from skillc import check
from skillc.evaluate import load_corpus


def pack(**kw):
    base = {"name": "t", "roles": ["agent"], "capabilities": {},
            "protocol": [], "goal": True}
    base.update(kw)
    return base


def act(cap, by="agent"):
    return {"act": {"cap": cap, "by": by}}


def test_trivial_goal_achievable():
    v = check(pack())
    assert v.achievable and v.label == "ACHIEVABLE"


def test_linear_chain_achievable_with_witness():
    v = check(pack(
        capabilities={
            "search": {"add": ["searched"]},
            "book": {"pre": "searched", "add": ["booked"]}},
        protocol=[act("search"), act("book")],
        goal="booked"))
    assert v.achievable
    assert v.witness == (("act", "search"), ("act", "book"))


def test_missing_capability():
    v = check(pack(
        capabilities={"search": {"add": ["searched"]}},
        protocol=[act("search"), act("send_email")],
        goal="searched"))
    assert not v.achievable
    assert v.reason == "MISSING_CAPABILITY"
    assert v.frontier == ("send_email",)


def test_goal_unsat_no_establisher():
    # STRIPS frame: confirmation_sent is false unless some effect adds it.
    v = check(pack(
        capabilities={"book": {"add": ["booked"]}},
        protocol=[act("book")],
        goal={"and": ["booked", "confirmation_sent"]}))
    assert not v.achievable
    assert v.reason == "GOAL_UNSAT"


def test_blocked_guard():
    v = check(pack(
        capabilities={
            "draft": {"add": ["drafted"]},
            "publish": {"pre": {"and": ["drafted", "approved"]},
                        "add": ["published"]}},
        protocol=[act("draft"), act("publish")],
        goal="published"))
    assert not v.achievable
    assert v.reason == "BLOCKED_GUARD"
    assert "publish" in v.detail


def test_non_projectable_unobserved_choice():
    v = check(pack(
        roles=["planner", "worker"],
        capabilities={
            "answer": {"add": ["answered"]},
            "deliver": {"pre": "answered", "add": ["delivered"]},
            "deliver_direct": {"add": ["delivered"]}},
        protocol=[{"choice": {"by": "worker", "branches": {
            "ask": [act("answer", "planner"), act("deliver", "worker")],
            "direct": [act("deliver_direct", "worker")]}}}],
        goal="delivered"))
    assert not v.achievable
    assert v.reason == "NON_PROJECTABLE"
    assert "planner" in v.detail


def test_informed_choice_is_projectable_and_achievable():
    v = check(pack(
        roles=["router", "handler"],
        capabilities={
            "fix_a": {"add": ["resolved"]},
            "fix_b": {"add": ["resolved"]}},
        protocol=[{"choice": {"by": "router", "branches": {
            "a": [{"msg": {"from": "router", "to": "handler", "label": "go_a"}},
                  act("fix_a", "handler")],
            "b": [{"msg": {"from": "router", "to": "handler", "label": "go_b"}},
                  act("fix_b", "handler")]}}}],
        goal="resolved"))
    assert v.achievable
    assert ("choose", "a") in v.witness or ("choose", "b") in v.witness


def test_choice_is_existential_one_good_branch_suffices():
    v = check(pack(
        capabilities={"win": {"add": ["done"]}, "noop": {}},
        protocol=[{"choice": {"by": "agent", "branches": {
            "bad": [act("noop")],
            "good": [act("win")]}}}],
        goal="done"))
    assert v.achievable


def test_budget_refinement_satisfiable():
    v = check(pack(
        capabilities={"book": {"add": ["booked"],
                               "nondet": {"price": {"cmp": ["price", "<", 500]}}}},
        protocol=[act("book")],
        goal={"and": ["booked", {"cmp": ["price", "<", 500]}]}))
    assert v.achievable


def test_budget_refinement_unsatisfiable_on_every_run():
    v = check(pack(
        capabilities={"book": {"add": ["booked"],
                               "nondet": {"price": {"cmp": ["price", ">=", 800]}}}},
        protocol=[act("book")],
        goal={"and": ["booked", {"cmp": ["price", "<", 500]}]}))
    assert not v.achievable
    assert v.reason == "GOAL_UNSAT"


def test_deterministic_assign_and_arithmetic():
    v = check(pack(
        capabilities={
            "init": {"assigns": {"x": 3}, "add": ["started"]},
            "double": {"assigns": {"x": {"*": [2, "x"]}}}},
        protocol=[act("init"), act("double")],
        goal={"and": ["started", {"cmp": ["x", "==", 6]}]}))
    assert v.achievable


def test_delete_effect_and_frame():
    v = check(pack(
        capabilities={
            "grab": {"add": ["holding"]},
            "drop": {"pre": "holding", "del": ["holding"]}},
        protocol=[act("grab"), act("drop")],
        goal="holding"))
    assert not v.achievable
    assert v.reason == "GOAL_UNSAT"


def test_goal_marker_midway():
    v = check(pack(
        capabilities={"a": {"add": ["done"]}, "b": {"del": ["done"]}},
        protocol=[act("a"), {"goal": "done"}, act("b")],
        goal="done"))
    assert v.achievable        # goal observed at the marker, before b undoes it


def test_detour_messages_do_not_refute():
    v = check(pack(
        roles=["worker", "user"],
        capabilities={"do": {"add": ["done"]}},
        protocol=[{"msg": {"from": "worker", "to": "user", "label": "status"}},
                  act("do", "worker"),
                  {"msg": {"from": "worker", "to": "user", "label": "status2"}}],
        goal="done"))
    assert v.achievable


def test_init_true_and_init_constraints():
    v = check(pack(
        capabilities={"spend": {"pre": "funded",
                                "assigns": {"balance": {"-": ["balance", 100]}}}},
        protocol=[act("spend")],
        goal={"cmp": ["balance", ">=", 0]},
        init_true=["funded"],
        init_constraints=[{"cmp": ["balance", "==", 100]}]))
    assert v.achievable


def test_cap_monotone_on_corpus():
    """Coq T3 operational check: adding a fresh capability to any corpus pack
    never turns ACHIEVABLE into IMPOSSIBLE."""
    for c in load_corpus():
        before = check(c["pack"]).achievable
        widened = dict(c["pack"])
        widened["capabilities"] = dict(widened["capabilities"],
                                       extra_cap={"add": ["extra_pred"]})
        after = check(widened).achievable
        if before:
            assert after, f"cap_monotone violated on {c['id']}"
