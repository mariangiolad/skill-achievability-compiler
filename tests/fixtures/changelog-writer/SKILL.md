---
name: changelog-writer
description: Draft a changelog entry from the current git diff and save it to CHANGELOG.md.
allowed-tools: Bash(git:*), Read, Write
---

# Changelog writer

You are helping the user write a changelog entry.

1. Inspect the pending changes: run `git` via the shell to get the diff, and
   read the existing entries using `Read`.
2. Draft a concise entry in the repository's established style.
3. Persist it with `Write` at the top of `CHANGELOG.md`.
