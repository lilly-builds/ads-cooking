---
name: pulse
description: One read-only check of a live Meta campaign. Reports spend, leads and cost per lead against a benchmark band, flags anyone editing the live ad, and warns before the token expires. Never writes to Meta and never changes an ad. Use when the user says "/meta-ads:pulse", "how are my ads doing", "check the campaign", "what's my cost per lead", or wants a daily or morning check on live ads.
---

# Check a live campaign

Read-only. This command cannot change anything on Meta, by design: the thing that watches the
spend should not also be able to change it.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m metaads pulse
```

Exit code is the verdict:

| Code | Means | What to do |
|---|---|---|
| 0 | Fine | One line and stop |
| 1 | Something to watch | Numbers plus the warning |
| 2 | Needs attention | Lead with the problem |
| 3 | Setup problem, not a campaign problem | Fix the config; do not report this as an ads issue |

Exit 3 is deliberately separate. A missing `.env` is not a reason to tell someone their ads are
in trouble.

## What to tell the user

Match the reply to the exit code. Do not pad a quiet day into a paragraph.

**Exit 0.** One line. `"$41 spent, 2 leads, $20.50 each. Nothing to flag."` Stop there.

**Exit 1.** The headline numbers, then the specific warning and what it means. Still short.

**Exit 2.** Lead with the problem, not the numbers. Say what it is, what it costs if ignored,
and the one thing to do about it. If they asked for a background or recurring check, this is
the case worth interrupting them for.

## Reading the findings

**Cost per lead above the band.** The band in their config is a starting point, not a target.
Before suggesting anything, check how many leads it is based on: under about 3 it is noise, and
the tool says so rather than giving a verdict.

**Spend with no leads.** These thresholds are house rules, not research. They mean "you have now
spent enough to know something is wrong", not "Meta is broken".

**An edit was detected.** Someone changed the live ad set since the last check. Editing a live
ad set restarts the learning phase, which at a small daily budget can cost several days of
delivery. If it happened inside the no-edit window, say so plainly.

**Token expiring.** Real deadline, and the tool gives you the date. Use it: "expires 14 March"
is something they can act on in a way that "expires in 12 days" is not. When it dies, the ads
keep running but every command here stops working, silently.

**No spend today on an active ad set.** Before mid-morning this is usually nothing. Later in the
day it means delivery has stopped.

**Nothing about edits on the first run.** Edit detection works by comparing against the previous
run, so the first one has nothing to compare to. That is expected, not a fault. Say so if they
ask why it did not check.

## What not to do

- **Never change anything in response to what this reports.** Not the budget, not the copy, not
  the status. Report, then let them decide. A run of this command that ends in an edit is a bug
  in your behaviour, not a helpful extra.
- **Do not invent a threshold.** If a number is outside what the config judges, log it and say
  it is not something you have a benchmark for. `${CLAUDE_PLUGIN_ROOT}/context/ad-management-principles.md`
  lists what was verified and what was not, on purpose.
- **Do not report a cost per lead verdict off one or two leads.** It is the fastest way to talk
  someone into killing an ad that was fine.

## Running it daily

If the user has the `/loop` skill, `/loop 24h /meta-ads:pulse` runs it daily. Otherwise a cron
entry or a launchd agent does the same thing; the command is a plain shell command with a
meaningful exit code, so anything that can run one works.

It keeps its own history in the config folder
(`pulse-history.jsonl`), so after a few weeks their own numbers are a better benchmark than any
published median.
