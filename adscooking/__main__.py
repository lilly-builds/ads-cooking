"""Command line entry point: python3 -m adscooking <command>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .check import run_check
from .config import ConfigError, config_dir, load_campaign, require_env
from .graph import Graph, GraphError
from .publish import publish
from .setup import (missing_values, python_ready, render_links, scaffold,
                    setup_links)
from .pulse import (EXIT_CODES, append_history, evaluate, gather, read_state,
                    render, snapshot_state, worst, write_state)
from .update import update_copy, update_form


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adscooking",
        description="Run a Meta lead campaign. Reads are free; writes need --go.",
    )
    parser.add_argument("--version", action="version", version=f"ads-cooking {__version__}")
    parser.add_argument("--config-dir", type=Path, default=None,
                        help="Where campaign.json and .env live (default: ./ads-cooking or ~/.ads-cooking)")
    sub = parser.add_subparsers(dest="command", required=True)

    connect_cmd = sub.add_parser(
        "connect", help="Set the config folder up and print the Meta steps, with links")
    connect_cmd.add_argument("--business-id", default=None,
                             help="Business Portfolio id, from business.facebook.com/settings/info")
    connect_cmd.add_argument("--page-id", default=None, help="Facebook Page id")
    connect_cmd.add_argument("--app-id", default=None, help="App id, once the app exists")

    sub.add_parser("check", help="Prove the token reaches the account, page and forms")

    publish_cmd = sub.add_parser("publish", help="Create the campaign (dry run unless --go)")
    publish_cmd.add_argument("--go", action="store_true",
                             help="Actually create it. Everything still lands PAUSED.")

    copy_cmd = sub.add_parser("copy", help="Swap in new ad copy on the live ad")
    copy_cmd.add_argument("--go", action="store_true", help="Actually make the change")

    form_cmd = sub.add_parser("form", help="Publish a changed lead form (creates a new one)")
    form_cmd.add_argument("--go", action="store_true", help="Actually make the change")

    sub.add_parser("pulse", help="One read-only check of the live campaign")
    return parser


# Exit codes. 0/1/2 are the campaign verdict, so a setup problem gets its own
# code: a caller polling this must not read "your .env is missing" as "your
# ads are in trouble".
SETUP_PROBLEM = 3

# The .env.example and campaign.example.json that `connect` copies live beside
# the package, both in a clone and in an installed plugin.
PACKAGE_ROOT = Path(__file__).resolve().parent.parent

# What each command actually reads out of the `live` section. Checking only
# ad_id would let copy run and fail mid-way on a blank video_id.
NEEDS_LIVE = {
    "copy": ("ad_id", "video_id", "thumbnail_hash", "form_id"),
    "form": ("ad_id", "video_id", "thumbnail_hash"),
    "pulse": ("campaign_id", "ad_set_id", "ad_id"),
}


def missing_live_ids(config: dict, command: str) -> list[str]:
    live = config.get("live") or {}
    return [key for key in NEEDS_LIVE.get(command, ()) if not live.get(key)]


def run_connect(args, directory) -> int:
    """Offline. Creates the folder, then prints the steps only a person can do.

    Deliberately does not reach Meta and deliberately does not ask for the token:
    the token is generated in a browser, shown once, and pasted into a file. It
    never travels through this command, or through a chat.
    """
    ready, note = python_ready()
    print(note)
    if not ready:
        return SETUP_PROBLEM

    print("\nSetting up your config folder.")
    created = scaffold(directory, PACKAGE_ROOT)
    for line in created.lines:
        print(line)

    print("\nThe Meta steps. These are yours: each one is a legal agreement, a "
          "password,\nor a key that is shown once. Work down the list.\n")
    print(render_links(setup_links(args.business_id, args.page_id, args.app_id)))

    # Before anything else, and regardless of whether the values are filled in.
    # A committable secrets file that reports success is worse than one that
    # reports nothing: it is the failure this whole command exists to prevent.
    if created.blocked:
        print("\nStopping here. Fix the .gitignore above, then run this again.")
        return SETUP_PROBLEM

    still_blank = missing_values(directory)
    print()
    if still_blank:
        print(f"Then fill these into {directory / '.env'}: {', '.join(still_blank)}")
        print("Paste the token straight into that file. Not into this chat, not into a doc.")
        print("\nWhen they are in, run: check")
        return SETUP_PROBLEM
    print("All three values are filled in. Run `check` to prove they reach Meta.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    directory = args.config_dir or config_dir()

    # Before require_env, on purpose. connect is what you run when there is no
    # .env, so it cannot be behind a check for one.
    if args.command == "connect":
        return run_connect(args, directory)

    try:
        env = require_env(directory)
    except ConfigError as exc:
        print(f"{exc}", file=sys.stderr)
        return SETUP_PROBLEM

    try:
        if args.command == "check":
            return run_check(Graph(env["META_SYSTEM_USER_TOKEN"]), env)

        if args.command == "publish":
            config = load_campaign(directory)
            publish(config, env, go=args.go, base_dir=directory,
                    resume=config.get('live'))
            return 0

        if args.command in ("copy", "form", "pulse"):
            config = load_campaign(directory)
            missing = missing_live_ids(config, args.command)
            if missing:
                print(f"campaign.json is missing these ids in its 'live' section: "
                      f"{', '.join(missing)}.\nRun `publish --go` first, then paste in "
                      f"the ids it prints.", file=sys.stderr)
                return SETUP_PROBLEM

        if args.command in ("copy", "form"):
            live = config["live"]
            if not args.go:
                which = "copy" if args.command == "copy" else "lead form"
                print(f"Dry run. This would create a new creative and point the live ad at it,\n"
                      f"changing the {which}. Nothing was sent. Re-run with --go to do it.")
                return 0
            api = Graph(env["META_SYSTEM_USER_TOKEN"])
            handler = update_copy if args.command == "copy" else update_form
            handler(config, env, live, api)
            return 0

        if args.command == "pulse":
            config = load_campaign(directory)
            api = Graph(env["META_SYSTEM_USER_TOKEN"])
            monitor = dict(config["monitor"])
            monitor["account_id"] = env["META_AD_ACCOUNT_ID"]
            monitor["ids"] = config["live"]

            state_path = directory / "pulse-state.json"
            snapshot = gather(api, monitor)
            findings = evaluate(snapshot, monitor, read_state(state_path))
            print(render(findings, snapshot))
            write_state(state_path, snapshot_state(snapshot))
            append_history(directory / "pulse-history.jsonl", snapshot, findings)
            return EXIT_CODES[worst(findings)]

    except ConfigError as exc:
        print(f"{exc}", file=sys.stderr)
        return SETUP_PROBLEM
    except GraphError as exc:
        print(f"Meta returned an error: {exc.message}\n\n{exc.explain()}", file=sys.stderr)
        return SETUP_PROBLEM
    except FileNotFoundError as exc:
        print(f"{exc}", file=sys.stderr)
        return SETUP_PROBLEM
    return 0


if __name__ == "__main__":
    sys.exit(main())
