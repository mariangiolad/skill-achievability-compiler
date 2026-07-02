#!/usr/bin/env python3
"""Fetch a real-skill corpus: SKILL.md files from Anthropic's public skills
repository (https://github.com/anthropics/skills).

Tries the repo tarball first; if that endpoint is unreachable (some proxies
allow only raw.githubusercontent.com), falls back to fetching the manifest of
known skill paths file-by-file from raw.githubusercontent.com.

Usage:  python3 scripts/fetch_skills.py [DEST]           (default: ./real-skills)
Then:   SKILLC_SKILLS_DIR=./real-skills pytest tests/test_real_skills.py
        skillc scan ./real-skills --profile claude-ai
"""
import io
import os
import sys
import tarfile
import urllib.error
import urllib.request

REPO = "anthropics/skills"
TARBALL = f"https://codeload.github.com/{REPO}/tar.gz/refs/heads/main"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"

# Skill directories in anthropics/skills@main (fallback manifest).
MANIFEST = [
    "skills/algorithmic-art", "skills/brand-guidelines",
    "skills/canvas-design", "skills/doc-coauthoring",
    "skills/docx", "skills/frontend-design", "skills/internal-comms",
    "skills/mcp-builder", "skills/pdf", "skills/pptx",
    "skills/skill-creator", "skills/slack-gif-creator",
    "skills/theme-factory", "skills/web-artifacts-builder",
    "skills/webapp-testing", "skills/xlsx",
]


def _write(dest: str, rel: str, data: bytes) -> None:
    out = os.path.join(dest, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as o:
        o.write(data)


def fetch_tarball(dest: str) -> int:
    with urllib.request.urlopen(TARBALL, timeout=120) as r:
        data = r.read()
    n = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            if m.isfile() and m.name.endswith("SKILL.md"):
                fh = tf.extractfile(m)
                assert fh is not None
                _write(dest, m.name.split("/", 1)[1], fh.read())
                n += 1
    return n


def fetch_manifest(dest: str) -> int:
    n = 0
    for d in MANIFEST:
        url = f"{RAW}/{d}/SKILL.md"
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                _write(dest, f"{d}/SKILL.md", r.read())
                n += 1
                print(f"  {d}/SKILL.md")
        except urllib.error.HTTPError as e:
            print(f"  SKIP {d}: HTTP {e.code}", file=sys.stderr)
    return n


def main() -> int:
    dest = sys.argv[1] if len(sys.argv) > 1 else "real-skills"
    try:
        print(f"fetching {TARBALL} ...")
        n = fetch_tarball(dest)
    except (urllib.error.URLError, OSError) as e:
        print(f"tarball unavailable ({e}); falling back to {RAW}")
        n = fetch_manifest(dest)
    print(f"wrote {n} SKILL.md files under {dest}/")
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
