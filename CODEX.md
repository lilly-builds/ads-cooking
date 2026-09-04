# CODEX.md

**Read [AGENTS.md](AGENTS.md) first.** It is the source of truth for this repo. This file only
adds what is specific to Codex, and repeats the rules that involve money so they are in front of
you even if you read nothing else.

## The rules that cost money if you get them wrong

1. **Never run a `--go` command unless the user asked for it in that turn.** `publish`, `copy`
   and `form` write to a live ad account that spends real money. Dry run, show the output, wait.
2. **Never set anything ACTIVE.** That is the user's decision, made in Ads Manager.
3. **Never ask for the token in chat**, and never print or echo `.env`.
4. **Never make `pulse` write.** It reads only.

## Running the commands

There is no plugin root here, so use the repo:

```bash
PYTHONPATH="$(pwd)" python3 -m metaads <command>
```

Or install it, which puts a `metaads` command on the path:

```bash
pip install -e .
metaads check
```

The `skills/` directory is Claude Code's command layer. It is not used by Codex, but the files
are still the clearest written description of each workflow and what to tell a user about it, so
read the relevant `SKILL.md` before changing a workflow.

## Setup and verification

```bash
python3 -m unittest discover -s tests -t .    # 85 tests, no network, no ad account
./scripts/check.sh                            # the full pre-push gate
```

Python 3.10 or newer. No dependencies; do not add any.

## Sandboxes and network access

Everything except the four Meta-facing commands runs fully offline. The test suite makes no
network calls at all: `tests/fake_graph.py` is an in-memory Graph API. If you are in a sandbox
without network, you can still run the tests, the gate, and every dry run.
