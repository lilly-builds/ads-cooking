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
| `/ads-cooking:connect` | Connect an ad account, ending with a working token | No |
| `/ads-cooking:check` | Prove the token reaches the account, page and forms | No |
| `/ads-cooking:publish` | Create the campaign | Only with `--go`, and it lands paused |
| `/ads-cooking:copy` | Change the wording on a live ad | Changes a live ad with `--go` |
| `/ads-cooking:form` | Change the lead form questions | Changes a live ad with `--go` |
| `/ads-cooking:pulse` | Spend, leads, cost per lead, edit detection | No, never |

Each maps to a subcommand of the same name, minus `start`, which only routes:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking <check|publish|copy|form|pulse>
```

## Rules you must not break

1. **Never run a `--go` command unless the user asked for it in that turn.** `publish`, `copy` and
   `form` write to a live ad account. Dry run first, show the output, wait for a reply. Approval
   for one run is not approval for the next.
2. **Never set a campaign, ad set or ad to ACTIVE.** No code path here does it and none should be
   added. A person makes that decision in Ads Manager, looking at the preview.
3. **Never ask the user to paste their token into the chat**, and never read `.env` back to them,
   print it, or write it into a file they will share. The token is a key to their ad spend.
4. **Never add a fallback ad account id**, not even in an example or a test helper that could be
   copied. A missing value must stop the command before it reaches Meta. `test_config.py` greps
   the package for this and will fail you.
5. **Never make `pulse` write.** It calls `get` only, and `test_pulse_never_writes` enforces it.
6. **Nothing identifying from a real ad account goes in this repo.** It is public. `scripts/check.sh`
   section 8 is the gate.

## Setup you can do without the user

All of this is safe, offline, and touches nothing on Meta.

```bash
git clone https://github.com/lilly-builds/ads-cooking
cd ads-cooking

# 1. Tests. No dependencies, no network, no ad account.
python3 -m unittest discover -s tests -t .        # expect: 91 tests, OK

# 2. The full gate.
./scripts/check.sh                                 # expect: ALL CHECKS PASSED

# 3. A config folder for the user to fill in.
mkdir -p ads-cooking
cp .env.example ads-cooking/.env
cp campaign.example.json ads-cooking/campaign.json

# 4. Confirm it is ignored by git before anything else happens.
git check-ignore ads-cooking/.env                     # expect: ads-cooking/.env
```

Requires Python 3.10 or newer. Nothing else: no pip install, no virtualenv, no lockfile.

Then stop. Step 5 is the user's.

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

> Meta will show the token once. Copy it straight into `ads-cooking/.env` after
> `META_SYSTEM_USER_TOKEN=`. Do not paste it into this chat, a document, or anywhere else. If it
> ends up somewhere it should not, regenerate it and the old one dies.

Then have them fill in the other two values in `ads-cooking/.env`:

- `META_AD_ACCOUNT_ID` from Ads Manager, top left. **The number in the panel text, not the
  `selected_asset_id` in the URL.** The URL number is an internal wrapper and produces confusing
  errors later.
- `META_PAGE_ID` from the Facebook Page, Settings, About.

Verify before moving on:

```bash
PYTHONPATH="$(pwd)" python3 -m adscooking check
```

Exit 0 means done. If lead forms fail while everything else passes, the system user has the ad
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
| `adscooking/publish.py` | The seven publish steps, dry run and resume |
| `adscooking/update.py` | Copy and lead form changes |
| `adscooking/pulse.py` | The read-only monitor |
| `skills/` | The Claude Code commands |
| `context/` | Setup guide, API notes, and the research behind the thresholds |
| `tests/` | 91 tests, including the in-memory Graph API |
