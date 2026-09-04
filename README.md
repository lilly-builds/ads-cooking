# ads-cooking

Run your Meta ads by talking to Claude Code.

You say what you want. Claude builds the campaign, writes the lead form, and checks how it's doing every morning. You approve everything before a dollar moves.

Built for people who can follow instructions but do not want to learn the Meta Marketing API.

## Install

```
/plugin marketplace add lilly-builds/ads-cooking
/plugin install ads-cooking@ads-cooking
```

That's it. No pip install. No virtualenv. No packages to download.

You need Python 3.10 or newer. Most Macs have it. To check, open Terminal and type `python3 --version`. If it says something older, or pops up a box asking to install developer tools, say yes to the box, or grab a current Python from [python.org](https://www.python.org/downloads/). The setup command checks this for you and tells you the same thing.

## Start here

Open Claude Code in any folder and type:

```
/ads-cooking:start
```

Then tell it about your ads in plain English. Something like:

> I sell an error tracking tool for dev teams. $99 a month. I want demo requests
> from engineering managers. Start with the US, UK, Canada, Germany and Australia.
> Budget is $30 a day. I have a 30 second demo video. Here's my pricing page: example.com

Claude takes it from there. It figures out where you are, sets up your account connection, and walks you through the parts only you can do. It stops and asks before anything spends money.

First time, it will hand you a few jobs in the Meta dashboard. Accepting Meta's terms. Making the login key. Flipping your app to Live. Turning the ads on at the end. Claude gives you the exact link and the exact buttons for each one. It cannot do these for you, and it should not.

It asks for one number before the rest: your Business Portfolio ID. Nearly every link after that is built around it, so with it in hand each step is a link that lands on the right screen, instead of "go find this somewhere in Business Settings." That is where the setup time normally goes.

## The seven commands

| Type this | What happens |
|---|---|
| `/ads-cooking:start` | Not sure where to begin? Start here. It figures it out. |
| `/ads-cooking:connect` | Hooks up your Meta account. Once, at the beginning. |
| `/ads-cooking:check` | Is everything still connected? Run this when something feels off. |
| `/ads-cooking:publish` | Builds the campaign. Shows you first. Creates nothing until you say go. |
| `/ads-cooking:copy` | Change the words on a running ad. |
| `/ads-cooking:form` | Change what the form asks people. |
| `/ads-cooking:pulse` | How much did I spend? How many leads? What did each one cost? |

Most days you only need `pulse`.

## Your money is safe here

This tool can spend your ad budget. So it is built to make that hard to do by accident.

**Nothing happens until you say go.** Run `publish` and it shows you what it would do. It sends nothing. You read it, then you decide.

```
Check these before you run it for real:

  Budget      $30.00 a day, about $900 a month
  Audience    all genders, 25 to 65, in US, GB, CA, DE, AU
  Placements  facebook, instagram
  Copy        3 primary texts, 2 headlines
  Leads go to the instant form 'Lead form v1'

  Warning: the lead form still points at example.com for its privacy
  policy. Meta will reject the form. Set a real URL first.
```

**Every ad starts paused.** Even after you say go. Nothing runs until you open Meta, look at your ad, and turn it on yourself. There is no code in here that can turn an ad on. A test checks for that.

**The morning check can only look.** It reads your numbers. It cannot change your budget, your ad, or your targeting. There is no code in it that writes to Meta at all.

**It never guesses which account you meant.** If your setup is missing something, it stops before it talks to Meta. It will not fall back to some other account ID.

**Your login key stays hidden.** Never printed. Never pasted into chat. Never in a file you'd share by accident. Setup locks the file to your account only and actually runs the check that git is ignoring it, rather than trusting that somebody remembered to.

**You get told when the key dies.** Setup prints the expiry date so you can write it down, and the morning check warns you 14 days out. A key that quietly expires means your ads keep running while every command here stops, which is a bad month to find out about late.

## Four things Meta will not tell you

These cost real hours to find out.

**You cannot edit a lead form.** Once it's live, it's frozen. Changing one question means making a whole new form and pointing your ad at it. Three steps for what feels like one. `/ads-cooking:form` does all three.

**You cannot edit an ad's creative either.** Same deal. Changing a headline means a new creative and a swap. Your ad keeps its ID though, so it keeps everything Meta learned about who clicks it.

**Lead forms need a different key than the rest.** Your setup works perfectly, right up until the form step, then fails with an error that never mentions why.

**When every call fails at once, Meta is down.** Not you. Not your key. Wait an hour. People rebuild their whole campaign during a Meta outage and turn a coffee break into a lost day.

The full list, with the exact error text and the fix, is in [`context/api-notes.md`](context/api-notes.md).

## Where the numbers come from

`/ads-cooking:pulse` tells you if $40 a lead is bad. That answer came from research, not a guess.

[`context/ad-management-principles.md`](context/ad-management-principles.md) has eight rules, each marked by how much you should trust it. It came from checking 25 popular claims. Seventeen held up. Eight did not.

It also has two lists most ad advice skips.

One is advice that failed the check. "Never edit a working ad set" is in there. So is "adding a new ad always resets learning."

The other is questions nobody could answer. Hook rate thresholds. Kill rules. Advantage+ versus doing it yourself. The morning check records those numbers and refuses to judge them, because making up a rule and calling it research is worse than saying you don't know.

## If you want to look under the hood

Clone it and run the tests. No account needed, no internet needed.

```bash
git clone https://github.com/lilly-builds/ads-cooking
cd ads-cooking
python3 -m unittest discover -s tests -t .      # 133 tests
./scripts/check.sh                              # the full gate
```

`tests/fake_graph.py` is a pretend Meta that records every call. So the tests can check exactly what would get sent, without an ad account and without spending anything.

Four bugs showed up this way instead of on somebody's live campaign:

Nested fields were being sent in Python's format instead of the one Meta reads, so every write would have bounced. Budgets lost a cent to rounding. The thumbnail was read from a spot Meta doesn't put it, and quietly came back empty, which would have built an ad with no picture. And three fields Meta demands but never asks for clearly were missing.

Each fix was checked by putting the bug back and making sure the tests screamed.

## Where things live

Every command is a folder in `skills/`. The folder name is the command name.

| Command | Lives in | Runs |
|---|---|---|
| `/ads-cooking:start` | `skills/start/` | nothing itself, it just points you at the right one |
| `/ads-cooking:connect` | `skills/connect/` | `adscooking/setup.py`, then `check` |
| `/ads-cooking:check` | `skills/check/` | `adscooking/check.py` |
| `/ads-cooking:publish` | `skills/publish/` | `adscooking/publish.py` |
| `/ads-cooking:copy` | `skills/copy/` | `adscooking/update.py` |
| `/ads-cooking:form` | `skills/form/` | `adscooking/update.py` |
| `/ads-cooking:pulse` | `skills/pulse/` | `adscooking/pulse.py` |

The code itself:

| File | What it does |
|---|---|
| `adscooking/graph.py` | The only file that talks to Meta. Everything goes through here. |
| `adscooking/config.py` | Reads your settings and your key. Refuses to guess if something's missing. |
| `adscooking/setup.py` | First-run setup: Python check, config folder, git check, Meta's links |
| `adscooking/publish.py` | Builds the campaign, seven steps, dry run and resume |
| `adscooking/update.py` | Changes copy or the lead form on a live ad |
| `adscooking/pulse.py` | The morning check. Reads only. |
| `adscooking/check.py` | Tests your connection in the order things break |
| `adscooking/__main__.py` | The command line: `python3 -m adscooking <command>` |

And the rest:

| Folder | What's in it |
|---|---|
| `context/` | Setup guide, Meta's gotchas, the research behind the numbers |
| `tests/` | 133 tests across 7 files, plus the pretend Meta they run against |
| `scripts/` | `check.sh` runs everything before you push. `check_docs.py` catches docs that drift from the code. |
| `.claude-plugin/` | The two files that make this installable |

Your settings and your login key live in `ads-cooking/` in your project, or `~/.ads-cooking/`, or wherever `$ADS_COOKING_HOME` says. Never inside the plugin, because plugins get replaced when they update and that would wipe your key.

## What this does not do yet

It has run against one ad account. The tests cover what gets sent to Meta, and it has worked on a live campaign. But "clone this and it works on your account" is not proven across many accounts, and Meta behaves differently depending on account age, spend history, and country.

It handles lead campaigns with instant forms and a vertical video. Other campaign types are not wired up.

The cost-per-lead range it ships with is a US average. Swap in numbers for your own industry before you trust it.

Running several countries at once is fine, but it gives you one blended cost per lead that hides everything. A $12 lead in Poland and a $60 lead in the US average out to something that looks normal and tells you nothing. If a market matters, give it its own ad set so you can see it and set a budget for it.

It's pinned to version 21 of Meta's API. Meta upgrades old versions on its own, which can change behavior without telling you. Bump it on purpose and run the tests first.

## Licence

MIT. See [LICENSE](LICENSE).
