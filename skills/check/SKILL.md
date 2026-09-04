---
name: check
description: Check that the Meta connection works, before publishing or when something has stopped working. Tests the token, the ad account, the page, and lead form access in the order they usually break, and names the fix for whichever one failed. Read-only, spends nothing. Use when the user says "/meta-ads:check", "is my Meta connection working", "check my token", "my ads stopped working", or before any publish.
---

# Check the Meta connection

Four reads, in the order things actually break. Run this first whenever anything is wrong.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m metaads check
```

Exit code `0` means everything works and they can publish.

## Reading the result

It checks the token, then the ad account, then the page, then lead form access. It stops being
useful to guess past the first failure, so fix them in order.

**Lead forms failing while everything else passes** is the common one, and it is almost always
the same cause: the system user has the ad account but was never given a task on the *page*.
Fix it in Business Settings by giving the system user MANAGE or ADVERTISE on the page.

**Everything failing at once** with Meta's generic error usually means Meta is down, not that
anything is wrong with the setup. Wait an hour and re-run. Do not regenerate the token and do
not rebuild anything: see `${CLAUDE_PLUGIN_ROOT}/context/api-notes.md`.

**A token error** means it expired or was revoked. Generate a new one in Business Settings under
Users, System users, and update the `.env` file. Never paste the token into chat.

## What to tell the user

Lead with whether they can publish or not. If something failed, give them the one fix for the
first failure, not a list of everything that might be wrong.
