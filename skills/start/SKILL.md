---
name: start
description: Front door to the Meta ads workflows. Works out where you are (no account connected yet, nothing published, campaign live) and routes to the right command, stopping before anything that spends money. Use when the user says "/ads-cooking:start", "run my Meta ads", "help me with Facebook ads", "set up a lead campaign", or is not sure which of the Meta commands they need.
---

# Meta Ads Kit

Routes to the right workflow. Does none of the work itself.

## The command form

Every command in this kit is run exactly this way, from any folder:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking <command>
```

No install step, no virtualenv, no dependencies.

**Check Python before anything else.** It needs 3.10 or newer. On a Mac that has never had
developer tools installed, `python3` is a stub that opens an Apple installer dialog, so without
this the first thing a new user meets is that dialog rather than a sentence from us:

```bash
python3 --version
```

Older than 3.10, or no output: tell them to run `xcode-select --install`, or to get a current
Python from <https://www.python.org/downloads/>. `/ads-cooking:connect` checks this too and stops
with the same advice.

## Work out where they are

Check in this order and stop at the first thing that is not true:

1. **Is there a config folder?** Look for `ads-cooking/` in the current project, then `~/.ads-cooking/`.
   Nothing there means they have never set this up. Run **`/ads-cooking:connect`**. Do not create
   the folder by hand: `connect` is the only path that sets the file permissions and proves git
   cannot commit the token.
2. **Does the token work?** Run **`/ads-cooking:check`**. If it fails, fix that before anything else.
   Everything downstream fails in more confusing ways.
3. **Is anything published?** Read `campaign.json`. An empty `live.ad_id` means nothing exists
   yet. Run **`/ads-cooking:publish`**.
4. **Something is live.** Ask what they want:
   - See how it is doing → **`/ads-cooking:pulse`**
   - Change the wording → **`/ads-cooking:copy`**
   - Change the form questions → **`/ads-cooking:form`**

## The commands

| Command | What it does | Spends money? |
|---|---|---|
| `/ads-cooking:connect` | Connect an ad account, ending with a working token | No |
| `/ads-cooking:check` | Prove the token reaches the account, page and forms | No |
| `/ads-cooking:publish` | Create the campaign, dry run unless told otherwise | Only with `--go`, and paused |
| `/ads-cooking:copy` | Swap in new ad copy | Changes a live ad with `--go` |
| `/ads-cooking:form` | Publish changed lead form questions | Changes a live ad with `--go` |
| `/ads-cooking:pulse` | Read-only check of spend, leads and cost per lead | No, never |

## Rules that hold across all of them

- **Never run a `--go` command without the user asking for it in that turn.** Dry run first,
  show them what it would do, then wait. This is someone's advertising budget.
- **Never set anything ACTIVE.** The kit creates everything paused on purpose. Going live is a
  person's decision, made in Ads Manager where they can see the preview.
- **Never print the token**, or paste it into a file the user is reading, or into chat.
- If Meta returns an error, read `${CLAUDE_PLUGIN_ROOT}/context/api-notes.md` before guessing.
  Most of the confusing ones are in there with the actual fix.
