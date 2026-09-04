---
name: connect
description: Connect a Meta ad account so the other commands can run, ending in a working token and a config folder. Walks the Business Settings steps in order, creates the .env and campaign.json, and finishes by proving the connection works. Use when the user says "/meta-ads:connect", "connect my Meta account", "set up Meta ads", "I need a Meta token", or when another command reports that nothing is configured.
---

# Connect a Meta ad account

One-time setup. It ends with a working token and a config folder, verified.

Walk `${CLAUDE_PLUGIN_ROOT}/context/connecting-your-account.md` with the user, one step at a
time. Do not paste the whole list at them: most of it happens in a browser, in Business
Settings, and it is easy to get lost.

## The shape of it

1. Confirm which Business Portfolio owns the Page and the ad account. If they are in different
   portfolios, that has to be fixed first or the token will never reach both.
2. Create an app, and a **system user** inside the portfolio. A system user is what makes this
   survive: it is not tied to a person's login, so it does not break when someone changes their
   password or leaves.
3. Assign the ad account, the page and the app to that system user. **Assigning the ad account
   is not enough**: lead forms live on the page, so the page needs assigning too, with MANAGE
   or ADVERTISE.
4. Generate the token with `ads_management`, `leads_retrieval`, `pages_show_list` and
   `pages_manage_ads`.
5. Set up the config folder (below).
6. Run `/meta-ads:check` and do not stop until it is clean.

## The config folder

Create `meta-ads/` in their project, or `~/.meta-ads/`:

```bash
mkdir -p meta-ads
cp ${CLAUDE_PLUGIN_ROOT}/.env.example meta-ads/.env
cp ${CLAUDE_PLUGIN_ROOT}/campaign.example.json meta-ads/campaign.json
```

Verify it end to end before saying you are done:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m metaads check
```

Then have **them** paste the token into `meta-ads/.env`. Do not ask them to read it out, do not
put it in chat, and do not echo the file back afterwards.

Check `meta-ads/` is gitignored before finishing. If their project has a `.gitignore`, add it.

## Two things to say out loud at the end

- **Token expiry, and which kind they chose.** Meta offers both at generation time: 60 days, or
  Never. Sixty days is safer, because a leaked token dies on its own. Never is one less thing to
  forget. Whichever they pick, **write it down in their notes**, because the two fail completely
  differently: a 60-day token stops everything on a date you can predict, and a never-expiring
  one stays a live key to their ad spend until someone revokes it. A standard 60-day token means the ads keep running when it
  dies but every command here stops working, quietly. `/meta-ads:pulse` warns 14 days out.
- **The token is a key to their ad spend.** Secrets file only. Never in git, chat, or a doc.
