"""Deterministic front-end: SKILL.md / agent markdown  ->  achievability pack.

This is the *untrusted* half of the compiler pipeline (the checker is the
trusted half).  It compacts a natural-language skill into a formal pack in a
purely deterministic, inspectable way -- no LLM required:

  1. **Declared capabilities Γ** come from the environment profile plus the
     skill's own frontmatter (`allowed-tools` for Claude Code skills, `tools`
     for agent markdown), plus prose declarations of the corpus style
     ("Tools: a, b, c" / "Tools available: ...").
  2. **Invoked actions** are extracted from the prose: backticked identifiers
     governed by an invocation verb ("via `ask_user_input_v0`",
     "use `str_replace`", "call `save_skill`", ...).  Fenced code blocks are
     not scanned (their contents run through the shell capability).
  3. Identifiers are classified: declared tools and snake_case names act via
     their own capability; unix-ish commands, scripts, and undeclared
     CamelCase code symbols (`pdftotext`, `thumbnail.py`, `PositionalTab`)
     act via the profile's shell (`bash`) capability.
  4. The pack: one capability per granted tool establishing `used_<tool>`;
     the protocol is the ordered sequence of invoked acts; the goal is the
     conjunction of `used_<t>` over all invoked tools -- i.e. *the skill, as
     written, can actually be carried out in this environment*.

An author can bypass the heuristics entirely by embedding a precise pack in a
fenced block tagged `skillc-pack`; that JSON is validated and used verbatim
(this unlocks the full checker: guards, budgets, roles, choice/projection).

Soundness note (mirrors the paper's trust boundary): a misextraction here can
only make the checker judge *a different pack*; the verdict remains sound for
the pack actually produced, and the provenance report makes the pack
inspectable at one checkpoint.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

import yaml

from ..pack import PackError, validate_pack
from ..profiles import Profile, normalize_tool

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
FENCE_RE = re.compile(r"^(```+|~~~+)([^\n]*)\n(.*?)^\1\s*$\n?", re.S | re.M)
INVOKE_RE = re.compile(
    r"\b(?:via|use[sd]?|using|call(?:s|ed|ing)?|invoke[sd]?|invoking|run(?:s|ning)?|through)"
    r"\s+(?:the\s+)?`([A-Za-z][A-Za-z0-9_.:-]*)`",
    re.I,
)
TOOLS_LINE_RE = re.compile(
    r"^\s*(?:\*\*)?tools(?:\s+available)?(?:\*\*)?\s*:\s*(.+)$", re.I | re.M)

AGENT_TOOL_RE = re.compile(r"\A(?:[a-z][a-z0-9]*(?:_[a-z0-9]+)+|[A-Z][A-Za-z0-9]*)\Z")
SHELL_TOKEN_RE = re.compile(r"\A[a-z][a-z0-9+.-]*\Z")
# Matches a negation word ("not", "never") in the ~20 chars immediately
# before an invocation verb, used to skip "do NOT use `X`" false positives.
_NEGATION_BEFORE_VERB_RE = re.compile(r'\b(?:not|never)\b', re.I)

SHELL_CAP = "bash"
PACK_FENCE_TAG = "skillc-pack"


@dataclass
class Invocation:
    """One extracted tool use, with provenance for the inspection report."""
    raw: str            # identifier as written
    tool: str           # normalized capability it acts through
    kind: str           # "agent-tool" | "shell"
    line: int           # 1-based line in the source markdown


@dataclass
class CompileResult:
    pack: dict
    name: str
    profile: str
    declared: dict[str, str] = field(default_factory=dict)  # tool -> source
    invocations: list[Invocation] = field(default_factory=list)
    embedded: bool = False           # pack came from a ```skillc-pack block
    warnings: list[str] = field(default_factory=list)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from the body.  Tolerates malformed YAML."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    body = text[m.end():]
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}, body
    return (meta if isinstance(meta, dict) else {}), body


def _tool_list(value) -> list[str]:
    """Frontmatter tools value: comma-separated string or YAML list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [t.strip() for t in value.split(",") if t.strip()]
    if isinstance(value, list):
        return [str(t).strip() for t in value if str(t).strip()]
    return []


def _strip_fences(body: str) -> tuple[str, Optional[dict]]:
    """Blank out fenced code blocks (preserving line numbers) and pull out an
    embedded ``skillc-pack`` JSON block if present."""
    embedded: Optional[dict] = None

    def repl(m: re.Match) -> str:
        nonlocal embedded
        info = m.group(2).strip().lower()
        if PACK_FENCE_TAG in info.split() and embedded is None:
            try:
                embedded = json.loads(m.group(3))
            except json.JSONDecodeError as e:
                raise PackError(f"embedded skillc-pack block is not valid JSON: {e}")
        return "\n" * m.group(0).count("\n")

    return FENCE_RE.sub(repl, body), embedded


def _classify(raw: str) -> Optional[str]:
    """Classify an extracted identifier: 'agent-tool', 'shell', or None."""
    if ":" in raw:
        return None                      # XML-ish / namespaced code refs
    if "." in raw:
        # scripts and dotted method refs execute through a shell if at all
        return "shell"
    if AGENT_TOOL_RE.match(raw):
        return "agent-tool"
    if SHELL_TOKEN_RE.match(raw):
        return "shell"                   # unix-ish command: jq, pdftotext, ...
    return None


def extract(body: str, declared: set[str]) -> list[Invocation]:
    """Extract ordered tool invocations from prose (code fences pre-stripped)."""
    out: list[Invocation] = []
    for m in INVOKE_RE.finditer(body):
        # Skip negated invocations: "do NOT use `X`", "never call `X`", etc.
        prefix = body[max(0, m.start() - 20):m.start()]
        if _NEGATION_BEFORE_VERB_RE.search(prefix):
            continue
        raw = m.group(1)
        norm = normalize_tool(raw)
        line = body.count("\n", 0, m.start(1)) + 1
        if norm in declared:
            out.append(Invocation(raw, norm, "agent-tool", line))
            continue
        kind = _classify(raw)
        if kind == "agent-tool" and raw[0].isupper():
            # Unknown CamelCase is a code symbol (library class/API), not an
            # agent tool: it executes through the shell, if at all.  Declared
            # CamelCase tools (e.g. `WebFetch` under claude-code) were matched
            # against Γ above.
            kind = "shell"
        if kind == "agent-tool":
            out.append(Invocation(raw, norm, "agent-tool", line))
        elif kind == "shell":
            out.append(Invocation(raw, SHELL_CAP, "shell", line))
    return out


def compile_markdown(text: str, profile: Profile,
                     name: Optional[str] = None) -> CompileResult:
    """Compact a SKILL.md / agent markdown into an achievability pack."""
    meta, body = parse_frontmatter(text)
    skill_name = str(name or meta.get("name") or "skill")
    prose, embedded = _strip_fences(body)

    if embedded is not None:
        validate_pack(embedded)
        return CompileResult(pack=embedded, name=skill_name,
                             profile=profile.name, embedded=True)

    # --- capability context Γ -------------------------------------------
    declared: dict[str, str] = {}
    for t in sorted(profile.tools):
        declared[t] = f"profile:{profile.name}"
    for key in ("allowed-tools", "allowed_tools", "tools"):
        for t in _tool_list(meta.get(key)):
            declared[normalize_tool(t)] = f"frontmatter:{key}"
    for m in TOOLS_LINE_RE.finditer(prose):
        for t in m.group(1).rstrip(".").split(","):
            t = t.strip().strip("`")
            if t and re.match(r"\A[A-Za-z][A-Za-z0-9_-]*\Z", t):
                declared[normalize_tool(t)] = "prose:tools-line"

    warnings: list[str] = []
    if profile.shell and SHELL_CAP not in declared:
        declared[SHELL_CAP] = f"profile:{profile.name}(shell)"

    # --- invoked actions --------------------------------------------------
    invocations = extract(prose, set(declared))
    if not invocations:
        warnings.append("no tool invocations extracted; goal is trivially "
                        "achievable (the skill demands no tool actions)")

    # --- pack --------------------------------------------------------------
    def pred(tool: str) -> str:
        return "used_" + re.sub(r"[^a-z0-9_]", "_", tool)

    capabilities = {t: {"owner": "agent", "add": [pred(t)]}
                    for t in sorted(declared)}
    seen: list[str] = []
    protocol = []
    for inv in invocations:
        protocol.append({"act": {"cap": inv.tool, "by": "agent"}})
        if inv.tool not in seen:
            seen.append(inv.tool)
    goal_conjuncts = [pred(t) for t in seen]
    goal = {"and": goal_conjuncts} if goal_conjuncts else True

    pack = {
        "name": skill_name,
        "roles": ["agent"],
        "capabilities": capabilities,
        "protocol": protocol,
        "goal": goal,
        "init_true": [],
    }
    validate_pack(pack)
    return CompileResult(pack=pack, name=skill_name, profile=profile.name,
                         declared=declared, invocations=invocations,
                         warnings=warnings)


def compile_file(path, profile: Profile, name: Optional[str] = None) -> CompileResult:
    with open(path, encoding="utf-8") as fh:
        return compile_markdown(fh.read(), profile, name=name)
