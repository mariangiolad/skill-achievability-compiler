# Semantic validation on real skills

`skillc 0.2.0`, LLM compaction model `claude-sonnet-5` (untrusted front-end; every verdict below is produced by the trusted checker on the schema-gated pack).  Regenerate with `python3 scripts/semantic_validation.py`.

Protocol: compact each real skill into a semantic pack; the deployed skill must check ACHIEVABLE.  Then sabotage the pack two ways with a known ground truth -- drop a capability the plan invokes, and strip a goal conjunct's establishers -- and require the compiler to refute each mutant *and name the wound*.

### `call-to-book`

* compacted: 13 capabilities, 8 protocol steps, goal `{"or": [{"and": ["user_informed", "calendar_updated", "booking_confirmed", "identity_disclosed"]}, "user_informed_reason"]}`
* repair round: NON_PROJECTABLE: role 'agent' must act in a branch of the choice by 'business' but receives no message distinguishing the branches, and the branch behaviours do not merge (unobserved choice -> deadlock/handoff failure)
* **original: ACHIEVABLE**
* mutation `drop add_to_calendar` -> **IMPOSSIBLE** [MISSING_CAPABILITY] frontier=['add_to_calendar'] (caught, tool named)

### `grocery-shopping`

* compacted: 12 capabilities, 13 protocol steps, goal `{"and": ["store_selected", "occasion_selected", "list_built", "budget_set", "delivery_window_suggested", "list_confirmed", "cart_built", "summary_shown", "summary_confirmed", "handoff_done"]}`
* **original: ACHIEVABLE**
* mutation `drop ask_budget` -> **IMPOSSIBLE** [MISSING_CAPABILITY] frontier=['ask_budget'] (caught, tool named)
* mutation `strip establishers of budget_set` -> **IMPOSSIBLE** [GOAL_UNSAT] frontier=['budget_set'] (caught, atom named)

### `cancel-unsubscribe`

* compacted: 12 capabilities, 2 protocol steps, goal `{"and": ["subscription_cancelled", "summary_shown"]}`
* **original: ACHIEVABLE**
* mutation `drop audit_statement` -> **IMPOSSIBLE** [MISSING_CAPABILITY] frontier=['audit_statement'] (caught, tool named)
* mutation `strip establishers of subscription_cancelled` -> **IMPOSSIBLE** [GOAL_UNSAT] frontier=['subscription_cancelled'] (caught, atom named)

### `prescription-refill`

* compacted: 17 capabilities, 3 protocol steps, goal `{"and": [{"or": ["refill_submitted", "prescriber_contacted"]}, "summary_shown"]}`
* repair round: NON_PROJECTABLE: role 'agent' must act in a branch of the choice by 'pharmacy' but receives no message distinguishing the branches, and the branch behaviours do not merge (unobserved choice -> deadlock/handoff failure)
* **original: ACHIEVABLE**
* mutation `drop attempt_online_portal` -> **IMPOSSIBLE** [MISSING_CAPABILITY] frontier=['attempt_online_portal'] (caught, tool named)

## Summary

* pass direction: 4/4 real skills compact to an ACHIEVABLE pack (0 false alarms).
* refute direction: 6/6 seeded semantic faults caught with the exact missing tool / dead goal atom named.
