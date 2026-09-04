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
PYTHONPATH="$(pwd)" python3 -m adscooking <command>
```

Or install it, which puts a `adscooking` command on the path:

```bash
pip install -e .
adscooking check
```

## The commands

| Subcommand | What it does | Can it spend money? |
|---|---|---|
| `check` | Prove the token reaches the account, page and forms | No |
| `publish` | Create the campaign | Only with `--go`, and it lands paused |
| `copy` | Change the wording on a live ad | Changes a live ad with `--go` |
| `form` | Change the lead form questions | Changes a live ad with `--go` |
| `pulse` | Spend, leads, cost per lead, edit detection | No, never |

In Claude Code these are also slash commands (`/ads-cooking:check` and so on), and two more exist
there with no CLI equivalent: `/ads-cooking:connect` walks the account setup, and
`/ads-cooking:start` routes to whichever of the others you need.

The `skills/` directory is Claude Code's command layer. It is not used by Codex, but the files
are still the clearest written description of each workflow and what to tell a user about it, so
read the relevant `SKILL.md` before changing a workflow.

## Setup and verification

```bash
python3 -m unittest discover -s tests -t .    # 96 tests, no network, no ad account
./scripts/check.sh                            # the full pre-push gate
```

Python 3.10 or newer. No dependencies; do not add any.

## Sandboxes and network access

Everything except the four Meta-facing commands runs fully offline. The test suite makes no
network calls at all: `tests/fake_graph.py` is an in-memory Graph API. If you are in a sandbox
without network, you can still run the tests, the gate, and every dry run.
