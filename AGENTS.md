# Working in this repo

Instructions for a coding agent. `CLAUDE.md` and `CODEX.md` point here; this file is the source
of truth.

## What this is

A Claude Code plugin wrapping the Meta Marketing API. Six workflows: connect an ad account, check
the connection, publish a lead campaign, change live ad copy, change a lead form, and a read-only
daily pulse.

**This code spends real money on advertising.** Every rule below exists because of that.

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

## Rules you must not break

1. **Never run a `--go` command unless the user asked for it in that turn.** `publish`, `copy` and
   `form` write to a live ad account. Dry run first, show the output, wait for a reply. Approval
   for one run is not approval for the next.
2. **Never set a campaign, ad set or ad to ACTIVE.** No code path here does it and none should be
   added. A person makes that decision in Ads Manager, looking at the preview.
3. **Never ask the user to paste their token into the chat**, and never read `.env` back to them,
   print it, or write it into a file they will share. The token is a key to their ad spend. This
   covers the browser too: never point a browser tool at the token screen, and never automate a
   consent click or a password field. Reading id numbers is fine; those four are the user's.
4. **Never add a fallback ad account id**, not even in an example or a test helper that could be
   copied. A missing value must stop the command before it reaches Meta. `test_config.py` greps
   the package for this and will fail you.
5. **Never make `pulse` write.** It calls `get` only, and `test_pulse_never_writes` enforces it.
6. **Nothing identifying from a real ad account goes in this repo.** It is public. `scripts/check.sh`
   section 8 is the gate.

## Setup you can do without the user

All of this is safe, offline, and touches nothing on Meta.

**Check Python first, before anything else.** It needs 3.10 or newer. On a Mac that has never had
developer tools installed, `python3` is a stub that opens an Apple installer dialog, so skipping
this means the first thing a new user meets is that dialog instead of a sentence from us.

```bash
python3 --version        # 3.10 or newer. Older: xcode-select --install
```

Then let `connect` do the rest. It is offline, it never reaches Meta, and it is the only path
that sets the file permissions and proves git cannot commit the token:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking connect   # installed as a plugin
PYTHONPATH="$(pwd)" python3 -m adscooking connect                  # working in a clone
```

It creates the config folder, copies `.env` and `campaign.json` into it without ever overwriting
an existing one, locks `.env` to its owner, runs `git check-ignore` on it for real, and prints
Meta's nine setup steps in order. Exit 3 on a first run means values are still blank, which is
the expected answer.

**Do not create the config folder by hand.** The prose version of this was four steps a model
performed from memory, and one of them, the gitignore check, is the only mistake in this repo
that cannot be undone. It is code with tests behind it now: `adscooking/setup.py` and
`tests/test_setup.py`.

**Ask for the Business Portfolio id before anything else, and re-run with it.**

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking connect --business-id <ID>
```

Almost every later URL is scoped to that id. With it, steps 4 to 7 are links that land on the
right screen; without it, the user is told to go hunting in Business Settings, which is where the
setup time goes. Add `--page-id` and `--app-id` as they appear and re-run. Re-running is safe.

If the git check says STOP, stop. Add the config folder to that repository's `.gitignore` before
a token goes anywhere near it.

Requires Python 3.10 or newer. Nothing else: no pip install, no virtualenv, no lockfile.

Then stop. The Meta steps are the user's.

### The browser can find the ids, and nothing else

Reading id numbers out of Business Settings is the tedious half of setup and it is safe to help
with. If a browser tool is available, use it for reading only:

**Allowed.** Open and read `https://business.facebook.com/settings/info` for the Business
Portfolio id, Ads Manager for the ad account id, and the Page's About tab for the Page id. Feed
what you find into the `connect` flags.

**Never.** Do not drive the token screen, click Generate token, click Accept or Save on any terms
or consent page, touch a password field, or read a page that is displaying the token. Those are
the user's steps by design, and a browser agent that reads the token screen puts a key to
somebody's ad spend into a transcript.

## What only a human can do

Four things. Each involves a password, a legal agreement, or a decision to spend money, and none
of them should be automated or worked around. When you reach one, say plainly that it is theirs,
give them the exact link and the exact clicks, and wait.

### Human step 1: connect the account and generate a token

Full walkthrough: `context/connecting-your-account.md`. Walk it with them one step at a time
rather than pasting the whole thing. The order matters and Meta's errors do not explain it.

The parts that are unavoidably theirs:

- **Accepting the developer terms** at <https://developers.facebook.com>. Legal consent.
- **Accepting the non-discrimination advertising policy** when creating the system user. Legal
  consent.
- **Typing their password** when creating the app.
- **Generating the token** at Business Settings, Users, System users, Generate token. It is shown
  once and never again.

Tell them, in these words or close to them:

> Meta will show the token once. Copy it straight into the `.env` file after
> `META_SYSTEM_USER_TOKEN=`. Do not paste it into this chat, a document, or anywhere else. If it
> ends up somewhere it should not, regenerate it and the old one dies.

**Use the path `connect` printed, and read it back to them.** Do not say `ads-cooking/.env` from
memory: with no flag, a first run writes `~/.ads-cooking/.env`, because `config_dir()` only
prefers a project-local `ads-cooking/` once it already holds config. Naming the wrong file is how
a user ends up hand-making a second one that skips every check here, and it wins, because a
project-local folder takes precedence the moment it exists. For a project-local setup, pass the
flag before the subcommand: `--config-dir ads-cooking connect`.

Then have them fill in the other two values in that same `.env`:

- `META_AD_ACCOUNT_ID` from Ads Manager, top left. **The number in the panel text, not the
  `selected_asset_id` in the URL.** The URL number is an internal wrapper and produces confusing
  errors later.
- `META_PAGE_ID` from the Facebook Page, Settings, About.

Verify before moving on:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking check   # installed as a plugin
PYTHONPATH="$(pwd)" python3 -m adscooking check                  # working in a clone
```

Exit 0 means done. A clean run ends with the token's expiry date: read it out and tell them to
write it down. `pulse` warns 14 days ahead, but only on a token that still works, so once one has
expired the warning that would have prevented it is exactly what stops running. If lead forms fail while everything else passes, the system user has the ad
account but was never given a task on the Page. Send them back to give it MANAGE or ADVERTISE.

### Human step 2: flip the app out of Development mode

A development-mode app cannot create ad creatives. Everything else works, so this only surfaces
at the last step of the first publish, after the video has already uploaded.

Give them this, with their App ID filled in:

1. Go to `https://developers.facebook.com/apps/<APP_ID>/settings/basic/`
2. If **Privacy Policy URL** is empty, paste a real privacy policy URL and click **Save changes**.
   Meta will not let the app go live without one.
3. At the top of the app dashboard, find the **App Mode** toggle that says **Development** and
   switch it to **Live**. Confirm if prompted.

### Human step 3: accept the lead ads terms for the Page

One-time, per Page. Without it, creating a lead form fails with `Terms of Service Not Accepted`.

Give them: `https://www.facebook.com/legal/leadgen/tos/?page_id=<PAGE_ID>` with their Page ID
filled in, or tell them to open the Forms Library for that Page once and accept.

### Human step 4: turn the ads on

Everything this kit creates is PAUSED. Turning it on is a decision to start spending, and it is
theirs.

After a successful `publish --go`, tell them:

1. Open <https://adsmanager.facebook.com>
2. Find the campaign it just created.
3. Look at the **ad preview** and click through the **lead form** as a real person would.
4. Set the **campaign**, the **ad set** and the **ad** to Active. All three; one still paused
   means nothing delivers.

Do not offer to do this for them, and do not add a command that does.

## After a publish, do not forget this

`publish --go` prints the ids it created. **Write them into the `live` section of
`ads-cooking/campaign.json`.** If you skip it, `copy`, `form` and `pulse` have nothing to work on,
and re-running `publish` will build a second campaign rather than resuming the first.

## Conventions

- **One command form**, everywhere, no exceptions:
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking <command>`. A skill with a bare
  `python3 -m adscooking` fails for anyone not sitting in the repo. `check.sh` section 5 catches it.
- **No dependencies.** Standard library only, tests included. Do not add a package.
- **Settings are data.** New knobs go in `campaign.json`, not in code.
- **`adscooking/graph.py` is the only module that talks to Meta.** Everything else builds payloads
  and hands them over. That is what makes the tests possible; do not route around it.
- **Every Meta quirk gets a comment saying why**, because none of them are guessable from the
  code. `context/api-notes.md` is the long form.
- **Run `./scripts/check.sh` before pushing.** Tests, JSON, manifest, skill frontmatter, command
  form, links, secrets, and the identifying-data denylist.

## Exit codes

| Code | Means |
|---|---|
| 0 | Fine |
| 1 | Something to watch |
| 2 | The campaign needs attention |
| 3 | Setup problem, not a campaign problem |

3 is deliberately separate from 2. A missing `.env` must never be reported to a user as their ads
being in trouble.

## Where things are

| Path | What |
|---|---|
| `adscooking/graph.py` | The only module that talks to Meta |
| `adscooking/config.py` | Loading credentials and settings, and refusing to guess |
| `adscooking/setup.py` | Python guard, config folder, git check, and Meta's setup links |
| `adscooking/publish.py` | The seven publish steps, dry run and resume |
| `adscooking/update.py` | Copy and lead form changes |
| `adscooking/pulse.py` | The read-only monitor |
| `skills/` | The Claude Code commands |
| `context/` | Setup guide, API notes, and the research behind the thresholds |
| `tests/` | 130 tests, including the in-memory Graph API |
