"""Corpus evaluation: measure the checker against ground-truth labels.

Claims under test (tied to the Coq proof):

  * SOUNDNESS (T1): the checker never emits a false IMPOSSIBLE
      => false negatives (truly achievable, called impossible) must be 0.
  * INCOMPLETENESS (T3): the checker may emit a false ACHIEVABLE, but every
    one must be an annotated SPURIOUS case (payload/intent residue), never a
    structural failure it should have caught.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources

from .checker import check


def load_corpus() -> list[dict]:
    data = resources.files("skillc").joinpath("data/corpus.json").read_text(
        encoding="utf-8")
    return json.loads(data)


@dataclass
class EvalRow:
    id: str
    category: str
    truth: str
    predicted: str
    reason: str

    @property
    def correct(self) -> bool:
        return self.truth == self.predicted


@dataclass
class EvalResult:
    rows: list[EvalRow] = field(default_factory=list)
    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0
    fp_ids: list[str] = field(default_factory=list)
    fn_ids: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.rows)

    @property
    def sound(self) -> bool:
        """Coq T1 empirically: no false IMPOSSIBLE."""
        return self.fn == 0

    def fp_all_spurious(self, corpus: list[dict]) -> bool:
        """Coq T3 empirically: every false ACHIEVABLE is annotated residue."""
        cats = {c["id"]: c["category"] for c in corpus}
        return all(cats[i] == "SPURIOUS" for i in self.fp_ids)


def evaluate(corpus: list[dict] | None = None) -> EvalResult:
    corpus = corpus if corpus is not None else load_corpus()
    res = EvalResult()
    for c in corpus:
        v = check(c["pack"])
        pred = v.label
        truth = c["ground_truth"]
        res.rows.append(EvalRow(c["id"], c["category"], truth, pred, v.reason))
        if truth == "ACHIEVABLE" and pred == "ACHIEVABLE":
            res.tp += 1
        elif truth == "IMPOSSIBLE" and pred == "IMPOSSIBLE":
            res.tn += 1
        elif truth == "IMPOSSIBLE" and pred == "ACHIEVABLE":
            res.fp += 1
            res.fp_ids.append(c["id"])
        else:
            res.fn += 1
            res.fn_ids.append(c["id"])
    return res


def format_report(res: EvalResult, corpus: list[dict] | None = None) -> str:
    corpus = corpus if corpus is not None else load_corpus()
    notes = {c["id"]: c.get("note", "") for c in corpus}
    w = max(len(r.id) for r in res.rows)
    lines = ["=" * 92,
             f"{'spec':<{w}}  {'category':<22} {'truth':<11} {'verdict':<11} {'reason':<18} ok",
             "-" * 92]
    for r in res.rows:
        lines.append(f"{r.id:<{w}}  {r.category:<22} {r.truth:<11} "
                     f"{r.predicted:<11} {r.reason:<18} {'Y' if r.correct else 'N'}")
    lines += ["=" * 92, "",
              f"Confusion matrix (positive = ACHIEVABLE), N={res.n}",
              "                 predicted ACHIEVABLE   predicted IMPOSSIBLE",
              f"  truly ACHIEVABLE        TP={res.tp:<2}                 FN={res.fn:<2}",
              f"  truly IMPOSSIBLE        FP={res.fp:<2}                 TN={res.tn:<2}",
              ""]
    lines.append("--- SOUNDNESS AUDIT (Coq T1: no false IMPOSSIBLE) ---")
    if res.sound:
        lines.append("  PASS: 0 false negatives; no achievable goal was wrongly refuted.")
    else:
        lines.append(f"  FAIL: {res.fn} false negative(s): {res.fn_ids}")
    lines.append("")
    lines.append("--- INCOMPLETENESS AUDIT (Coq T3: false ACHIEVABLE only on residue) ---")
    for i in res.fp_ids:
        lines.append(f"  {i}: {notes.get(i, '')}")
    lines.append("  PASS: all false positives are SPURIOUS residue cases."
                 if res.fp_all_spurious(corpus)
                 else "  FAIL: a structural failure slipped through!")
    return "\n".join(lines)
