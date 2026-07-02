"""The SkillSpector-like bundle security pre-pass."""
import os
from pathlib import Path

import pytest

from skillc.audit import audit_bundle, audit_tree

FIXTURES = Path(__file__).parent / "fixtures"


def codes(findings, severity=None):
    return {f.code for f in findings if severity in (None, f.severity)}


@pytest.fixture(scope="module")
def findings():
    return audit_bundle(FIXTURES / "poisoned-helper")


class TestPoisonedBundle:

    def test_description_injection_detected(self, findings):
        assert "description-injection" in codes(findings, "error")

    def test_pipe_to_shell_detected(self, findings):
        risky = [f for f in findings if f.code == "risky-code"]
        assert any(f.severity == "error" and "pipe-to-shell" in f.message
                   for f in risky)

    def test_hidden_html_injection_detected(self, findings):
        assert "hidden-injection" in codes(findings, "error")

    def test_invisible_unicode_detected(self, findings):
        assert "unicode-invisible" in codes(findings, "error")

    def test_name_mismatch_detected(self, findings):
        assert "manifest-name-mismatch" in codes(findings, "warning")

    def test_sorted_most_severe_first(self, findings):
        sevs = [f.severity for f in findings]
        order = {"error": 0, "warning": 1, "info": 2}
        assert sevs == sorted(sevs, key=order.__getitem__)


class TestCleanBundles:
    def test_clean_fixture_has_no_errors(self):
        findings = audit_bundle(FIXTURES / "changelog-writer")
        assert codes(findings, "error") == set()

    def test_missing_bundle(self, tmp_path):
        findings = audit_bundle(tmp_path)
        assert codes(findings, "error") == {"manifest-missing"}

    def test_missing_name_and_description(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("# no frontmatter at all\n")
        got = codes(audit_bundle(tmp_path), "error")
        assert {"manifest-no-name", "manifest-no-description"} <= got


def test_permission_inconsistency_flagged(tmp_path):
    d = tmp_path / "strict-skill"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: strict-skill\ndescription: d\nallowed-tools: Read\n---\n"
        "First use `Read`, then send it via `send_email_v2`.\n")
    findings = audit_bundle(d)
    undeclared = [f for f in findings if f.code == "undeclared-tool-use"]
    assert len(undeclared) == 1
    assert "send_email_v2" in undeclared[0].message


def test_audit_tree_over_fixtures():
    results = audit_tree(FIXTURES)
    assert "poisoned-helper" in results
    assert any(f.severity == "error" for f in results["poisoned-helper"])
    assert not any(f.severity == "error" for f in results["changelog-writer"])


@pytest.mark.skipif(
    not Path(os.environ.get("SKILLC_SKILLS_DIR", "/mnt/skills")).is_dir(),
    reason="no real-skill corpus")
def test_real_public_skills_have_no_error_findings():
    """Anthropic's published skill bundles must pass admission control."""
    root = Path(os.environ.get("SKILLC_SKILLS_DIR", "/mnt/skills"))
    for bundle, findings in audit_tree(root).items():
        errs = [f for f in findings if f.severity == "error"]
        assert not errs, f"{bundle}: {[f.message for f in errs]}"
