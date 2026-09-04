#!/usr/bin/env bash
# Pre-push gate. Run from the repo root: ./scripts/check.sh
#
# Local on purpose, not a GitHub Actions workflow: this repo has no CI budget
# and the whole suite runs in well under a second.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
section() { echo; echo "== $1"; }

section "1. Tests"
if python3 -m unittest discover -s tests -t . >/tmp/adscooking-tests.log 2>&1; then
  echo "   OK   $(grep -oE 'Ran [0-9]+ tests' /tmp/adscooking-tests.log) passed"
else
  echo "   FAIL"; sed 's/^/        /' /tmp/adscooking-tests.log | tail -30; fail=1
fi

section "2. JSON syntax"
while IFS= read -r f; do
  if python3 -c "import json,sys;json.load(open('$f'))" 2>/dev/null; then
    echo "   OK   $f"
  else
    echo "   FAIL $f"; fail=1
  fi
done < <(find . -name '*.json' -not -path './.git/*' -not -path './ads-cooking/*')

section "3. Plugin manifest (strict)"
if command -v claude >/dev/null 2>&1; then
  out=$(claude plugin validate . --strict 2>&1)
  if grep -q 'Validation passed' <<<"$out"; then echo "   OK"
  else echo "   FAIL"; sed 's/^/        /' <<<"$out"; fail=1; fi
else
  echo "   SKIP claude CLI not on PATH"
fi

section "4. Every SKILL.md has name + description frontmatter"
while IFS= read -r f; do
  if head -1 "$f" | grep -q '^---$' && grep -q '^name:' "$f" && grep -q '^description:' "$f"; then
    echo "   OK   $f"
  else echo "   FAIL $f"; fail=1; fi
done < <(find skills -name SKILL.md | sort)

section "5. Skills use the one documented command form"
# Every runnable example must be PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking ...
# A bare `python3 -m adscooking` in a skill fails for anyone not sitting in the repo.
bare=$(grep -rn '^python3 -m adscooking' skills/ 2>/dev/null || true)
if [ -n "$bare" ]; then
  echo "   FAIL a skill has a command without PYTHONPATH:"; sed 's/^/        /' <<<"$bare"; fail=1
else
  echo "   OK   all $(grep -rc 'PYTHONPATH' skills/*/SKILL.md | grep -c ':[1-9]') skills use it"
fi

section "6. Internal links resolve"
python3 - <<'PY' || fail=1
import pathlib, re, sys
bad = 0
root = pathlib.Path(".")
for f in sorted(root.rglob("*.md")):
    if ".git" in f.parts: continue
    for target in re.findall(r'\]\(([^)#:]+?\.(?:md|json|py))\)', f.read_text()):
        if not (f.parent / target).exists():
            print(f"   FAIL {f} -> {target}"); bad += 1
print("   OK   all internal links resolve" if not bad else f"   {bad} broken")
sys.exit(1 if bad else 0)
PY

section "7. No secrets"
# Meta system-user tokens start with EAA and run to a few hundred characters.
if grep -rIn --exclude-dir=.git --exclude-dir=scripts -E '\bEAA[A-Za-z0-9]{40,}' . ; then
  echo "   FAIL something shaped like a Meta token is committed"; fail=1
else
  echo "   OK   no token-shaped strings"
fi
if [ -f .env ] || [ -d ads-cooking ]; then
  if git check-ignore -q .env ads-cooking 2>/dev/null; then
    echo "   OK   local config is gitignored"
  else
    echo "   FAIL a local .env or ads-cooking/ is NOT gitignored"; fail=1
  fi
fi
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --redact --exit-code 1 >/dev/null 2>&1 \
    && echo "   OK   gitleaks clean" || { echo "   FAIL gitleaks findings"; fail=1; }
else
  echo "   SKIP gitleaks not installed (brew install gitleaks)"
fi

section "8. Nothing identifying from the account this was built on"
# This repo is public and was extracted from work done on a real ad account.
# The terms live in .denylist, which is gitignored: a list of former clients is
# itself identifying data, so committing it would make this check the leak it
# exists to prevent. Note there is no --exclude-dir=scripts here; this section
# scans itself.
if [ -f .denylist ]; then
  # --exclude=.denylist so the term list does not match itself. Everything else,
  # including this script, is in scope.
  if grep -rIiEn --exclude-dir=.git --exclude=.denylist -f .denylist . ; then
    echo "   FAIL denylist match"; fail=1
  else
    echo "   OK   no denylist matches ($(grep -cvE '^#|^$' .denylist) terms)"
  fi
else
  echo "   SKIP no .denylist file (copy .denylist.example and fill it in)"
fi
# Real Meta object ids are long digit strings. Examples must be obviously fake.
# Documentation URLs (help centre article ids, ToS links) are not object ids.
if grep -rIn --exclude-dir=.git --include='*.py' --include='*.json' --include='*.md' \
     -E '\b(act_)?[0-9]{11,}\b' . \
   | grep -vE 'facebook\.com/(business/help|legal)' \
   | grep -vE '999999|888888|000000|123456' | grep . ; then
  echo "   FAIL a long numeric id is present; replace it with an obvious placeholder"; fail=1
else
  echo "   OK   no real-looking Meta object ids"
fi

echo
[ "$fail" -eq 0 ] && echo "ALL CHECKS PASSED" || echo "CHECKS FAILED"
exit "$fail"
