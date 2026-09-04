---
name: check
description: Check that the Meta connection works, before publishing or when something has stopped working. Tests the token, the ad account, the page, and lead form access in the order they usually break, and names the fix for whichever one failed. Read-only, spends nothing. Use when the user says "/ads-cooking:check", "is my Meta connection working", "check my token", "my ads stopped working", or before any publish.
---

# Check the Meta connection

Four reads, in the order things actually break. Run this first whenever anything is wrong.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m adscooking check
```

Exit code `0` means everything works and they can publish. `1` means the account, page or forms
need attention. `3` means the setup itself is broken, which now includes a dead token: a key that
needs regenerating must never be reported as the ads being in trouble.

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

## The expiry line

A clean run ends with the token's expiry date. **Say it out loud and tell them to write it down.**
`/ads-cooking:pulse` warns 14 days out, but only on a token that still works: once it has expired,
the warning that would have prevented it is the thing that stops running. This line at setup time
is the only chance to diary it.

## What to tell the user

Lead with whether they can publish or not. If something failed, give them the one fix for the
first failure, not a list of everything that might be wrong.
