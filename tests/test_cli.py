import json
from pathlib import Path

from skillc.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_check_achievable_exit_0(capsys):
    rc = main(["check", str(FIXTURES / "changelog-writer/SKILL.md"),
               "--profile", "claude-code"])
    assert rc == 0
    assert "ACHIEVABLE" in capsys.readouterr().out


def test_check_impossible_exit_1(capsys):
    rc = main(["check", str(FIXTURES / "hallucinated-mailer/SKILL.md"),
               "--profile", "claude-ai"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "MISSING_CAPABILITY" in out and "send_email_v2" in out


def test_check_json_output(capsys):
    rc = main(["check", "--json", str(FIXTURES / "hallucinated-mailer/SKILL.md")])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == "IMPOSSIBLE"
    assert "send_email_v2" in data["frontier"]


def test_compile_writes_pack(tmp_path, capsys):
    out = tmp_path / "pack.json"
    rc = main(["compile", str(FIXTURES / "embedded-pack/SKILL.md"),
               "-o", str(out), "-q"])
    assert rc == 0
    pack = json.loads(out.read_text())
    assert pack["name"] == "embedded-pack"


def test_check_a_compiled_pack_json(tmp_path, capsys):
    out = tmp_path / "pack.json"
    main(["compile", str(FIXTURES / "changelog-writer/SKILL.md"),
          "--profile", "claude-code", "-o", str(out), "-q"])
    rc = main(["check", str(out)])
    assert rc == 0


def test_scan_directory_json(capsys):
    rc = main(["scan", str(FIXTURES), "--json", "--profile", "claude-code"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    by_name = {r["skill"]: r for r in rows}
    assert by_name["changelog-writer/SKILL.md"]["verdict"] == "ACHIEVABLE"
    assert by_name["hallucinated-mailer/SKILL.md"]["verdict"] == "IMPOSSIBLE"


def test_check_unknown_exit_3(tmp_path, capsys):
    pack = {"name": "spawner", "capabilities": {},
            "protocol": [{"spawn": {"role": "helper"}}], "goal": True}
    p = tmp_path / "pack.json"
    p.write_text(json.dumps(pack))
    rc = main(["check", str(p)])
    assert rc == 3
    assert "UNKNOWN" in capsys.readouterr().out


def test_examples_check_out(capsys):
    root = Path(__file__).parent.parent / "examples"
    for skill in sorted(root.rglob("SKILL.md")):
        assert main(["check", str(skill)]) == 0, skill


def test_audit_poisoned_exit_1(capsys):
    rc = main(["audit", str(FIXTURES / "poisoned-helper")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "description-injection" in out


def test_audit_clean_exit_0(capsys):
    rc = main(["audit", str(FIXTURES / "changelog-writer")])
    assert rc == 0


def test_audit_json(capsys):
    rc = main(["audit", "--json", str(FIXTURES / "poisoned-helper")])
    assert rc == 1
    data = json.loads(capsys.readouterr().out)
    (findings,) = data.values()
    assert any(f["code"] == "unicode-invisible" for f in findings)


def test_eval_passes(capsys):
    rc = main(["eval"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "FN=0" in out and "PASS" in out


def test_profiles_listed(capsys):
    rc = main(["profiles"])
    assert rc == 0
    out = capsys.readouterr().out
    for name in ("claude-ai", "claude-code", "none"):
        assert name in out


def test_error_exit_2(capsys):
    rc = main(["check", "no-such-file.json"])
    assert rc == 2
