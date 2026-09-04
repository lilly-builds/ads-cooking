---
name: publish
description: Create a Meta lead campaign from a config file: campaign, ad set, video, thumbnail, lead form, creative and ad. Shows exactly what it would do first and creates nothing until told to go, then creates everything paused. Use when the user says "/ads-cooking:publish", "publish my campaign", "launch the ad", "create the Meta campaign", or has a video and copy ready and wants it live.
---

# Publish a campaign

Seven steps in one command. Two safety rules hold throughout: nothing is created without `--go`,
and everything that is created is PAUSED.

## Always dry run first

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking publish
```

This sends nothing. It prints the budget, the audience, the placements, the creative and where
leads land. **Show the user that summary and wait.** Do not run the next command in the same turn.

## Then, only if they say yes

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking publish --go
```

It prints the ids it created. Paste them into the `live` section of `campaign.json`, or `copy`,
`form` and `pulse` will not know what to change.

## After it runs

Everything is paused. Tell them the last step is theirs: open Ads Manager, look at the ad
preview and click through the lead form, then set the campaign, ad set and ad to active. That
last click is deliberately not automated.

## If it fails partway

Run it again. Any id already in the `live` section is reused rather than recreated, so a failure
at the lead form step does not re-upload the video. Fill in what it printed before it failed.

## Errors worth knowing before you debug

Full list with fixes in `${CLAUDE_PLUGIN_ROOT}/context/api-notes.md`. The two that stop people:

- **"created by an app that is in development mode"** means the app is still in Development.
  Add a Privacy Policy URL in App Settings, then flip App Mode to Live. Nothing else will fix it.
- **"Terms of Service Not Accepted"** means the Page has never accepted the lead ads terms. Open
  the Forms Library for that page once and accept.

## What not to do

- Never run `--go` without the user asking in that turn.
- Never set anything ACTIVE.
- If the dry run warns about the privacy policy URL, stop and get a real one. Meta rejects the
  form otherwise, and it fails at step 5 after the video has already uploaded.
