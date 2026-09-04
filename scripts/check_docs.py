#!/usr/bin/env python3
"""Catch documentation that drifts away from the code.

check.sh section 6 validates markdown link syntax. It cannot see a path written
in backticks, which is how `skills/<old-name>/SKILL.md` survived a rename and
shipped as a dead reference. This closes that gap and two related ones.
"""

import pathlib
import re
import sys

REFERENCE = re.compile(r'`((?:skills|context|adscooking|tests|scripts)/[A-Za-z0-9_./-]+)`')
problems = []

for path in sorted(pathlib.Path(".").rglob("*.md")):
    if ".git" in path.parts:
        continue
    for reference in sorted(set(REFERENCE.findall(path.read_text()))):
        if not pathlib.Path(reference).exists():
            problems.append(f"{path} refers to {reference}, which does not exist")

skills = sorted(p for p in pathlib.Path("skills").iterdir() if p.is_dir())

# A skill nobody documents is a skill nobody runs.
readme = pathlib.Path("README.md").read_text()
for skill in skills:
    if f"/ads-cooking:{skill.name}" not in readme:
        problems.append(f"skills/{skill.name} exists but README.md does not document it")

# The frontmatter name is the command name. If it drifts from the folder, the
# command is not the one the docs promise.
for skill in skills:
    declared = re.search(r'^name:\s*(\S+)', (skill / "SKILL.md").read_text(), re.M)
    found = declared.group(1) if declared else None
    if found != skill.name:
        problems.append(f"skills/{skill.name}/SKILL.md declares name: {found}")

# Commands the docs promise must exist as skills.
promised = set()
for path in (pathlib.Path(p) for p in ("README.md", "AGENTS.md", "CLAUDE.md", "CODEX.md")):
    promised |= set(re.findall(r'/ads-cooking:([a-z-]+)', path.read_text()))
for command in sorted(promised - {s.name for s in skills}):
    problems.append(f"docs promise /ads-cooking:{command} but there is no such skill")

for problem in problems:
    print(f"   FAIL {problem}")
if not problems:
    print(f"   OK   {len(skills)} skills, names match folders, all documented, no dead paths")
sys.exit(1 if problems else 0)
