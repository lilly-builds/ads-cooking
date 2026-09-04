# Meta Marketing API notes

Things that cost hours the first time. Read this before debugging an error.

## Four facts that shape everything else

**1. Lead forms cannot be edited.** Once published, a form is frozen. Changing a question means
creating a new form, a new creative pointing at it, and swapping that onto the ad. This is why
`metaads form` looks like it does more than it should.

**2. Ad creatives cannot be edited either.** Same pattern: a copy change is a new creative and a
swap. The ad keeps its id, so its delivery history survives.

**3. Page-owned endpoints need a page token.** Lead forms live on the Page, not the ad account.
Calling `/{page_id}/leadgen_forms` with the system-user token fails with a permission error that
never mentions page tokens. Get one with `GET /{page_id}?fields=access_token` first. Publishing
works perfectly right up until the form step, which makes this confusing to diagnose.

**4. A blanket error code 1 across every call means Meta is down.** Code 1 is Meta's generic
server-side error. On one call it means little. When *every* call in a run returns it, the account
is fine and the token is fine: Meta is having an outage. Wait an hour or two and re-run. Do not
regenerate the token, and do not rebuild the campaign. Rebuilding during an outage is how a
30-minute wait turns into a day of cleanup.

## Errors when creating a campaign, and their fixes

These came up in order on a first publish. Each is a one-line fix.

| Error | Fix |
|---|---|
| `Must specify True or False in is_adset_budget_sharing_enabled` | Set `is_adset_budget_sharing_enabled: false` on the **campaign**. False means the budget lives on the ad set. |
| `Bid Amount Or Bid Constraints Required For Bid Strategy` | Set `bid_strategy: LOWEST_COST_WITHOUT_CAP` on the **ad set**. Automatic bidding, no cap. |
| `Terms of Service Not Accepted` | The **Page** has never accepted the lead ads terms. Open the Forms Library for that page once, or visit `facebook.com/legal/leadgen/tos/?page_id=<PAGE_ID>`. |
| `Advantage+ audience min age can't be > 25` | Advantage+ forces ages 25 to 65. Either accept a broad range or turn Advantage+ off to hold your own. |
| `Advantage Audience Flag Required` | Even when off, the flag must be sent explicitly: `targeting_automation: {advantage_audience: 0}`. |
| `Invalid keys "required, label" in custom_disclaimer[checkboxes]` | The consent checkbox takes `{key, text}`, not `required`/`label`. |
| `Each bullet point should be under 80 characters for LIST_STYLE` | Shorten the greeting bullets, or switch to `PARAGRAPH_STYLE`. |
| `Ads creative post was created by an app that is in development mode` | Flip the app to Live: App Settings, add a Privacy Policy URL, then change App Mode to Live. A development-mode app cannot create ad creatives. |

The first five are handled for you in `metaads/publish.py`. The last three depend on your content
and your app, so they can still bite.

## Two rules Meta enforces on lead forms

- **The consent checkbox must default to unchecked.** A pre-checked box is rejected.
- **List-style greeting bullets must be under 80 characters each.**

## Setup problems and what they actually mean

| Symptom | Cause | Fix |
|---|---|---|
| "Add system user" is greyed out | No app exists in the portfolio yet | Create the app first. Hover the button; Meta says so in the tooltip. |
| The token cannot see the ad account | The ad account is personal, not owned by the business portfolio | Move it into the portfolio. A system user can only reach assets the portfolio owns. |
| Assets still show "none assigned" after assigning them | The settings UI caches | Refresh the page. Do not assign them again. |
| Calls fail with the wrong ad account id | The number in the URL was used | The URL's `selected_asset_id` is an internal wrapper. Use the id shown in the panel text. |
| Everything stops working after about two months | The 60-day token expired | Regenerate it and update `.env`. `metaads pulse` warns 14 days out. |

## Rate limits

Ad account calls are throttled per account, and the headers tell you where you stand:
`X-Business-Use-Case-Usage` carries a percentage. Nothing in this kit polls hard enough to hit it,
but a loop over many ad sets can. Back off when the usage percentage climbs rather than retrying
immediately.

## Versioning

This kit pins `v21.0` in `metaads/graph.py`. Meta supports a version for about two years and then
auto-upgrades calls, which can change behaviour without warning. When you bump it, re-run the tests
first: they assert payload shapes, so a field that moved or was renamed shows up there rather than
in production.
