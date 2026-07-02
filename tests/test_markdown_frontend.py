from pathlib import Path

import pytest

from skillc import check, compile_file, compile_markdown, load_profile
from skillc.frontend.markdown import parse_frontmatter
from skillc.pack import PackError

FIXTURES = Path(__file__).parent / "fixtures"

CLAUDE_AI = load_profile("claude-ai")
CLAUDE_CODE = load_profile("claude-code")
NONE = load_profile("none")


# ---------------------------------------------------------------- frontmatter

def test_parse_frontmatter():
    meta, body = parse_frontmatter("---\nname: x\ntools: A, B\n---\nbody")
    assert meta == {"name": "x", "tools": "A, B"}
    assert body == "body"


def test_no_frontmatter():
    meta, body = parse_frontmatter("# just markdown")
    assert meta == {} and body == "# just markdown"


def test_malformed_frontmatter_tolerated():
    meta, body = parse_frontmatter("---\n: : :\n\t bad\n---\nbody")
    assert meta == {} and body == "body"


# ---------------------------------------------------------------- extraction

def test_invocation_verbs_and_ordering():
    md = ("Ask the user via `ask_user_input_v0`. Then use `str_replace` to "
          "edit. Finally call `save_skill`.")
    res = compile_markdown(md, CLAUDE_AI)
    assert [i.tool for i in res.invocations] == [
        "ask_user_input_v0", "str_replace", "save_skill"]
    assert all(i.kind == "agent-tool" for i in res.invocations)


def test_backtick_mention_without_verb_is_not_an_invocation():
    md = "The JSON output has a `best_description` field."
    res = compile_markdown(md, CLAUDE_AI)
    assert res.invocations == []
    assert check(res.pack).achievable          # trivially: no demands


def test_negated_invocation_is_not_extracted():
    """'Do NOT use `X`' and '**not** use `X`' must not be treated as invocations."""
    md = ("# s\n"
          "Do NOT use `some_tool_v1` for new code.\n"
          "Do **not** use `other_tool_v2` here.\n"
          "Never call `yet_another_tool`.\n"
          "Instead use `ask_user_input_v0` for this.")
    res = compile_markdown(md, CLAUDE_AI)
    extracted = [i.raw for i in res.invocations]
    assert "some_tool_v1" not in extracted
    assert "other_tool_v2" not in extracted
    assert "yet_another_tool" not in extracted
    assert "ask_user_input_v0" in extracted
    assert check(res.pack).achievable


def test_shell_commands_route_through_bash():
    md = "Convert using `pdftotext`, then run `thumbnail.py` on the output."
    res = compile_markdown(md, CLAUDE_AI)
    assert [i.tool for i in res.invocations] == ["bash", "bash"]
    assert all(i.kind == "shell" for i in res.invocations)
    assert check(res.pack).achievable


def test_unknown_camelcase_is_a_code_symbol_not_a_tool():
    md = "Use `PositionalTab` for dot leaders."
    res = compile_markdown(md, CLAUDE_AI)
    assert [i.tool for i in res.invocations] == ["bash"]


def test_declared_camelcase_is_a_tool():
    md = "Fetch the page using `WebFetch`."
    res = compile_markdown(md, CLAUDE_CODE)
    assert [(i.tool, i.kind) for i in res.invocations] == [
        ("webfetch", "agent-tool")]
    assert check(res.pack).achievable


def test_code_fences_are_not_scanned():
    md = "Run the setup.\n```python\n# use `fake_tool_x` here\n```\nDone."
    res = compile_markdown(md, CLAUDE_AI)
    assert res.invocations == []


def test_line_numbers_survive_fence_stripping():
    md = "intro\n```\nx\ny\n```\nnow use `ask_user_input_v0` here"
    res = compile_markdown(md, CLAUDE_AI)
    assert res.invocations[0].line == 6


def test_namespaced_code_refs_ignored():
    md = "Set the attribute via `w:id` in the XML."
    res = compile_markdown(md, CLAUDE_AI)
    assert res.invocations == []


# ------------------------------------------------------- capability context Γ

def test_frontmatter_allowed_tools_with_qualifiers():
    md = ("---\nname: t\nallowed-tools: Bash(git:*), Read, mcp__jira__create\n"
          "---\nUse `Read` then use `mcp__jira__create`.")
    res = compile_markdown(md, NONE)
    assert res.declared["bash"] == "frontmatter:allowed-tools"
    assert res.declared["read"] == "frontmatter:allowed-tools"
    assert check(res.pack).achievable


def test_prose_tools_line_declares_capabilities():
    md = ("# Skill: refund\nTools: lookup_order, issue_refund.\n"
          "First use `lookup_order`, then use `issue_refund`.")
    res = compile_markdown(md, NONE)
    assert res.declared["lookup_order"] == "prose:tools-line"
    assert check(res.pack).achievable


def test_undeclared_snake_case_tool_is_refuted():
    md = "# s\nSend it via `send_email_v2`."
    res = compile_markdown(md, CLAUDE_AI)
    v = check(res.pack)
    assert not v.achievable
    assert v.reason == "MISSING_CAPABILITY"
    assert v.frontier == ("send_email_v2",)


def test_profile_relativity_same_skill_two_verdicts():
    """The heart of the design: achievability is judged relative to Γ."""
    md = "# s\nAsk via `ask_user_input_v0`, then proceed."
    ok = check(compile_markdown(md, CLAUDE_AI).pack)
    bad = check(compile_markdown(md, CLAUDE_CODE).pack)
    assert ok.achievable
    assert not bad.achievable and bad.reason == "MISSING_CAPABILITY"


def test_extra_tools_widen_the_context():
    md = "# s\nCall `deploy_service` now."
    assert not check(compile_markdown(md, CLAUDE_AI).pack).achievable
    widened = CLAUDE_AI.with_tools(["deploy_service"])
    assert check(compile_markdown(md, widened).pack).achievable


def test_shell_needs_a_shell_granting_profile():
    md = "# s\nRun `pdftotext` on the file."
    v = check(compile_markdown(md, NONE).pack)
    assert not v.achievable and v.frontier == ("bash",)


# ------------------------------------------------------------------ fixtures

def test_fixture_changelog_writer_achievable_under_claude_code():
    res = compile_file(FIXTURES / "changelog-writer/SKILL.md", CLAUDE_CODE)
    assert not res.embedded
    v = check(res.pack)
    assert v.achievable


def test_fixture_hallucinated_mailer_refuted_everywhere():
    for profile in (CLAUDE_AI, CLAUDE_CODE):
        res = compile_file(FIXTURES / "hallucinated-mailer/SKILL.md", profile)
        v = check(res.pack)
        assert not v.achievable
        assert v.reason == "MISSING_CAPABILITY"
        assert "send_email_v2" in v.frontier


def test_fixture_embedded_pack_used_verbatim():
    res = compile_file(FIXTURES / "embedded-pack/SKILL.md", CLAUDE_AI)
    assert res.embedded
    assert res.pack["name"] == "embedded-pack"
    v = check(res.pack)
    assert v.achievable          # z3 finds a price < 500


def test_embedded_pack_invalid_json_rejected():
    md = "# s\n```skillc-pack\n{not json\n```\n"
    with pytest.raises(PackError):
        compile_markdown(md, CLAUDE_AI)


def test_no_invocations_warns_and_is_trivially_achievable():
    res = compile_markdown("# pure prose skill\nBe kind.", CLAUDE_AI)
    assert res.warnings
    assert check(res.pack).achievable
