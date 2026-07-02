#!/usr/bin/env python3
"""Generate docs/REAL_SKILLS_REPORT.md: verdicts for every real public skill
under each capability profile.

Usage: python3 scripts/make_report.py [SKILLS_DIR]   (default: /mnt/skills)
"""
import sys
from pathlib import Path

from skillc import __version__, check, compile_file, load_profile

PROFILES = ["claude-ai", "claude-code"]


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/skills")
    files = sorted(root.rglob("SKILL.md"))
    if not files:
        print(f"no SKILL.md under {root}", file=sys.stderr)
        return 2
    profiles = {n: load_profile(n) for n in PROFILES}
    lines = [
        "# Real-skill scan report",
        "",
        f"`skillc {__version__}` run over the public skills corpus "
        f"([anthropics/skills](https://github.com/anthropics/skills)): "
        f"{len(files)} `SKILL.md` files, checked under each capability "
        "profile.  Regenerate with `python3 scripts/make_report.py <dir>`.",
        "",
        "A verdict is always *relative to a capability context*: "
        "`IMPOSSIBLE [MISSING_CAPABILITY]` means the skill's instructions "
        "invoke a tool that this runtime does not grant -- the skill cannot "
        "be carried out as written there.  It is not a defect of the skill.",
        "",
        "| skill | " + " | ".join(PROFILES) + " |",
        "|---|" + "---|" * len(PROFILES),
    ]
    stats = {n: 0 for n in PROFILES}
    for f in files:
        rel = f.relative_to(root).parent
        cells = []
        for n in PROFILES:
            v = check(compile_file(f, profiles[n]).pack)
            if v.achievable:
                stats[n] += 1
                cells.append("ACHIEVABLE")
            else:
                missing = ", ".join(f"`{x}`" for x in v.frontier)
                cells.append(f"IMPOSSIBLE ({missing})")
        lines.append(f"| `{rel}` | " + " | ".join(cells) + " |")
    lines += ["",
              "**Totals:** " + ", ".join(
                  f"{stats[n]}/{len(files)} achievable under `{n}`"
                  for n in PROFILES),
              ""]
    out = Path(__file__).parent.parent / "docs" / "REAL_SKILLS_REPORT.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} ({len(files)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
