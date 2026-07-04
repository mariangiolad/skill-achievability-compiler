"""Type-check the mechanized soundness proof, when Coq is installed."""
import shutil
import subprocess
from pathlib import Path

import pytest

PROOF = Path(__file__).parent.parent / "proof"

pytestmark = pytest.mark.skipif(shutil.which("coqc") is None,
                                reason="coqc not installed")


def test_soundness_proof_typechecks(tmp_path):
    for src in ("SkillAchievability.v", "check_assumptions.v"):
        (tmp_path / src).write_text((PROOF / src).read_text())
    r = subprocess.run(["coqc", "SkillAchievability.v"], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run(["coqc", "check_assumptions.v"], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    # the axiom audit prints "Closed under the global context" for each theorem
    assert r.stdout.count("Closed under the global context") >= 3, r.stdout


def test_direct_typing_proof_typechecks(tmp_path):
    """The direct T-Comm/T-Act/T-Goal discipline (no local types, no
    projection, no merge, no separate subtyping relation): deadlock-freedom
    (progress), preservation, and the mechanized planner/worker instance."""
    for src in ("SkillAchievability.v", "DirectTyping.v", "check_direct_typing.v"):
        (tmp_path / src).write_text((PROOF / src).read_text())
    r = subprocess.run(["coqc", "SkillAchievability.v"], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run(["coqc", "DirectTyping.v"], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run(["coqc", "check_direct_typing.v"], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("Closed under the global context") >= 7, r.stdout
