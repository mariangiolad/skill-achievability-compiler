# skill-achievability-compiler

**`skillc`** — a static compiler that decides whether the *goal* of an agent
skill (a `SKILL.md`, agent markdown, or a formal achievability pack) is
achievable in a given capability context.  It is **sound for refutation**:
an `IMPOSSIBLE` verdict is a proof (relative to the declared capabilities and
frame assumption) that no run of the skill can reach its goal.  It is
deliberately **incomplete for achievement**: `ACHIEVABLE` means "structurally
admissible", not "guaranteed".

The soundness core is mechanized in Coq ([`proof/SkillAchievability.v`](proof/SkillAchievability.v),
zero axioms, audited by [`proof/check_assumptions.v`](proof/check_assumptions.v));
the checker decides capability-guarded may-reachability with z3, in
milliseconds, with no LLM in the trusted path.  The accompanying paper —
extended here with full proofs and four implementation-driven strengthenings —
lives in [`paper/`](paper/) ([PDF](paper/skillachievability.pdf)).

```
 natural-language skill ──► [ front-end compaction ] ──► pack ──► [ checker ] ──► verdict
      (SKILL.md)              UNTRUSTED                           TRUSTED
                              deterministic or LLM                sound for refutation
```

## Install

```bash
pip install -e ".[dev]"        # installs the `skillc` CLI
```

## Quick start

Check a real skill against the runtime that will execute it:

```console
$ skillc check call-to-book/SKILL.md --profile claude-ai
call-to-book: ACHIEVABLE

$ skillc check call-to-book/SKILL.md --profile claude-code
call-to-book: IMPOSSIBLE [MISSING_CAPABILITY]
  protocol invokes undeclared capabilities: ['ask_user_input_v0']
  missing: ask_user_input_v0 (line 7)
```

The same skill, two verdicts: achievability is always judged **relative to a
capability context Γ** (an environment *profile* plus the skill's own
`allowed-tools`/`tools` frontmatter).  A consumer-app skill that asks
questions via `ask_user_input_v0` is provably not executable as written under
Claude Code, which has no such tool.

Batch-scan a skill tree, compile a pack, or run the evaluation corpus:

```console
$ skillc scan /mnt/skills --profile claude-ai      # 32/32 achievable
$ skillc compile SKILL.md -o pack.json             # inspect the formal object
$ skillc check pack.json --json                    # machine-readable verdict
$ skillc eval                                      # corpus + soundness audit
$ skillc profiles                                  # claude-ai, claude-code, none
```

Exit codes: `0` achievable, `1` impossible, `2` error, `3` unknown (outside
the decidable fragment) — so `skillc check` can
gate CI for skill repositories.

## What the checker decides

A **pack** declares capabilities (STRIPS pre/effects, numeric assignments,
constrained non-determinism), a goal-marked global protocol (`act` / `msg` /
`choice` / tail-recursive `rec`/`continue` loops / `spawn`), a goal formula,
the initial state, and optionally per-role declared behaviours (`skills`).
The checker decides **all four premises of the paper's achievability
judgment** (§5.2):

```
   Γ ⊇ caps(G)          capability soundness   — no hallucinated tools
   G ⇓ {T_p}            realizability          — projection defined for every role
   ∀p. S_p ≤ G↾p        conformance            — declared skills refine their
                                                  contracts (Gay–Hole subtyping)
   Γ; G ⊨ ◇goal         liveness               — goal may-reachable (z3)
   ─────────────────────
   Γ ⊢ {S_p} : G ▷ ◇goal
```

Projection implements Proj-Sel / Proj-Brn / Proj-Mrg with the merge `⊓`
(label-union on external branches); conformance implements Sub-Ext / Sub-Int
coinductively.  Refutations name the failing premise:

| reason | failure mode it catches |
|---|---|
| `MISSING_CAPABILITY` | hallucinated planning — the protocol invokes a tool that is not granted |
| `GOAL_UNSAT` | no establisher for a goal conjunct, or a numeric refinement (e.g. *under $500*) unsatisfiable on every run |
| `BLOCKED_GUARD` | a mandatory action's precondition can never be satisfied (the retry-forever cause) |
| `NON_PROJECTABLE` | a role must act inside a branch it is never told about and the branches do not merge (unobserved choice → deadlock/handoff freeze) |
| `NON_CONFORMANT` | a declared role behaviour does not refine its projected contract — the verdict on `G` cannot be transported to it |

**The decidable fragment (Theorems 4–5).** Tail-recursive loops are explored
with predicate-state saturation plus numeric widening on the back edge —
widening only enlarges the reachable set, so refutation stays sound.  Dynamic
participant spawning (`spawn`) crosses the autonomy boundary
(Brand–Zafiropulo): the procedure degrades to a semi-decision — it still
refutes what survives autonomy and otherwise answers **`UNKNOWN`** (exit
code 3) instead of guessing.

**Beyond the original paper** (proved in [`paper/`](paper/), §6.5–§7):

- **Establisher-closure refutation** — a goal conjunct no capability
  establishes refutes *every* protocol over Γ in one SMT query, spawning
  included; `GOAL_UNSAT` with a `protocol-independent` certificate then means
  "acquire a tool", not "fix the plan".
- **Observed choice** (`"observed": true`) — a choice resolved inside a live
  conversation (assistant↔user chat, a phone call) is announced by the medium
  itself; projection treats it as an implicit broadcast (unobserved choice is
  a ≥3-party *asynchronous* phenomenon).  This eliminated every false
  refutation of real conversational skills.
- **Adversarial must-achievability** (`skillc check --adversarial`, choices
  marked `"external": true`) — the goal must survive every environment
  resolution while the agent's own choices stay existential (AND-OR search);
  adversarial refutations inherit soundness compositionally from T1.
- **Counterexample-guided compaction repair** — a `NON_PROJECTABLE`
  counterexample is fed back to the untrusted compactor for one bounded,
  structure-only repair round (it may not invent tools or weaken the goal);
  the verdict always comes from the trusted checker.

Tolerance comes from may-reachability (detours allowed), interface slack in
the safe direction (a skill may *offer more* receives and *make fewer*
selections than its contract), and goal-relevant abstraction — extra status
messages or beneficial branches never cause a refutation (Coq T2), and
*adding* capabilities never flips `ACHIEVABLE` to `IMPOSSIBLE` (Coq T3,
`cap_monotone`).

## Front-ends

1. **Deterministic markdown front-end** (default, no LLM).  Parses
   frontmatter (`allowed-tools` / `tools`), prose tool declarations
   (`Tools: a, b, c`), and extracts tool invocations from the prose
   ("ask via `ask_user_input_v0`", "use `str_replace`", …).  Unix commands
   and code symbols route through the profile's shell capability; fenced code
   blocks are not scanned.  Every extraction is reported with line-number
   provenance (`skillc compile` prints it to stderr) so the pack is
   inspectable at one checkpoint.
2. **Embedded pack**: a fenced block tagged ```` ```skillc-pack ```` inside
   the SKILL.md is validated and used verbatim — full checker power (guards,
   budgets, roles, choice) for authors who want precise semantics.
3. **LLM compaction** (`skillc compile --llm`, needs `ANTHROPIC_API_KEY`):
   semantic NL→pack distillation.  Untrusted by design — its output passes
   the same deterministic schema gate and trusted checker, so a hallucinated
   compaction can only produce a false `ACHIEVABLE` (caught by later layers),
   never a false `IMPOSSIBLE` about the pack it actually emitted.

## The bundle security pre-pass (`skillc audit`)

Before the formal pack is trusted, a SkillSpector-like deterministic scanner
vets the bundle itself — admission control at the compiler's boundary,
complementary to the type discipline:

```console
$ skillc audit ./my-skill
my-skill: ERROR [description-injection] instruction-injection pattern in the description ...
my-skill: ERROR [risky-code] pipe-to-shell install (SKILL.md:6)
```

Checks: manifest consistency (name/description present, name matches the
bundle directory), metadata poisoning (invisible/bidi Unicode,
instruction-injection patterns in the description or hidden in HTML
comments), risky code patterns in fenced blocks and bundle scripts
(pipe-to-shell, decode-and-execute, destructive commands, plaintext HTTP),
and permission-metadata consistency (prose invocations not covered by
`allowed-tools`).  Exit 1 on any error-severity finding.  All 32 real public
bundles pass with zero errors; the planted `poisoned-helper` fixture trips
every class.

## Results on real, public skills

Validated against Anthropic's public skills corpus
([anthropics/skills](https://github.com/anthropics/skills), 32 `SKILL.md`
files mounted at `/mnt/skills`, or fetched with
`python3 scripts/fetch_skills.py`):

* **32/32 achievable under the `claude-ai` profile** — their home runtime.
  Zero false refutations on deployed skills (the empirical face of T1).
* **16/32 refuted under the `claude-code` profile**, each with the exact
  missing tool named (`ask_user_input_v0`, `read_page`, `upload_file`,
  `create_file`, `str_replace`, `show_widget`, `search_mcp_registry`, …) and
  the source line.  Granting the named tools flips every one of them back to
  achievable (T3 on real data).

Full table: [`docs/REAL_SKILLS_REPORT.md`](docs/REAL_SKILLS_REPORT.md).

**Semantic level** ([`docs/SEMANTIC_VALIDATION.md`](docs/SEMANTIC_VALIDATION.md),
`scripts/semantic_validation.py`): four representative consumer skills were
LLM-compacted into semantic packs (goals like *booked ∧ calendar-updated ∧
user-informed* with per-step guards), through the schema gate and at most one
repair round — **4/4 check ACHIEVABLE** (no false alarms on deployed skills).
Each pack was then sabotaged with a known ground truth: drop a capability the
plan invokes, and strip a goal conjunct's establishers — **6/6 mutants
refuted**, naming the dropped tool (`MISSING_CAPABILITY`) or the dead conjunct
(`GOAL_UNSAT`, protocol-independent certificate) every time.  Deterministic
mutation testing over all 32 skills works in both directions: removing an
invoked tool from the profile flips the verdict and names exactly that tool;
granting the frontier back flips it to achievable.

On the 15-spec ground-truth corpus (`skillc eval`): **FN = 0** (no achievable
goal ever refuted — T1) and the only false `ACHIEVABLE`s are the two planted
`SPURIOUS` cases (payload faithfulness / intent fidelity), i.e. exactly the
residues the compiler openly defers to runtime monitoring and human review —
never a structural failure it should have caught.

## Tests

```bash
python3 -m pytest                          # 236 tests
SKILLC_SKILLS_DIR=./real-skills pytest tests/test_real_skills.py   # real corpus
SKILLC_LIVE_LLM=1 pytest tests/test_llm_frontend.py               # live LLM (opt-in)
coqc proof/SkillAchievability.v && coqc proof/check_assumptions.v  # the proof
```

The suite covers the formula language, the schema gate, every refutation
reason, projection/merge/subtyping, tail recursion and the autonomy boundary
(loops saturate, `spawn` degrades to `UNKNOWN`, refutation survives
autonomy), conformance (Sub-Ext/Sub-Int both directions), the corpus
confusion matrix (reproduced exactly: TP=6 FN=0 FP=2 TN=7) plus a 6-spec
extended corpus for the fragment boundary, the markdown front-end
(extraction, classification, profiles, embedded packs), the bundle audit
(poisoned fixture trips every class; real bundles are clean), the CLI, and —
when a corpus is present — every real public skill under multiple profiles,
including the monotone-widening property.

## Layout

```
src/skillc/            the compiler package
  checker.py             trusted core: the four-premise judgment over z3
                         may-reachability, loops + widening, UNKNOWN boundary
  session.py             projection (Proj-Sel/Brn/Mrg), merge, Gay-Hole subtyping
  pack.py                pack model + deterministic schema gate
  formula.py             guard/goal mini-language
  profiles.py            capability contexts (claude-ai, claude-code, none)
  audit.py               SkillSpector-like bundle security pre-pass
  frontend/markdown.py   deterministic SKILL.md -> pack compaction
  frontend/llm.py        optional LLM compaction (untrusted, env-gated)
  evaluate.py            corpus evaluation + soundness/incompleteness audit
  cli.py                 skillc compile | check | scan | audit | eval | profiles
  data/                  built-in profiles + evaluation corpora
paper/                 the paper (LaTeX + built PDF): full proofs +
                       implementation-driven extensions
proof/                 the theorem checkers for the paper's claims (Coq 8.18,
                       zero axioms) -- certify T1/T2/T3; the compiler itself
                       is the Python package above
corpus/build_corpus.py 15 headline specs + 6 fragment/conformance specs
docs/                  compaction prompt + real-skill scan report
examples/              embedded-pack skills: retry loop, conformance-checked team
scripts/               fetch_skills.py, make_report.py
tests/                 the test suite (pytest)
```

## Honest limitations

Everything is proved about the *declared* capabilities and protocol; if the
prose lies, the checker verifies a fiction (honest declaration is a runtime
obligation — the `skillc audit` pre-pass narrows, but does not close, that
gap).  The deterministic front-end is a conservative heuristic — its
extraction is inspectable and a misextraction only makes the checker judge a
different pack, but it does not understand semantics (use the embedded-pack
escape hatch or `--llm` for that).  The merge `⊓` implements label-union on
external branches and structural recursion on equal prefixes — a sound core
of, not the complete, MPST merge lattice; loop widening havocs *all* numeric
state at the back edge (coarser than needed, always in the sound direction).
Dynamic subagent spawning is outside the decidable fragment and yields
`UNKNOWN`, never a guess.
