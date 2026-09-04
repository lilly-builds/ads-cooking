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

## When Meta changes

The integration was last reviewed on 4 September 2026 and is pinned to Graph API `v21.0`. Read the
**“When Meta changes something”** section in [AGENTS.md](AGENTS.md) before responding to a Meta
error, deprecation, or changed dashboard path. Diagnose and repair with official Meta sources and
a test account; never "self-heal" by changing a live campaign, using `--go`, or setting anything
ACTIVE without the user's explicit request in that turn.

## Before you run anything on a new machine

`python3 --version` must say 3.10 or newer. On a Mac without developer tools, `python3` is a stub
that opens an Apple installer dialog, and that dialog is otherwise the first thing a new user
meets. Older than 3.10: `xcode-select --install`.

Then `connect`, which is offline and is the only path that locks the secrets file down and proves
git cannot commit it. Never build the config folder by hand.

## Running the commands

Installed as a plugin, from any folder:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking <command>
```

Working inside a clone of the repo, `${CLAUDE_PLUGIN_ROOT}` is not set, so use the repo root:

```bash
PYTHONPATH="$(pwd)" python3 -m adscooking <command>
```

Skills must always use the first form. `./scripts/check.sh` fails the build if one does not.


## The commands

Installed as a plugin, these are the slash commands. They are namespaced by the plugin, so the
prefix is part of the name.

| Command | What it does | Can it spend money? |
|---|---|---|
| `/ads-cooking:start` | Works out where the user is and routes to the right one | No |
| `/ads-cooking:connect` | Set up the config folder, then the Meta steps as prefilled links | No |
| `/ads-cooking:check` | Prove the token reaches the account, page and forms | No |
| `/ads-cooking:publish` | Create the campaign | Only with `--go`, and it lands paused |
| `/ads-cooking:copy` | Change the wording on a live ad | Changes a live ad with `--go` |
| `/ads-cooking:form` | Change the lead form questions | Changes a live ad with `--go` |
| `/ads-cooking:pulse` | Spend, leads, cost per lead, edit detection | No, never |

Each maps to a subcommand of the same name, minus `start`, which only routes:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking <connect|check|publish|copy|form|pulse>
```

## The skills

`skills/start/SKILL.md` is the front door and routes to the other six. If you are adding a
skill, match the existing shape: frontmatter with `name` and `description`, the exact command,
what to tell the user, and an explicit "what not to do".

Reference docs from a skill with `${CLAUDE_PLUGIN_ROOT}/context/<file>.md`, never a relative path.

## Reviewing changes here

The safety properties in AGENTS.md are asserted by tests, not just documented. If you change
`publish.py`, `pulse.py`, `config.py` or `setup.py`, run the suite before you say anything works:

```bash
python3 -m unittest discover -s tests -t .
```
