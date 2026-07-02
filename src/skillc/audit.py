"""Skill-bundle security audit: the SkillSpector-like pre-pass.

The paper's practical-compiler recommendation: before the formal pack is
trusted by the achievability checker, a deterministic scanner should vet the
incoming bundle -- SKILL.md, scripts, dependencies, manifests, and permission
metadata.  This module is that admission-control pass.  It is *complementary*
to the type discipline: it asks "should this bundle be admitted at all?",
not "is the goal achievable?".

Deterministic checks (no LLM):
  * manifest consistency  -- SKILL.md present; frontmatter has name and
    description; the name matches the bundle directory; sane name shape and
    description length.
  * metadata poisoning    -- invisible/bidirectional Unicode in the skill
    text; instruction-injection patterns in the description or hidden inside
    HTML comments.
  * risky code patterns   -- pipe-to-shell installs, decode-and-execute,
    destructive commands, plaintext-HTTP fetches, in fenced code blocks and
    bundle scripts.
  * permission consistency-- when the frontmatter declares `allowed-tools`,
    every agent-tool invocation extracted from the prose must be covered.

Severities: "error" (reject/deep-review), "warning" (review), "info" (note).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .frontend.markdown import (FENCE_RE, extract, parse_frontmatter,
                                _strip_fences, _tool_list)
from .pack import PackError
from .profiles import normalize_tool

SCRIPT_SUFFIXES = {".sh", ".bash", ".py", ".js", ".ts", ".rb", ".pl"}

INVISIBLE_RE = re.compile(  # zero-width, word-joiner, BOM, bidi controls
    "[​-‏⁠-⁤﻿‪-‮⁦-⁩]")
HTML_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)
INJECTION_RE = re.compile(
    r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above)\s+instructions"
    r"|disregard\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions)"
    r"|do\s+not\s+(?:tell|inform|alert|notify)\s+the\s+user"
    r"|without\s+(?:telling|informing|asking)\s+the\s+user"
    r"|exfiltrat", re.I)
RISKY_CODE = [
    ("error", re.compile(r"\brm\s+-rf\s+/(?:\s|$|['\"])"), "destructive: rm -rf /"),
    ("error", re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b"),
     "pipe-to-shell install"),
    ("error", re.compile(r"base64\s+(?:-d|--decode)[^\n|]*\|\s*(?:ba|z|da)?sh\b"),
     "decode-and-execute"),
    ("warning", re.compile(r"\beval\s*\("), "dynamic eval()"),
    ("warning", re.compile(r"\bchmod\s+777\b"), "world-writable chmod"),
    ("info", re.compile(r"\bhttp://(?!localhost|127\.0\.0\.1)[\w.-]+"),
     "plaintext-HTTP URL"),
]
NAME_RE = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
MAX_DESCRIPTION = 1024


@dataclass
class Finding:
    severity: str            # "error" | "warning" | "info"
    code: str
    message: str
    file: str
    line: int = 0

    def to_dict(self) -> dict:
        return {"severity": self.severity, "code": self.code,
                "message": self.message, "file": self.file, "line": self.line}


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def audit_bundle(path: str | Path) -> list[Finding]:
    """Audit one skill bundle (a directory containing SKILL.md, or a SKILL.md
    path).  Returns findings sorted most-severe first."""
    path = Path(path)
    if path.is_dir():
        bundle, skill_md = path, path / "SKILL.md"
    else:
        bundle, skill_md = path.parent, path
    out: list[Finding] = []
    rel = str(skill_md)

    if not skill_md.is_file():
        return [Finding("error", "manifest-missing",
                        f"no SKILL.md found in bundle {bundle}", str(bundle))]
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(text)

    # ---- manifest consistency ------------------------------------------
    name = meta.get("name")
    if not name:
        out.append(Finding("error", "manifest-no-name",
                           "frontmatter is missing 'name'", rel))
    else:
        if not NAME_RE.match(str(name)):
            out.append(Finding("warning", "manifest-name-shape",
                               f"name {name!r} is not lower-kebab-case", rel))
        if bundle.name not in (str(name), f"{name}.skill"):
            out.append(Finding("warning", "manifest-name-mismatch",
                               f"name {name!r} does not match bundle "
                               f"directory {bundle.name!r}", rel))
    desc = meta.get("description")
    if not desc:
        out.append(Finding("error", "manifest-no-description",
                           "frontmatter is missing 'description'", rel))
    elif len(str(desc)) > MAX_DESCRIPTION:
        out.append(Finding("warning", "manifest-description-length",
                           f"description is {len(str(desc))} chars "
                           f"(> {MAX_DESCRIPTION})", rel))

    # ---- metadata poisoning ---------------------------------------------
    for m in INVISIBLE_RE.finditer(text):
        out.append(Finding("error", "unicode-invisible",
                           f"invisible/bidi character U+{ord(m.group(0)):04X}",
                           rel, _line_of(text, m.start())))
    if desc and INJECTION_RE.search(str(desc)):
        out.append(Finding("error", "description-injection",
                           "instruction-injection pattern in the description "
                           "(metadata poisoning)", rel))
    for m in HTML_COMMENT_RE.finditer(body):
        sev, code = "info", "hidden-html-comment"
        msg = "HTML comment (hidden-content channel)"
        if INJECTION_RE.search(m.group(1)):
            sev, code = "error", "hidden-injection"
            msg = "instruction-injection pattern hidden in an HTML comment"
        out.append(Finding(sev, code, msg, rel, _line_of(body, m.start())))
    if INJECTION_RE.search(body):
        pos = INJECTION_RE.search(body).start()
        out.append(Finding("warning", "body-injection-pattern",
                           "instruction-injection-like phrase in the skill "
                           "body", rel, _line_of(body, pos)))

    # ---- risky code patterns ---------------------------------------------
    for m in FENCE_RE.finditer(body):
        _scan_code(m.group(3), rel, _line_of(body, m.start(3)), out)
    for script in sorted(bundle.rglob("*")):
        if script.suffix in SCRIPT_SUFFIXES and script.is_file():
            _scan_code(script.read_text(encoding="utf-8", errors="replace"),
                       str(script), 1, out)

    # ---- permission consistency ------------------------------------------
    declared_raw = None
    for key in ("allowed-tools", "allowed_tools", "tools"):
        if meta.get(key) is not None:
            declared_raw = _tool_list(meta.get(key))
            break
    if declared_raw is not None:
        declared = {normalize_tool(t) for t in declared_raw}
        try:
            prose, _ = _strip_fences(body)
        except PackError:
            prose = body
        for inv in extract(prose, declared):
            if inv.kind == "agent-tool" and inv.tool not in declared:
                out.append(Finding(
                    "warning", "undeclared-tool-use",
                    f"prose invokes `{inv.raw}` but frontmatter allowed-tools "
                    f"does not declare it (permission-metadata inconsistency)",
                    rel, inv.line))

    order = {"error": 0, "warning": 1, "info": 2}
    out.sort(key=lambda f: (order[f.severity], f.file, f.line))
    return out


def _scan_code(code: str, file: str, base_line: int, out: list[Finding]) -> None:
    for sev, rx, label in RISKY_CODE:
        for m in rx.finditer(code):
            out.append(Finding(sev, "risky-code", label, file,
                               base_line + code.count("\n", 0, m.start())))


def audit_tree(root: str | Path) -> dict[str, list[Finding]]:
    """Audit every bundle under a directory tree (bundle = dir of SKILL.md)."""
    root = Path(root)
    if (root / "SKILL.md").is_file():
        return {str(root): audit_bundle(root)}
    return {str(p.parent.relative_to(root)): audit_bundle(p.parent)
            for p in sorted(root.rglob("SKILL.md"))}
