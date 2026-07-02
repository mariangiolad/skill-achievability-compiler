"""Optional LLM compaction front-end (untrusted, env-gated).

Produces a *semantic* pack from natural language via the Anthropic API --
capturing guards, budgets, roles, and branching that the deterministic
front-end does not attempt.  The output is untrusted by design: it passes
through the deterministic schema gate (validate_pack) and then the trusted
checker; a hallucinated compaction can only yield a false ACHIEVABLE (caught
by later layers), never a false IMPOSSIBLE about the pack it actually emitted.

Requires ANTHROPIC_API_KEY.  Never used implicitly: only via
`skillc compile --llm` or a direct call to compact().
"""
from __future__ import annotations

import json
import os
import urllib.request

from ..pack import validate_pack

DEFAULT_MODEL = "claude-sonnet-5"
API_URL = "https://api.anthropic.com/v1/messages"

SCHEMA_DOC = """
Pack schema (JSON):
{
  "name": "string",
  "roles": ["string", ...],
  "capabilities": {
    "<cap>": {
      "owner": "<role>",
      "pre":  <formula>,           // guard; default true
      "add":  ["pred", ...],       // predicates set TRUE (STRIPS effect)
      "del":  ["pred", ...],       // predicates set FALSE
      "assigns": {"var": <expr>},  // deterministic numeric update v := expr
      "nondet":  {"var": <formula over the NEW value>}
    }
  },
  "protocol": [<step>, ...],
  "goal": <formula>,
  "init_true": ["pred", ...],
  "init_constraints": [<formula>, ...]
}
<step>    = {"act": {"cap": "<cap>", "by": "<role>"}}
          | {"msg": {"from": "<role>", "to": "<role>", "label": "<l>"}}
          | {"choice": {"by": "<role>", "branches": {"<label>": [<step>...], ...}}}
          | {"goal": <formula>}
          | {"rec": {"name": "X", "body": [<step>...]}}   // tail-recursive loop
          | {"continue": "X"}                             // last step of its block
          | {"spawn": {"role": "<role>"}}   // runtime participant spawning
Optionally declare per-role behaviours for conformance checking:
"skills": {"<role>": [<local step>...]} with local steps
  {"send": {"to","label"}} | {"recv": {"from","label"}} | {"act": {"cap"}}
  | {"select": {"branches": {...}}} | {"branch": {"from", "branches": {...}}}
  | {"rec": {"name","body"}} | {"continue": "X"}
<formula> = "pred" | true | false | {"and":[...]} | {"or":[...]} | {"not": f}
          | {"cmp": [expr, "<"|"<="|"=="|">"|">="|"!=", expr]}
<expr>    = "var" | int | {"+":[e,e]} | {"-":[e,e]} | {"*":[e,e]}
"""

SYSTEM = (
    "You convert a natural-language agent skill into a formal achievability "
    "pack. Output ONLY JSON conforming to the schema. Be conservative:\n"
    "1. Declare a capability ONLY if the prose grants that tool. Never invent "
    "a tool to make the goal reachable. If the plan mentions an action with "
    "no corresponding tool, still emit it in the protocol as an 'act', but do "
    "NOT add it to capabilities -- the checker will flag the gap. This is the "
    "single most important rule.\n"
    "2. For each capability, extract its precondition (pre) and effects "
    "(add/del/assigns/nondet) from what the prose claims. Use nondet for "
    "\"books a fare under 500\"-style post-conditions.\n"
    "3. Encode the goal as a formula capturing every conjunct the user asked "
    "for, including refinements like \"under $500\".\n"
    "4. Encode the plan as the protocol; use 'choice' for branching and 'msg' "
    "for inter-role messages. If a role must act inside a branch, include the "
    "informing msg only if the prose provides one.\n"
    "5. List predicates true at the start in init_true; everything else is "
    "false by default (frame assumption).\n"
    "6. Use rec/continue for retry loops (continue must be the last step of "
    "its block: only tail recursion is decidable). If the prose spawns "
    "subagents at run time, emit a spawn step -- the checker degrades to "
    "UNKNOWN rather than guessing.\n"
    "7. Abstract goal-irrelevant payload detail away (the tolerance dial): "
    "keep the pack SMALL -- at most ~12 capabilities and ~25 protocol steps. "
    "Merge micro-steps that share a tool; model only state that the goal or "
    "some guard mentions.\n"
    "8. IMPORTANT -- observed choices. Unobserved choice is a phenomenon of "
    "asynchronous multi-agent handoffs; inside a live conversation the "
    "outcome of a choice is announced by the medium itself. Whenever a "
    "choice is resolved within a conversation among the roles that then act "
    "on it (an assistant<->user chat, a phone call), set \"observed\": true "
    "on that choice. In a skill that is one continuous conversation between "
    "the agent and its user, EVERY choice by either of them is observed. "
    "Reserve msg steps for genuinely asynchronous handoffs between separate "
    "agents; a choice with neither observed:true nor informing msgs is "
    "refuted as a deadlock. Use \"external\": true when the environment "
    "rather than the agent resolves the choice.\n" + SCHEMA_DOC)

RUNTIME_ABILITIES_NOTE = (
    "\nThe skill executes in a runtime that ALREADY grants the agent these "
    "general abilities: {abilities}. When the plan performs an action that "
    "one of these abilities covers, DECLARE it as a capability (owner: the "
    "acting role) -- you are not inventing a tool, the runtime provides it. "
    "Leave an act undeclared ONLY when the prose itself signals the tool "
    "may be absent (e.g. 'where the save_skill tool exists') or the action "
    "exceeds every listed ability.")

CONSUMER_ABILITIES = [
    "converse with the user and ask questions",
    "browse the web and operate a browser session",
    "place and hold phone calls when the flow is phone-based",
    "read and write files and present them to the user",
    "check and update the user's calendar",
    "use memory of the user's stated preferences",
]


def compact(nl: str, model: str = DEFAULT_MODEL, timeout: int = 600,
            runtime_abilities: list[str] | None = None) -> dict:
    """Compact natural language into a validated pack via the Anthropic API.

    runtime_abilities: general abilities the target runtime grants (the
    Gamma_0 the prose presupposes without naming tools); without it the
    compactor under-grants and refutes deployed skills that assume a phone,
    a browser, or a user to talk to."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; the LLM front-end is "
                           "opt-in -- use the deterministic front-end instead")
    system = SYSTEM
    if runtime_abilities:
        system += RUNTIME_ABILITIES_NOTE.format(
            abilities="; ".join(runtime_abilities))
    body = json.dumps({
        "model": model,
        "max_tokens": 16000,
        "system": system,
        "messages": [{"role": "user",
                      "content": f"Natural-language skill:\n```\n{nl}\n```\nJSON pack:"}],
    }).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    text = "".join(b.get("text", "") for b in out.get("content", [])
                   if b.get("type") == "text").strip()
    pack = _extract_json_object(text)
    validate_pack(pack)          # the deterministic gate on untrusted output
    return pack


REPAIR_PROMPT = (
    "The trusted checker refuted the pack you produced, with this "
    "counterexample:\n\n  {reason}: {detail}\n\n"
    "This is usually a modelling artifact of the communication structure, "
    "not a real fault in the skill. Repair the pack and output ONLY the "
    "corrected JSON. You may ONLY adjust communication structure: set "
    "\"observed\": true on choices that are resolved inside a conversation "
    "the acting roles share, or add the informing msg steps the prose "
    "actually describes. You may NOT add or remove capabilities, change any "
    "effect, or weaken the goal.\n\nYour previous pack:\n{pack}\n")


def compact_with_repair(nl: str, model: str = DEFAULT_MODEL,
                        runtime_abilities: list[str] | None = None,
                        rounds: int = 2) -> tuple[dict, list[str]]:
    """Counterexample-guided compaction: compact, check, and when the trusted
    checker refutes with NON_PROJECTABLE (almost always an under-modelled
    conversation, not a real deadlock in the prose), feed the counterexample
    back to the untrusted compactor for a bounded number of repair rounds.

    Only NON_PROJECTABLE triggers repair: repairing MISSING_CAPABILITY or
    GOAL_UNSAT would tempt the model to invent tools or weaken the goal,
    which rule 1 forbids.  Returns (pack, repair_log); soundness is untouched
    -- every candidate passes the schema gate and the final verdict still
    comes from the trusted checker.
    """
    from ..checker import check as _check
    log: list[str] = []
    pack = compact(nl, model=model, runtime_abilities=runtime_abilities)
    for _ in range(rounds):
        v = _check(pack)
        if v.achievable or v.reason != "NON_PROJECTABLE":
            break
        log.append(f"repair round: {v.reason}: {v.detail}")
        followup = REPAIR_PROMPT.format(reason=v.reason, detail=v.detail,
                                        pack=json.dumps(pack))
        pack = compact(nl + "\n\n" + followup, model=model,
                       runtime_abilities=runtime_abilities)
    return pack, log


def _extract_json_object(text: str) -> dict:
    """Pull the first balanced top-level JSON object out of model output
    (tolerates prose or code fences around it)."""
    start = text.find("{")
    if start < 0:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unbalanced JSON object in model output "
                     "(truncated response?)")
