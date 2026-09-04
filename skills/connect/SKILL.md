---
name: connect
description: Connect a Meta ad account so the other commands can run, ending in a working token and a config folder. Checks Python, creates the config folder, proves the secrets file is hidden from git, and hands over Meta's setup steps as prefilled links once it knows the Business Portfolio id. Use when the user says "/ads-cooking:connect", "connect my Meta account", "set up Meta ads", "I need a Meta token", or when another command reports that nothing is configured.
---

# Connect a Meta ad account

One-time setup. Most of it is a person clicking through Meta. The command does the parts that
have to be identical every time, and tells them what is theirs.

## Run this first

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking connect
```

It touches nothing on Meta. It checks the Python version, creates the config folder, locks the
secrets file to the user only, proves git cannot commit it, and prints the nine Meta steps in
order. Exit `3` means values are still blank, which on a first run is the expected answer.

**With no flag it writes `~/.ads-cooking/`.** To keep the settings inside a project instead, name
the folder. The flag goes before the subcommand:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking --config-dir ads-cooking connect
```

Either way, **read the path it printed back to the user** and tell them to fill the values in at
that path. Never name a `.env` from memory: if they hand-make one somewhere else, a project-local
folder takes precedence over the home one the moment it exists, and the hand-made file skips every
check this command does.

## Then get the Business Portfolio id, and re-run

Step 1 of the printed list is the Business Portfolio id, and it comes first because almost
every later link is scoped to it. Once you have it:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking connect --business-id <ID>
```

Now each step lands in the right portfolio instead of sending them hunting, which is where the
time goes. Add `--page-id` and `--app-id` as those appear, and re-run again. Re-running never
overwrites anything.

Two of the steps give the Business Settings root and then the sidebar clicks, rather than a
direct link. That is deliberate: Meta renames those sections and moves them between Business
Manager and Business Suite, and a link that 404s wastes the same time as no link. Read the
sidebar path out loud rather than inventing a URL.

## What only they can do

Nine steps print; five of them are unavoidably the user's, and none should be automated or
worked around:

- **Accepting the developer terms.** A legal agreement.
- **Accepting the non-discrimination advertising policy** when creating the system user.
- **Typing their password** when creating the app.
- **Generating the token.** Shown once, never again.
- **Turning the ads on** at the very end, in Ads Manager.

Walk `${CLAUDE_PLUGIN_ROOT}/context/connecting-your-account.md` with them one step at a time
rather than pasting the whole thing. The order matters and Meta's errors do not explain it.

Say this, in these words or close to them:

> Meta will show the token once. Copy it straight into the `.env` file after
> `META_SYSTEM_USER_TOKEN=`. Do not paste it into this chat, a document, or anywhere else. If it
> ends up somewhere it should not, regenerate it and the old one dies.

They also fill in two more values in `.env`:

- `META_AD_ACCOUNT_ID` from Ads Manager, top left. **The number in the panel text, not the
  `selected_asset_id` in the URL.** The URL number is an internal wrapper and produces
  confusing errors later.
- `META_PAGE_ID` from the Facebook Page, Settings, About.

## Using the browser to find the ids

Reading id numbers out of Business Settings is the tedious half and it is safe to help with. If
Claude in Chrome is available, offer it, and keep it to reading:

**Allowed.** Open and read `https://business.facebook.com/settings/info` for the Business
Portfolio id, the Ads Manager page for the ad account id, and the Page's About tab for the Page
id. Report the numbers back and put them in the `connect` flags.

**Never.** Do not drive the token screen, do not click Generate token, do not click any Accept
or Save on a terms or consent page, do not touch a password field, and do not read a page that
is displaying the token. Those steps are the user's by design, and a browser agent that reads
the token screen puts the token into a transcript, which is the one leak here that cannot be
undone.

If the browser gets stuck, or a page needs a login, stop and hand it back rather than retrying.

## Finish

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking check
```

Do not stop until it is clean. It ends by printing the token's expiry date. **Read that date out
and tell them to write it down**, because the two kinds of token fail completely differently: a
60-day one stops every command here on a predictable date while the ads keep running, and a
never-expiring one stays a live key to their ad spend until somebody revokes it. `/ads-cooking:pulse`
warns 14 days out, but only while the token still works.

## What not to do

- Do not ask them to paste the token into chat, and do not read `.env` back to them.
- Do not create the config folder by hand. `connect` does it, and it is the only path that
  checks git and sets the file permissions.
- Do not carry on if the git check says STOP. A token in git history cannot be taken back.
