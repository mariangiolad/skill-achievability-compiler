"""skillc command-line interface.

  skillc compile SKILL.md [--profile P] [-o pack.json]   markdown -> pack
  skillc check   FILE     [--profile P] [--json]         pack.json or SKILL.md -> verdict
  skillc scan    DIR      [--profile P] [--json|--md]    batch-check a skill tree
  skillc audit   PATH     [--json]                       bundle security pre-pass
  skillc eval                                            corpus evaluation
  skillc profiles                                        list capability profiles

Exit codes: 0 achievable / all pass, 1 impossible / soundness violation,
2 usage or input error, 3 unknown (outside the decidable fragment).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .checker import check
from .evaluate import evaluate, format_report, load_corpus
from .frontend.markdown import CompileResult, compile_file
from .pack import Pack, PackError
from .profiles import builtin_profiles, load_profile


def _load_result(path: Path, args) -> tuple[dict, CompileResult | None]:
    """Return (pack, compile_result_or_None) for a .json pack or markdown."""
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8")), None
    profile = load_profile(args.profile)
    if getattr(args, "tool", None):
        profile = profile.with_tools(args.tool)
    if getattr(args, "llm", False):
        from .frontend.llm import compact
        pack = compact(path.read_text(encoding="utf-8"), model=args.model)
        return pack, None
    res = compile_file(path, profile)
    return res.pack, res


def cmd_compile(args) -> int:
    pack, res = _load_result(Path(args.file), args)
    out = json.dumps(pack, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    if res is not None and not args.quiet:
        _print_provenance(res, file=sys.stderr)
    return 0


def _print_provenance(res: CompileResult, file=sys.stdout) -> None:
    if res.embedded:
        print("[embedded skillc-pack block used verbatim]", file=file)
        return
    fm = sorted(t for t, s in res.declared.items() if s.startswith("frontmatter"))
    pl = sorted(t for t, s in res.declared.items() if s.startswith("prose"))
    if fm:
        print(f"declared (frontmatter): {', '.join(fm)}", file=file)
    if pl:
        print(f"declared (prose):       {', '.join(pl)}", file=file)
    if res.invocations:
        print("invocations:", file=file)
        for inv in res.invocations:
            note = "" if inv.raw.lower() == inv.tool else f"  [{inv.raw} -> {inv.tool}]"
            print(f"  line {inv.line:>4}: {inv.tool} ({inv.kind}){note}", file=file)
    for w in res.warnings:
        print(f"warning: {w}", file=file)


def cmd_check(args) -> int:
    pack, res = _load_result(Path(args.file), args)
    v = check(pack, semantics="adversarial" if args.adversarial else "may")
    if args.json:
        out = v.to_dict()
        out["pack_name"] = pack.get("name", "?")
        print(json.dumps(out, indent=2))
    else:
        print(f"{pack.get('name', '?')}: {v.label}"
              + (f" [{v.reason}]" if not v.achievable else ""))
        if v.detail and not v.achievable:
            print(f"  {v.detail}")
        if res is not None and not v.achievable and v.reason == "MISSING_CAPABILITY":
            lines = {i.tool: i.line for i in reversed(res.invocations)}
            for capname in v.frontier:
                loc = f" (line {lines[capname]})" if capname in lines else ""
                print(f"  missing: {capname}{loc}")
        if args.verbose and v.achievable:
            print("  witness:", " -> ".join(f"{k}:{x}" for k, x in v.witness))
    if v.unknown:
        return 3
    return 0 if v.achievable else 1


def cmd_scan(args) -> int:
    root = Path(args.dir)
    files = sorted(root.rglob(args.glob))
    if not files:
        print(f"no files matching {args.glob!r} under {root}", file=sys.stderr)
        return 2
    rows = []
    for f in files:
        rel = f.relative_to(root)
        try:
            pack, _ = _load_result(f, args)
            v = check(pack)
            rows.append({"skill": str(rel), "verdict": v.label,
                         "reason": v.reason if not v.achievable else "",
                         "frontier": list(v.frontier)})
        except (PackError, ValueError) as e:
            rows.append({"skill": str(rel), "verdict": "ERROR",
                         "reason": type(e).__name__, "frontier": [str(e)]})
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        w = max(len(r["skill"]) for r in rows)
        for r in rows:
            extra = f"  {r['reason']} {r['frontier']}" if r["reason"] else ""
            print(f"{r['skill']:<{w}}  {r['verdict']}{extra}")
        n_ok = sum(r["verdict"] == "ACHIEVABLE" for r in rows)
        print(f"\n{n_ok}/{len(rows)} achievable under profile "
              f"'{args.profile}'")
    return 0


def cmd_audit(args) -> int:
    from .audit import audit_tree
    results = audit_tree(args.path)
    n_err = 0
    if args.json:
        print(json.dumps({b: [f.to_dict() for f in fs]
                          for b, fs in results.items()}, indent=2))
        n_err = sum(f.severity == "error" for fs in results.values() for f in fs)
    else:
        for bundle, findings in results.items():
            if not findings and not args.quiet:
                print(f"{bundle}: clean")
                continue
            for f in findings:
                loc = f":{f.line}" if f.line else ""
                print(f"{bundle}: {f.severity.upper()} [{f.code}] {f.message} "
                      f"({f.file}{loc})")
                n_err += f.severity == "error"
        n = len(results)
        print(f"\naudited {n} bundle{'s' if n != 1 else ''}, "
              f"{n_err} error-severity finding{'s' if n_err != 1 else ''}")
    return 1 if n_err else 0


def cmd_eval(args) -> int:
    corpus = load_corpus()
    res = evaluate(corpus)
    print(format_report(res, corpus))
    ok = res.sound and res.fp_all_spurious(corpus)
    return 0 if ok else 1


def cmd_profiles(args) -> int:
    for name in builtin_profiles():
        p = load_profile(name)
        print(f"{p.name:<12} {len(p.tools):>3} tools, shell={p.shell}  -- {p.description}")
    return 0


def _add_compile_opts(sp) -> None:
    sp.add_argument("--profile", default="claude-ai",
                    help="capability profile (built-in name or JSON path)")
    sp.add_argument("--tool", action="append", metavar="NAME",
                    help="grant an extra tool capability (repeatable)")
    sp.add_argument("--llm", action="store_true",
                    help="use the LLM compaction front-end (needs ANTHROPIC_API_KEY)")
    sp.add_argument("--model", default="claude-sonnet-5",
                    help="model for --llm compaction")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skillc",
                                 description="Skill Achievability Compiler")
    ap.add_argument("--version", action="version", version=f"skillc {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("compile", help="markdown -> achievability pack (JSON)")
    sp.add_argument("file")
    sp.add_argument("-o", "--output")
    sp.add_argument("-q", "--quiet", action="store_true")
    _add_compile_opts(sp)
    sp.set_defaults(fn=cmd_compile)

    sp = sub.add_parser("check", help="decide achievability of a pack or SKILL.md")
    sp.add_argument("file")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("-v", "--verbose", action="store_true")
    sp.add_argument("--adversarial", action="store_true",
                    help="require the goal under EVERY resolution of choices "
                         "marked external (must-achievability)")
    _add_compile_opts(sp)
    sp.set_defaults(fn=cmd_check)

    sp = sub.add_parser("scan", help="batch-check every skill under a directory")
    sp.add_argument("dir")
    sp.add_argument("--glob", default="SKILL.md")
    sp.add_argument("--json", action="store_true")
    _add_compile_opts(sp)
    sp.set_defaults(fn=cmd_scan)

    sp = sub.add_parser("audit",
                        help="skill-bundle security pre-pass (SkillSpector-like)")
    sp.add_argument("path")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("-q", "--quiet", action="store_true",
                    help="omit clean bundles from the listing")
    sp.set_defaults(fn=cmd_audit)

    sp = sub.add_parser("eval", help="run the corpus evaluation")
    sp.set_defaults(fn=cmd_eval)

    sp = sub.add_parser("profiles", help="list built-in capability profiles")
    sp.set_defaults(fn=cmd_profiles)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except (PackError, KeyError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"skillc: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
