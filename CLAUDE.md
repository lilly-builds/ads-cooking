# CLAUDE.md

**Read [AGENTS.md](AGENTS.md) first.** It is the source of truth for this repo. This file only
adds what is specific to Claude Code, and repeats the rules that involve money so they are in
front of you even if you read nothing else.

## The rules that cost money if you get them wrong

1. **Never run a `--go` command unless the user asked for it in that turn.** Dry run, show the
   output, wait. Approval for one run is not approval for the next.
2. **Never set anything ACTIVE.** That is the user's decision, made in Ads Manager.
3. **Never ask for the token in chat**, and never print or echo `.env`.
4. **Never make `pulse` write.** It reads only.

## Running the commands

Installed as a plugin, from any folder:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m metaads <command>
```

Working inside a clone of the repo, `${CLAUDE_PLUGIN_ROOT}` is not set, so use the repo root:

```bash
PYTHONPATH="$(pwd)" python3 -m metaads <command>
```

Skills must always use the first form. `./scripts/check.sh` fails the build if one does not.

## The skills

`skills/meta-ads/SKILL.md` is the front door and routes to the other six. If you are adding a
skill, match the existing shape: frontmatter with `name` and `description`, the exact command,
what to tell the user, and an explicit "what not to do".

Reference docs from a skill with `${CLAUDE_PLUGIN_ROOT}/context/<file>.md`, never a relative path.

## Reviewing changes here

The safety properties in AGENTS.md are asserted by tests, not just documented. If you change
`publish.py`, `pulse.py` or `config.py`, run the suite before you say anything works:

```bash
python3 -m unittest discover -s tests -t .
```
