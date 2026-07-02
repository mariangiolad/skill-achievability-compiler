# The paper

`skillachievability.tex` — *Can This Agent Even Do That? A Decidable
Goal-Achievability Type Discipline for LLM-Synthesized Agent Skills*
(extended version), with `skillachievability.pdf` built from it.

This extended version completes and strengthens the original draft:

**Proofs written out** (the draft had statements or sketches):
- Theorem 2 (tolerance soundness) — full proof via monotonicity of
  reachability in the step relation, matching Coq `reach_mono`/`tolerance_sound`.
- Theorem 3 (capability monotonicity) — full proof, including why the other
  judgment premises are unaffected.
- Theorem 4 (decidability) — the proof now exhibits the actual decision
  procedure the implementation runs (symbolic configurations, predicate-state
  saturation, havoc widening at back edges) and proves termination,
  refutation-soundness of the widening, and exactness of the pruning.
- Theorem 5 (undecidability under autonomy) — a worked reduction from CFSM
  control-state reachability (courier-participant encoding of FIFO channels).

**New results (§6.6 and §7), from implementing and testing the compiler on
real skills:**
- Lemma (establisher closure) + Corollary (protocol-independent refutation):
  a goal needing an atom no capability establishes is refuted for *every*
  protocol over Γ — the certificate survives the undecidable autonomous
  fragment.
- Observed choice (Proj-Obs) + soundness by desugaring into broadcasts;
  the observation that unobserved choice is a ≥3-party asynchronous
  phenomenon, which is why conversation-embedded skills were falsely refuted.
- Adversarial (must-)achievability with compositional refutation soundness
  inherited from Theorem 1.
- Counterexample-guided compaction repair at the trust boundary, and the
  admission-control (SkillSpector-like) pre-pass.

**Evaluation extended** with the real-skill study: 32 public bundles across
capability profiles, mutation testing in both directions, and the live
semantic-compaction loop (4/4 deployed skills achievable, 6/6 seeded faults
caught with the wound named). See `docs/SEMANTIC_VALIDATION.md` and
`docs/REAL_SKILLS_REPORT.md` in the repository for the raw runs.

Citations marked `[verify]` are placeholders the original draft flagged for
bibliographic verification and remain flagged.

## Build

```bash
pdflatex skillachievability.tex && pdflatex skillachievability.tex
```

Requires a TeX Live with `mathpartir` (package `texlive-science`) and the
usual AMS/TikZ packages (`texlive-latex-extra`).

## Relation to the Coq development

`../proof/SkillAchievability.v` mechanizes the trusted core's soundness
theorems (T1 refutation soundness, T2 tolerance, T3 capability monotonicity,
plus the concrete FlightInstance), axiom-free under Coq 8.18 — it is the
theorem checker for the paper's central claims, not the compiler. The
compiler is the `skillc` Python package in this repository. The newer results
(establisher closure, the decision procedure of Theorem 4, Proj-Obs,
adversarial soundness) are proved in the paper; mechanizing them is listed as
future work in §11.
