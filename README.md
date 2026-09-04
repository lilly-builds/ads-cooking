# Meta Ads Kit

Run a Meta lead-generation campaign from Claude Code, or from a terminal. Connect an ad account,
publish a campaign, change live ad copy and lead forms, and check spend and cost per lead every
morning.

**No dependencies.** Python standard library only, tests included. If you have `python3`, you have
everything.

```
/plugin marketplace add lilly-builds/ads-cooking
/plugin install meta-ads@ads-cooking
```

Commands are namespaced by the plugin, so they are `/meta-ads:check`, `/meta-ads:publish` and so
on. `/meta-ads:start` is the front door if you are not sure which you want.

## The commands

| Command | What it does | Can it spend money? |
|---|---|---|
| `/meta-ads:start` | Works out where you are and routes to the right one | No |
| `/meta-ads:connect` | Connect an ad account, ending with a working token | No |
| `/meta-ads:check` | Prove the token reaches the account, page and forms | No |
| `/meta-ads:publish` | Create the campaign | Only with `--go`, and it lands paused |
| `/meta-ads:copy` | Change the wording on a live ad | Changes a live ad with `--go` |
| `/meta-ads:form` | Change the lead form questions | Changes a live ad with `--go` |
| `/meta-ads:pulse` | Spend, leads, cost per lead, and edit detection | No, never |

Everything runs the same way, from any folder:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m metaads <command>
```

## Why it is built the way it is

This code can spend someone's advertising budget. Most of the design follows from that.

**Dry run is the default.** `publish`, `copy` and `form` create nothing without `--go`. A dry run
prints the budget, the audience, the placements and where leads land, so there is something real to
check before money is involved:

```
Check these before you run it for real:

  Budget      $20.00 a day, about $600 a month
  Audience    women, 30 to 45, in US
  Placements  facebook, instagram
  Copy        3 primary texts, 2 headlines
  Leads go to the instant form 'Lead form v1'

  Warning: the lead form still points at example.com for its privacy
  policy. Meta will reject the form. Set a real URL first.
```

**Everything is created paused.** Publishing and going live are separate decisions. The second one
is made by a person looking at the ad preview in Ads Manager. The code has no path to setting
anything active, and a test asserts it.

**The monitor cannot write.** `pulse` only ever calls `get`. The thing watching the spend should not
also be able to change it, and `test_pulse_never_writes` enforces that by handing it a client that
raises on any write.

**Nothing is ever assumed.** There is no fallback ad account id anywhere. A missing value stops the
command before it reaches Meta, rather than falling back to whatever was baked in as a default. A
test greps the package to keep it that way.

**The token is never printed.** It is not exposed on the client object and not in its `repr`, so a
stray traceback cannot leak it.

## What Meta will not tell you

Four constraints shape the whole design. Full detail with the error messages is in
[`context/api-notes.md`](context/api-notes.md).

**Lead forms cannot be edited.** Once published, frozen. Changing one question means a new form, a
new creative pointing at it, and a swap onto the ad. One change, three API calls.

**Ad creatives cannot be edited either.** A copy change is a new creative and a swap. The ad keeps
its id, which is what preserves its delivery history.

**Lead forms need a page token, not the system-user token.** Publishing works perfectly until step
five and then fails with a permission error that never mentions page tokens.

**A blanket error code 1 on every call means Meta is down.** Not your account, not your token. Wait
and re-run. Rebuilding during an outage turns a 30-minute wait into a day of cleanup.

## The thresholds are researched, and the gaps are marked

[`context/ad-management-principles.md`](context/ad-management-principles.md) is where the numbers in
`campaign.json` come from. Eight rules, each with a confidence rating, from a research pass that put
25 claims through adversarial verification: 17 survived and 8 were refuted.

It also has two sections most guidance leaves out:

- **Refuted lore** lists popular advice that failed verification, including "never edit a working ad
  set" and "adding a new ad always resets learning".
- **Unanchored zones** lists what could not be verified at all: hook rate thresholds, kill rules,
  Advantage+ versus manual for narrow demographics. The monitor records frequency and CPM and
  applies no threshold to either. Inventing a threshold and presenting it as a rule is worse than
  admitting there isn't one.

## Setup

```bash
mkdir -p meta-ads
cp .env.example meta-ads/.env            # then fill in three values
cp campaign.example.json meta-ads/campaign.json
PYTHONPATH=. python3 -m metaads check
```

`/meta-ads:connect` walks the Business Settings side of this, which is the fiddly part:
[`context/connecting-your-account.md`](context/connecting-your-account.md).

Config lives in `meta-ads/` in your project, or `~/.meta-ads/`, or wherever `$META_ADS_HOME` points.
Deliberately never inside the plugin, because a plugin directory is replaced on update and that
would silently delete your token.

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

85 tests, no dependencies, no network, no ad account needed. `tests/fake_graph.py` is an in-memory
Graph API that records every call, so the tests assert on the exact payloads that would go to Meta.
It refuses writes when asked to, which is what makes the read-only guarantee testable rather than
aspirational.

Four bugs were found by the tests and by review rather than by running the code:

- Nested fields were being form-encoded as Python's `repr`, so `targeting` went out with single
  quotes instead of JSON and Meta would have rejected every write. Now handled once, in the client,
  rather than at each call site where it can be forgotten.
- `float(20.005) * 100` is `2000.4999...`, which rounds budgets to the wrong cent. Now `Decimal`.
- The thumbnail hash was read from the top level of the `/adimages` response, where it does not
  exist, and defaulted to `""`, so a creative would have been built with no image. It now reads
  the real nested shape and raises if it is missing.
- Three fields Meta requires but does not clearly ask for were missing, so a first publish would
  have hit errors that had already been solved once.

## Layout

| Path | What |
|---|---|
| `metaads/graph.py` | The only module that talks to Meta. Error classification lives here. |
| `metaads/config.py` | Loading credentials and settings, and refusing to guess |
| `metaads/publish.py` | The seven publish steps, dry run and resume |
| `metaads/update.py` | Copy and lead form changes, both create-and-swap |
| `metaads/pulse.py` | The read-only monitor. `evaluate()` is pure, so it is easy to test. |
| `skills/` | The Claude Code commands |
| `context/` | The setup guide, the API notes, the research behind the thresholds |
| `tests/` | 85 tests including `fake_graph.py` |

## Honest limits

- **Verified against one ad account.** The payload construction is covered by tests, and the
  workflows have run against a real live campaign. But "clone this and it works on your account"
  has not been proven across several accounts, and Meta's behaviour varies by account age, spend
  history and region.
- **Lead-objective campaigns with instant forms and a vertical video.** Other objectives and
  formats are not wired up.
- **The benchmark band ships as US lead-objective medians.** They are a starting point for a small
  budget, not a target, and you should replace them with your own vertical's numbers.
- **Pinned to Graph API v21.0.** Meta auto-upgrades old versions, which can change behaviour without
  warning. Bump it deliberately and run the tests first.

## Licence

MIT. See [LICENSE](LICENSE).
