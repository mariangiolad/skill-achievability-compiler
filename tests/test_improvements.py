"""Improvements beyond the original paper.

1. Establisher-closure refutation: a goal whose required atoms have no
   establisher in Gamma is refuted PROTOCOL-INDEPENDENTLY -- the certificate
   holds for every protocol over Gamma, spawning included.
2. Adversarial (must-)achievability: the paper's diamond is purely angelic;
   choices marked {"external": true} can instead be resolved by the
   environment, turning the search into AND-OR reachability.
"""
import pytest

from skillc import check
from skillc.checker import establishable_atoms
from skillc.pack import Pack


def pack(**kw):
    base = {"name": "t", "roles": ["agent"], "capabilities": {},
            "protocol": [], "goal": True}
    base.update(kw)
    return base


def act(cap, by="agent"):
    return {"act": {"cap": cap, "by": by}}


# ------------------------------------------ establisher-closure refutation

def test_establishable_atoms_closure():
    p = Pack.load(pack(
        capabilities={"a": {"add": ["x"], "del": ["y"]}},
        init_true=["y"], protocol=[], goal=True))
    assert establishable_atoms(p) == {"x", "y"}


def test_gamma_refutation_is_protocol_independent():
    """Same Gamma, goal needs an atom nothing establishes: refuted with the
    protocol-independent certificate, dead atom in the frontier."""
    v = check(pack(
        capabilities={"book": {"add": ["booked"]}},
        protocol=[act("book")],
        goal={"and": ["booked", "confirmation_sent"]}))
    assert not v.achievable and v.reason == "GOAL_UNSAT"
    assert v.frontier == ("confirmation_sent",)
    assert "protocol-independent" in v.detail


def test_gamma_refutation_survives_spawning():
    """The certificate quantifies over ALL protocols, so it refutes even
    outside the decidable fragment where reachability would say UNKNOWN."""
    v = check(pack(
        capabilities={"deliver": {"add": ["delivered"]}},
        protocol=[{"spawn": {"role": "helper"}}, act("deliver")],
        goal={"and": ["delivered", "ledger_updated"]}))
    assert v.label == "IMPOSSIBLE"          # not UNKNOWN
    assert v.reason == "GOAL_UNSAT"
    assert "ledger_updated" in v.frontier


def test_disjunction_with_one_live_disjunct_not_refuted():
    """or-goals must not be refuted when a live disjunct remains."""
    v = check(pack(
        capabilities={"book": {"add": ["booked"]}},
        protocol=[act("book")],
        goal={"or": ["booked", "confirmation_sent"]}))
    assert v.achievable


def test_negated_dead_atom_helps_rather_than_hurts():
    """not(dead-atom) is vacuously true under the closure; no refutation."""
    v = check(pack(
        capabilities={"book": {"add": ["booked"]}},
        protocol=[act("book")],
        goal={"and": ["booked", {"not": "cancelled"}]}))
    assert v.achievable


def test_init_true_atom_counts_as_establishable():
    v = check(pack(
        capabilities={"book": {"add": ["booked"]}},
        protocol=[act("book")],
        goal={"and": ["booked", "session_open"]},
        init_true=["session_open"]))
    assert v.achievable


# ---------------------------------------------- adversarial achievability

def external_choice_pack(**extra):
    """The service either confirms or declines; only the confirm branch can
    establish the goal."""
    return pack(
        roles=["agent", "service"],
        capabilities={"record": {"pre": "confirmed", "add": ["recorded"]},
                      "note_confirm": {"add": ["confirmed"]}},
        protocol=[{"choice": {"by": "service", "external": True, "branches": {
            "confirm": [{"msg": {"from": "service", "to": "agent",
                                 "label": "ok"}},
                        act("note_confirm"), act("record")],
            "decline": [{"msg": {"from": "service", "to": "agent",
                                 "label": "no"}}]}}}],
        goal="recorded", **extra)


def test_may_semantics_is_angelic_about_external_choice():
    v = check(external_choice_pack())          # default: may
    assert v.achievable


def test_adversarial_semantics_refutes_the_same_pack():
    v = check(external_choice_pack(), semantics="adversarial")
    assert not v.achievable
    assert v.reason == "GOAL_UNSAT"
    assert "decline" in v.detail               # the defeating branch is named


def test_adversarial_passes_when_every_branch_recovers():
    p = external_choice_pack()
    # give the decline branch a recovery path that also reaches the goal
    p["capabilities"]["record_denial"] = {"add": ["recorded"]}
    p["protocol"][0]["choice"]["branches"]["decline"].append(
        act("record_denial"))
    v = check(p, semantics="adversarial")
    assert v.achievable


def test_agents_own_choices_stay_existential_under_adversarial():
    v = check(pack(
        capabilities={"good": {"add": ["done"]}, "noop": {}},
        protocol=[{"choice": {"by": "agent", "branches": {
            "bad": [act("noop")],
            "good": [act("good")]}}}],
        goal="done"), semantics="adversarial")
    assert v.achievable


def test_external_flag_ignored_under_may():
    v = check(external_choice_pack())
    assert v.achievable


def test_bad_semantics_rejected():
    with pytest.raises(ValueError, match="unknown semantics"):
        check(pack(), semantics="pessimistic")
