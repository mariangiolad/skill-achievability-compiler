"""
build_corpus.py  --  emits corpus.json

Each entry pairs a natural-language skill (what an author writes) with its
*reference compaction* (the formal pack an LLM distills from that NL), a
ground-truth semantic label, and the failure category it exercises.

Ground truth is the TRUE semantic achievability of the goal.  The eval then
measures the checker against it.  The key claims under test:

  * NO false "IMPOSSIBLE"  (soundness, Coq T1)  -> false-negatives must be 0
  * SOME false "ACHIEVABLE" allowed (incompleteness, Coq T3) -> the spurious
    cases, each annotated with which residue (payload / intent) caused it.

Categories trace the user's own failure docs:
  HALLUCINATED_PLANNING  (infinite-loop doc, failure mode 2)
  INFINITE_LOOP / NO_PROGRESS (failure mode 1)
  DEADLOCK / NON_PROJECTABLE  (STJP one-pager, the freeze)
  REFINEMENT  (budget constraints)
  ACHIEVABLE / TOLERANCE  (detours, extra messages, subtyping)
  SPURIOUS  (T3 incompleteness demonstrations)
"""
import json

C = []

def add(id, category, ground_truth, nl, pack, note=""):
    C.append({"id": id, "category": category, "ground_truth": ground_truth,
              "nl": nl.strip(), "pack": pack, "note": note})

# ---------------------------------------------------------------- ACHIEVABLE
add("book_flight_ok", "ACHIEVABLE", "ACHIEVABLE",
"""
# Skill: Book a flight and confirm
Goal: the customer has a booked flight and a confirmation email is sent.
Tools: search_flights, filter_results, book_flight, send_email.
Steps: search, then filter, then book, then email the confirmation.
""",
{"name":"book_flight_ok","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   "filter":{"owner":"agent","pre":"searched","add":["filtered"]},
   "book":{"owner":"agent","pre":"filtered","add":["booked"]},
   "email":{"owner":"agent","pre":"booked","add":["confirmation_sent"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"filter","by":"agent"}},
             {"act":{"cap":"book","by":"agent"}},
             {"act":{"cap":"email","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent"]}})

add("budget_ok", "REFINEMENT", "ACHIEVABLE",
"""
# Skill: Book a flight under $500
Goal: a flight is booked at a price below 500 and confirmation is sent.
Tools: search, book_cheap (only books fares under 500), send_email.
""",
{"name":"budget_ok","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   "book_cheap":{"owner":"agent","pre":"searched","add":["booked"],
                 "nondet":{"price":{"cmp":["price","<",500]}}},
   "email":{"owner":"agent","pre":"booked","add":["confirmation_sent"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"book_cheap","by":"agent"}},
             {"act":{"cap":"email","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent",{"cmp":["price","<",500]}]}})

add("detour_ok", "TOLERANCE", "ACHIEVABLE",
"""
# Skill: Research then answer (with optional clarification)
Goal: a researched answer is delivered.
The worker may first ping the user with a status note (a detour that does not
change the outcome), then search, then deliver.
""",
{"name":"detour_ok","roles":["worker","user"],
 "capabilities":{
   "search":{"owner":"worker","add":["searched"]},
   "deliver":{"owner":"worker","pre":"searched","add":["answered"]}},
 "protocol":[{"msg":{"from":"worker","to":"user","label":"status_note"}},
             {"act":{"cap":"search","by":"worker"}},
             {"msg":{"from":"worker","to":"user","label":"status_note2"}},
             {"act":{"cap":"deliver","by":"worker"}}],
 "goal":"answered"},
 note="extra status messages (payload-level detail) must not refute the goal")

add("choice_informed_ok", "TOLERANCE", "ACHIEVABLE",
"""
# Skill: Triage then handle
Goal: the ticket is resolved.
The router picks 'simple' or 'complex' and TELLS the handler which path it
chose; the handler then resolves accordingly.
""",
{"name":"choice_informed_ok","roles":["router","handler"],
 "capabilities":{
   "resolve_simple":{"owner":"handler","add":["resolved"]},
   "resolve_complex":{"owner":"handler","add":["resolved"]}},
 "protocol":[{"choice":{"by":"router","branches":{
     "simple":[{"msg":{"from":"router","to":"handler","label":"go_simple"}},
               {"act":{"cap":"resolve_simple","by":"handler"}}],
     "complex":[{"msg":{"from":"router","to":"handler","label":"go_complex"}},
                {"act":{"cap":"resolve_complex","by":"handler"}}]}}}],
 "goal":"resolved"})

# --------------------------------------------------------- IMPOSSIBLE (sound)
add("hallucinated_email", "HALLUCINATED_PLANNING", "IMPOSSIBLE",
"""
# Skill: Book a flight and confirm
Goal: flight booked AND confirmation email sent.
Tools available: search, filter, book.   (No email tool is provided.)
But the plan still says: ...then send the confirmation email.
""",
{"name":"hallucinated_email","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   "filter":{"owner":"agent","pre":"searched","add":["filtered"]},
   "book":{"owner":"agent","pre":"filtered","add":["booked"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"filter","by":"agent"}},
             {"act":{"cap":"book","by":"agent"}},
             {"act":{"cap":"send_email","by":"agent"}}],   # <- undeclared tool
 "goal":{"and":["booked","confirmation_sent"]}},
 note="plan invokes a tool that does not exist -> MISSING_CAPABILITY")

add("no_establisher", "HALLUCINATED_PLANNING", "IMPOSSIBLE",
"""
# Skill: Book a flight and confirm
Goal: flight booked AND confirmation sent.
Tools: search, filter, book.  No tool can send a confirmation, and the plan
forgets that step entirely.
""",
{"name":"no_establisher","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   "filter":{"owner":"agent","pre":"searched","add":["filtered"]},
   "book":{"owner":"agent","pre":"filtered","add":["booked"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"filter","by":"agent"}},
             {"act":{"cap":"book","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent"]}},
 note="no capability establishes confirmation_sent -> GOAL_UNSAT (Coq FlightInstance)")

add("over_budget", "REFINEMENT", "IMPOSSIBLE",
"""
# Skill: Book a flight under $500
Goal: flight booked under 500 and confirmation sent.
The only booking tool available books premium fares (>= 800).
""",
{"name":"over_budget","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   "book_premium":{"owner":"agent","pre":"searched","add":["booked"],
                   "nondet":{"price":{"cmp":["price",">=",800]}}},
   "email":{"owner":"agent","pre":"booked","add":["confirmation_sent"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"book_premium","by":"agent"}},
             {"act":{"cap":"email","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent",{"cmp":["price","<",500]}]}},
 note="refinement on price is unsatisfiable along every run -> GOAL_UNSAT")

add("blocked_precondition", "INFINITE_LOOP", "IMPOSSIBLE",
"""
# Skill: Publish a report
Goal: the report is published.
publish requires the report to be APPROVED; but there is no approval tool and
nothing in the plan ever approves it, so publish can never fire.
""",
{"name":"blocked_precondition","roles":["agent"],
 "capabilities":{
   "draft":{"owner":"agent","add":["drafted"]},
   "publish":{"owner":"agent","pre":{"and":["drafted","approved"]},
              "add":["published"]}},
 "protocol":[{"act":{"cap":"draft","by":"agent"}},
             {"act":{"cap":"publish","by":"agent"}}],
 "goal":"published"},
 note="guard 'approved' never establishable -> BLOCKED_GUARD (the retry-forever cause)")

add("deadlock_unobserved", "DEADLOCK", "IMPOSSIBLE",
"""
# Skill: Plan / worker collaboration
Goal: the task result is delivered.
The worker decides whether to ASK a clarifying question or to DELIVER. In the
'ask' branch the planner must answer -- but the planner is never told the
worker chose to ask, so it just keeps waiting for a result. Classic freeze.
""",
{"name":"deadlock_unobserved","roles":["planner","worker"],
 "capabilities":{
   "answer":{"owner":"planner","add":["answered"]},
   "deliver":{"owner":"worker","pre":"answered","add":["delivered"]},
   "deliver_direct":{"owner":"worker","add":["delivered"]}},
 "protocol":[{"choice":{"by":"worker","branches":{
     "ask":[ {"act":{"cap":"answer","by":"planner"}},   # planner must act...
             {"act":{"cap":"deliver","by":"worker"}}],  # ...but was never told
     "direct":[{"act":{"cap":"deliver_direct","by":"worker"}}]}}}],
 "goal":"delivered"},
 note="planner must act in 'ask' branch with no distinguishing receive -> NON_PROJECTABLE")

add("missing_tool_chain", "HALLUCINATED_PLANNING", "IMPOSSIBLE",
"""
# Skill: Refund a customer
Goal: refund issued AND ledger updated.
Tools: lookup_order, issue_refund.   The plan also 'updates the ledger' but no
ledger tool exists.
""",
{"name":"missing_tool_chain","roles":["agent"],
 "capabilities":{
   "lookup":{"owner":"agent","add":["order_found"]},
   "refund":{"owner":"agent","pre":"order_found","add":["refunded"]}},
 "protocol":[{"act":{"cap":"lookup","by":"agent"}},
             {"act":{"cap":"refund","by":"agent"}},
             {"act":{"cap":"update_ledger","by":"agent"}}],   # undeclared
 "goal":{"and":["refunded","ledger_updated"]}},
 note="MISSING_CAPABILITY on update_ledger")

# ---------------------------------------------- SPURIOUS (T3 incompleteness)
add("spurious_payload", "SPURIOUS", "IMPOSSIBLE",
"""
# Skill: Book a flight under $500
Goal: booked under 500 and confirmed.
The 'filter_cheap' tool CLAIMS to keep only fares under 500, and the compaction
trusts that claim -- but in this market every real fare is >= 800, so no run
actually succeeds. The structure is fine; the payload claim is false.
""",
{"name":"spurious_payload","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   # compaction trusts the declared post-condition price<500 (payload faithfulness
   # is NOT verified by Layer A) -> abstraction admits a satisfying price
   "filter_cheap":{"owner":"agent","pre":"searched","add":["filtered"],
                   "nondet":{"price":{"cmp":["price","<",500]}}},
   "book":{"owner":"agent","pre":"filtered","add":["booked"]},
   "email":{"owner":"agent","pre":"booked","add":["confirmation_sent"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"filter_cheap","by":"agent"}},
             {"act":{"cap":"book","by":"agent"}},
             {"act":{"cap":"email","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent",{"cmp":["price","<",500]}]}},
 note="FALSE ACHIEVABLE: payload faithfulness of filter_cheap is a Layer-C "
      "(runtime) obligation, not decided here. Expected & sound per T3.")

add("spurious_intent", "SPURIOUS", "IMPOSSIBLE",
"""
# Skill: Schedule a meeting
Goal (what the USER meant): schedule with the RIGHT attendees next week.
The compacted goal only says 'meeting_scheduled'. A plan that schedules an
empty meeting satisfies the formal goal but not the user's intent.
""",
{"name":"spurious_intent","roles":["agent"],
 "capabilities":{
   "create_event":{"owner":"agent","add":["meeting_scheduled"]}},
 "protocol":[{"act":{"cap":"create_event","by":"agent"}}],
 "goal":"meeting_scheduled"},
 note="FALSE ACHIEVABLE: intent fidelity (does the formal goal capture what the "
      "user meant) is the top-edge residue, surfaced for human review, not decided.")

# A couple more straightforward ACHIEVABLE/IMPOSSIBLE for balance
add("recursion_ok", "ACHIEVABLE", "ACHIEVABLE",
"""
# Skill: Retry search until found, then answer
Goal: answer delivered. search may be tried; once found, deliver.
""",
{"name":"recursion_ok","roles":["worker"],
 "capabilities":{
   "search":{"owner":"worker","add":["found"]},
   "deliver":{"owner":"worker","pre":"found","add":["answered"]}},
 "protocol":[{"act":{"cap":"search","by":"worker"}},
             {"act":{"cap":"deliver","by":"worker"}}],
 "goal":"answered"})

add("two_goals_one_missing", "HALLUCINATED_PLANNING", "IMPOSSIBLE",
"""
# Skill: Onboard employee
Goal: account created AND badge issued.
Tools: create_account only. Badge system not integrated.
""",
{"name":"two_goals_one_missing","roles":["agent"],
 "capabilities":{
   "create_account":{"owner":"agent","add":["account_created"]}},
 "protocol":[{"act":{"cap":"create_account","by":"agent"}}],
 "goal":{"and":["account_created","badge_issued"]}},
 note="badge_issued has no establisher -> GOAL_UNSAT")

add("choice_one_branch_ok", "TOLERANCE", "ACHIEVABLE",
"""
# Skill: Pay invoice by card or transfer
Goal: invoice paid. Either branch (card or transfer) reaches it; the payer is
informed which rail to use.
""",
{"name":"choice_one_branch_ok","roles":["sys","payer"],
 "capabilities":{
   "pay_card":{"owner":"payer","add":["paid"]},
   "pay_transfer":{"owner":"payer","add":["paid"]}},
 "protocol":[{"choice":{"by":"sys","branches":{
     "card":[{"msg":{"from":"sys","to":"payer","label":"use_card"}},
             {"act":{"cap":"pay_card","by":"payer"}}],
     "transfer":[{"msg":{"from":"sys","to":"payer","label":"use_transfer"}},
                 {"act":{"cap":"pay_transfer","by":"payer"}}]}}}],
 "goal":"paid"})

import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "src", "skillc", "data", "corpus.json")
with open(OUT, "w") as f:
    json.dump(C, f, indent=2)
print(f"wrote {os.path.relpath(OUT)} with {len(C)} specs")
from collections import Counter
print("by category:", dict(Counter(c["category"] for c in C)))
print("by ground truth:", dict(Counter(c["ground_truth"] for c in C)))

# ==========================================================================
# Extended corpus: the decidable-fragment boundary (tail recursion, dynamic
# spawning) and the conformance premise.  Kept separate from the 15-spec
# headline corpus so the paper's confusion matrix stays reproducible.
# Ground truth may be UNKNOWN: outside the fragment the semi-decision must
# neither claim ACHIEVABLE nor IMPOSSIBLE.
# ==========================================================================

E = []

def add_ext(id, category, ground_truth, nl, pack, note=""):
    E.append({"id": id, "category": category, "ground_truth": ground_truth,
              "nl": nl.strip(), "pack": pack, "note": note})

add_ext("retry_loop_ok", "TOLERANCE", "ACHIEVABLE",
"""
# Skill: Retry search until found, then deliver
Goal: answer delivered. Search in a loop; when found, exit and deliver.
""",
{"name":"retry_loop_ok","roles":["worker"],
 "capabilities":{
   "search":{"owner":"worker","add":["found"]},
   "deliver":{"owner":"worker","pre":"found","add":["answered"]}},
 "protocol":[{"rec":{"name":"X","body":[
                {"act":{"cap":"search","by":"worker"}},
                {"choice":{"by":"worker","branches":{
                  "retry":[{"continue":"X"}],
                  "found":[]}}}]}},
             {"act":{"cap":"deliver","by":"worker"}}],
 "goal":"answered"},
 note="tail-recursive retry with an exit branch is inside the fragment")

add_ext("spin_forever", "INFINITE_LOOP", "IMPOSSIBLE",
"""
# Skill: Publish a report (but the plan only ever re-drafts)
Goal: published. The loop re-drafts forever; nothing establishes published.
""",
{"name":"spin_forever","roles":["agent"],
 "capabilities":{"draft":{"owner":"agent","add":["drafted"]}},
 "protocol":[{"rec":{"name":"X","body":[
                {"act":{"cap":"draft","by":"agent"}},
                {"continue":"X"}]}}],
 "goal":"published"},
 note="predicate-state saturation terminates the loop search -> GOAL_UNSAT")

add_ext("spawn_helpers", "AUTONOMY", "UNKNOWN",
"""
# Skill: Fan out research to freshly spawned subagents
Goal: report delivered. The planner spawns helper agents at run time.
""",
{"name":"spawn_helpers","roles":["planner"],
 "capabilities":{"deliver":{"owner":"planner","add":["delivered"]}},
 "protocol":[{"spawn":{"role":"helper"}},
             {"act":{"cap":"deliver","by":"planner"}}],
 "goal":"delivered"},
 note="dynamic topology -> outside the decidable fragment (Theorem 5)")

add_ext("spawn_with_ghost_tool", "AUTONOMY", "IMPOSSIBLE",
"""
# Skill: Fan out, then update the ledger
Goal: ledger updated. Spawns helpers AND invokes a tool nobody has.
""",
{"name":"spawn_with_ghost_tool","roles":["planner"],
 "capabilities":{},
 "protocol":[{"spawn":{"role":"helper"}},
             {"act":{"cap":"update_ledger","by":"planner"}}],
 "goal":"ledger_updated"},
 note="capability soundness survives autonomy: refute before degrading")

add_ext("nonconformant_handler", "CONFORMANCE", "IMPOSSIBLE",
"""
# Skill: Triage then handle -- but the declared handler only handles one path
Goal: resolved. Contract informs the handler of go_simple/go_complex; the
declared handler behaviour only receives go_simple.
""",
{"name":"nonconformant_handler","roles":["router","handler"],
 "capabilities":{
   "resolve_simple":{"owner":"handler","add":["resolved"]},
   "resolve_complex":{"owner":"handler","add":["resolved"]}},
 "protocol":[{"choice":{"by":"router","branches":{
     "simple":[{"msg":{"from":"router","to":"handler","label":"go_simple"}},
               {"act":{"cap":"resolve_simple","by":"handler"}}],
     "complex":[{"msg":{"from":"router","to":"handler","label":"go_complex"}},
                {"act":{"cap":"resolve_complex","by":"handler"}}]}}}],
 "goal":"resolved",
 "skills":{"handler":[{"branch":{"from":"router","branches":{
     "go_simple":[{"act":{"cap":"resolve_simple"}}]}}}]}},
 note="S_handler drops an external choice -> S </= G|handler (Sub-Ext)")

add_ext("conformant_tolerant_handler", "CONFORMANCE", "ACHIEVABLE",
"""
# Skill: Triage then handle -- handler declared with an EXTRA receive
Goal: resolved. The declared handler also accepts a go_escalate label the
contract never sends; extra external choices are safe (Sub-Ext).
""",
{"name":"conformant_tolerant_handler","roles":["router","handler"],
 "capabilities":{
   "resolve_simple":{"owner":"handler","add":["resolved"]},
   "resolve_complex":{"owner":"handler","add":["resolved"]}},
 "protocol":[{"choice":{"by":"router","branches":{
     "simple":[{"msg":{"from":"router","to":"handler","label":"go_simple"}},
               {"act":{"cap":"resolve_simple","by":"handler"}}],
     "complex":[{"msg":{"from":"router","to":"handler","label":"go_complex"}},
                {"act":{"cap":"resolve_complex","by":"handler"}}]}}}],
 "goal":"resolved",
 "skills":{"handler":[{"branch":{"from":"router","branches":{
     "go_simple":[{"act":{"cap":"resolve_simple"}}],
     "go_complex":[{"act":{"cap":"resolve_complex"}}],
     "go_escalate":[{"act":{"cap":"resolve_complex"}}]}}}]}},
 note="interface slack in the safe direction must not refute (T2 flavour)")

OUT_EXT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "src", "skillc", "data", "corpus_extended.json")
with open(OUT_EXT, "w") as f:
    json.dump(E, f, indent=2)
print(f"wrote {os.path.relpath(OUT_EXT)} with {len(E)} extended specs")
