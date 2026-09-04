# Connecting a Meta ad account to the API

One-time setup. It ends with a token that lets the commands in this kit reach your ad account and
your Page, without anyone's password.

**Why a system user rather than your own login:** a system user belongs to the business, not to a
person. It does not break when someone changes their password, turns on two-factor, or leaves. It
is the difference between automation that keeps working and automation that breaks in three months.

**Order matters.** Several steps are blocked until an earlier one is done, and Meta's error
messages rarely say which. Work through these in sequence.

## Before you start

You need admin access to the Business Portfolio that owns the Page, and the ability to accept terms
on the account. Two steps require accepting legal terms and one asks for a password. Those are
yours to do; do not hand them to a tool.

## 1. Find the right Business Portfolio

Go to business.facebook.com, then Settings, then Business Settings.

Confirm the Page is listed under Accounts, Pages. Note the Business ID from the URL
(`business_id=...`); you will reuse it.

**Then check where the ad account lives.** Open Ads Manager and click the account selector. If the
portfolio shows "0 ad accounts" and the account sits under "Your account" as personal, that is the
problem you will hit at step 7. Worth knowing now.

## 2. Register as a developer

Go to developers.facebook.com. If it shows a marketing page with "Get Started", this account is not
a developer yet. Click through, which accepts Meta's Platform Terms and Developer Policies, fill in
contact info, and pick the Developer role.

## 3. Create the app

My Apps, then Create App.

- Name it something you will recognise later.
- Contact email gets the policy notices. Use one you read.
- Use cases: **Create and manage ads with Marketing API**, **Measure ad performance data**, and
  **Capture and manage ad leads** (needed for lead forms).
- Type Business, attached to your portfolio.
- Copy the App ID from the dashboard URL.

You do **not** need App Review. A system user token managing your own ad account works fine while
the app is in development mode. App Review is for acting on other people's accounts.

## 4. Create the system user

Business Settings, Users, System users, Add.

Name it something plain like `ad_manager`. Accept the non-discrimination advertising policy when
prompted.

**If the Add button is greyed out**, the portfolio has no app yet. Go back to step 3. Hovering the
button shows Meta's own explanation.

## 5. Assign the Page and the app to the system user

Select the system user, then Assign assets. Do this for Pages and for Apps: pick the asset, give
full control, assign.

**Assigning the ad account alone is not enough.** Lead forms live on the Page, so the Page needs
assigning too, with MANAGE or ADVERTISE. Skipping this is the most common reason publishing works
until the lead form step and then fails.

If the panel still says "no assets assigned" afterwards, refresh the page. The settings UI caches.
Do not assign them again.

## 6 and 7. Get the ad account into the portfolio

Skip to step 8 if Business Settings, Accounts, Ad accounts already lists your account.

If it does not, the ad account is personal and the system user cannot see it. Two options:

- **Move the existing account into the portfolio.** Preferred: it keeps its history, quality score,
  pixel and payment method.
- **Create a new ad account inside the portfolio.** Clean, but it starts with no history and needs
  a payment method.

**Moving an ad account into a portfolio is hard to undo.** If it is your own account and this is
its permanent home, that is fine. Be deliberate about it.

When you are done, note the ad account ID from the panel text, not from the URL. The URL's
`selected_asset_id` is an internal wrapper and using it produces confusing errors later.

## 8. Assign the ad account to the system user

On the Ad accounts page, open the account, Assign people, tick the system user, full control.

## 9. Generate the token

Back on the system user, Generate token.

- **App:** the one from step 3.
- **Expiry:** 60 days or Never. Sixty days is safer, since a leaked token dies on its own. Never is
  one less thing to forget. **Write down which you chose**, because they fail differently: a 60-day
  token stops everything on a predictable date, and a never-expiring one stays a live key to your
  ad spend until someone revokes it.
- **Scopes:** `ads_management`, `ads_read`, `business_management`, `leads_retrieval`,
  `pages_show_list`, `pages_read_engagement`, `pages_manage_ads`.

**The token is shown once.** Copy it straight into your `.env` file. Never paste it into a chat, a
document, or a commit. If you lose it, generate another.

## 10. Set up the config folder

```bash
mkdir -p meta-ads
cp "${CLAUDE_PLUGIN_ROOT}/.env.example" meta-ads/.env
cp "${CLAUDE_PLUGIN_ROOT}/campaign.example.json" meta-ads/campaign.json
```

Fill in the three values in `meta-ads/.env`. Make sure `meta-ads/` is gitignored.

## 11. Prove it works

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m metaads check
```

This checks the token, the ad account, the Page and lead form access, in the order they break. A
clean run means you can publish.

Lead forms failing while everything else passes is step 5: the system user needs a task on the Page.

## One more thing, before your first publish

A development-mode app cannot create ad creatives. Before running a real publish, go to App
Settings, add a Privacy Policy URL, and flip App Mode to Live. Everything else works in development
mode, so this only surfaces at the last step of your first publish.

## Keeping it working

- If you chose a 60-day token, regenerate it before it lapses. `metaads pulse` warns 14 days out.
  When it dies the ads keep running, but every command here stops working silently.
- The token is a key to your ad spend. Treat it like a password.
