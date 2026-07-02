# LLM Compaction: natural-language skill → formal achievability pack

This is the **untrusted** front-end of the pipeline. An LLM reads a
natural-language skill / agent markdown and *compacts* it into a formal
**pack**: capabilities with preconditions and effects, a goal-marked global
protocol, and an initial state. The downstream checker is **sound regardless
of what the LLM produces** — a buggy compaction can only cause a *false
ACHIEVABLE* (caught later by the runtime monitor / human review), never a
false IMPOSSIBLE about the pack it actually emitted.

The compaction is exactly the "abstract away the prose into packs of
precondition / effect / deduction, then see if the goal is reachable" step.

## Trust boundary

```
   natural language  ──►  [ LLM compaction ]  ──►  pack (JSON)  ──►  [ checker ]  ──►  verdict
        (author)            UNTRUSTED                              TRUSTED (Coq-proved)
                            may hallucinate                        sound for refutation
```

The only thing the LLM must get right for *soundness* is: do not invent
capabilities or effects that the prose does not grant. If it under-grants, the
checker may wrongly refute — but that is surfaced as a counterexample the
author can inspect ("you say you can't send email; did you mean to?"). If it
over-grants, the checker may wrongly pass — caught downstream. Either error is
**inspectable at one checkpoint**, which is the whole architectural point.

## Pack schema

```jsonc
{
  "name": "string",
  "roles": ["string", ...],
  "capabilities": {
    "<cap>": {
      "owner": "<role>",
      "pre":  <formula>,          // guard; default true
      "add":  ["pred", ...],      // predicates set TRUE  (STRIPS effect)
      "del":  ["pred", ...],      // predicates set FALSE
      "assigns": {"var": <expr>}, // deterministic numeric update v := expr
      "nondet":  {"var": <formula over the NEW value>}  // v := * s.t. constraint
    }
  },
  "protocol": [ <step>, ... ],     // the goal-marked global protocol
  "goal": <formula>,
  "init_true": ["pred", ...],      // predicates true at start (frame: else false)
  "init_constraints": [ <formula>, ... ]
}
```

`<step>` is one of:
```jsonc
{"act":    {"cap": "<cap>", "by": "<role>"}}        // effectful action
{"msg":    {"from":"<role>","to":"<role>","label":"<l>"}}  // communication
{"choice": {"by":"<role>","branches":{"<label>":[<step>...], ...}}}
{"goal":   <formula>}                                // explicit goal marker (optional)
```

`<formula>`: `"pred"` | `true`/`false` | `{"and":[...]}` | `{"or":[...]}` |
`{"not":f}` | `{"cmp":[expr,"<|<=|==|>|>=|!=",expr]}`
`<expr>`: `"var"` | int | `{"+":[e,e]}` | `{"-":[e,e]}` | `{"*":[c,e]}`

## The prompt (verbatim)

> You convert a natural-language agent skill into a formal achievability pack.
> Output **only** JSON conforming to the schema below. Be conservative:
>
> 1. Declare a capability **only** if the prose says the agent has that tool.
>    Never invent a tool to make the goal reachable. If the plan mentions an
>    action with no corresponding tool, still put it in the `protocol` as an
>    `act`, but do **not** add it to `capabilities` — the checker will flag the
>    gap. This is the single most important rule.
> 2. For each capability, extract its precondition (`pre`) and its effects
>    (`add`/`del`/`assigns`/`nondet`) from what the prose claims. Use `nondet`
>    for "books a fare under 500" style post-conditions (the value is not fixed
>    but is constrained). You are *trusting* the prose here; faithfulness of
>    that claim is checked later, not now.
> 3. Encode the goal as a formula over predicates and numeric comparisons.
>    Capture every conjunct the user asked for, including refinements like
>    "under $500".
> 4. Encode the plan/coordination as the `protocol`. Use `choice` where the
>    prose describes branching, and `msg` for messages between roles. If a role
>    must act based on a branch, ensure a `msg` informs it of that branch;
>    if the prose does not provide one, leave it out (the checker will detect
>    the non-projectable handoff).
> 5. List predicates true at the start in `init_true`. Everything else is false
>    by default (frame assumption).
>
> Natural-language skill:
> ```
> {NL_SKILL}
> ```
> JSON pack:

## Live vs. reference compaction

`compaction.py` will call this prompt against `api.anthropic.com` if
`ANTHROPIC_API_KEY` is set, and otherwise fall back to the **reference
compactions** stored in `corpus.json` (which are what a faithful LLM should
produce). The scientific content — checker soundness and the eval — does not
depend on a live model: the LLM is the untrusted producer by design.
