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

# The layout tables go stale the moment a file is added or renamed. Every
# shipped module and every skill has to appear in README.md by name.
readme_text = pathlib.Path("README.md").read_text()
for module in sorted(pathlib.Path("adscooking").glob("*.py")):
    if module.name == "__init__.py":
        continue
    if f"adscooking/{module.name}" not in readme_text:
        problems.append(f"adscooking/{module.name} exists but README.md never mentions it")
for helper in sorted(pathlib.Path("scripts").iterdir()):
    if helper.name not in readme_text:
        problems.append(f"scripts/{helper.name} exists but README.md never mentions it")

# And a path the README names must exist.
for reference in sorted(set(re.findall(
        r'`((?:adscooking|skills|context|tests|scripts)/[A-Za-z0-9_./-]+)`', readme_text))):
    if not pathlib.Path(reference).exists():
        problems.append(f"README.md names {reference}, which does not exist")

# The test count in the docs has to be the real one.
import subprocess
result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                        capture_output=True, text=True)
actual = re.search(r"Ran (\d+) tests", result.stderr)
if actual:
    for doc in ("README.md", "AGENTS.md", "CODEX.md"):
        for claimed in set(re.findall(r"(\d+) tests", pathlib.Path(doc).read_text())):
            if claimed != actual.group(1):
                problems.append(f"{doc} says {claimed} tests; there are {actual.group(1)}")

for problem in problems:
    print(f"   FAIL {problem}")
if not problems:
    print(f"   OK   {len(skills)} skills, names match folders, all documented, no dead paths")
sys.exit(1 if problems else 0)
