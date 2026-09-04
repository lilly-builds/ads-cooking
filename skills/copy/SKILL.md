---
name: copy
description: Change the wording on a live Meta ad. Builds a new creative with the new text and points the existing ad at it, so the ad keeps its id and its delivery history. Use when the user says "/meta-ads:copy", "change the ad copy", "update the headline", "the wording isn't working", or wants to test different text on a running ad.
---

# Change the copy on a live ad

## First, say what this actually does

Ad creatives cannot be edited. So changing a headline is not an update, it is: build a new
creative with the new text, then point the existing ad at it. The ad keeps its id, which is what
preserves its delivery history. Worth saying once, because "why is there a new creative in my
account" is a reasonable question.

## Edit the text

In `campaign.json`, under `creative`: `primary_texts` and `headlines`. Several of each is
better than one. Meta picks the combination per person, which beats splitting a small budget
across near-identical ads.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m metaads copy
```

Dry run. Shows what would change, sends nothing. Then, only if they confirm:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m metaads copy --go
```

## Before running it on a campaign that is still learning

Ask when it launched. Changing the creative on a live ad set can restart the learning phase,
and at a small daily budget that costs a few days of stable delivery. If it launched in the
last few days, say so and let them decide whether it can wait. Do not just do it quietly.

If they want to test new copy without disturbing a campaign that is working, the safer move is
duplicating the ad set and changing the copy on the duplicate. That leaves the original alone.

## What not to do

- Never run `--go` without them asking in that turn.
- Do not rewrite their copy unless they asked you to. Changing the wording is their call; this
  command's job is to get their wording live.
