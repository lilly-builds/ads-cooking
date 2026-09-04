"""Loading credentials and campaign settings, and refusing to guess.

The rule here is worth stating plainly, because breaking it is how tools like
this end up writing to the wrong ad account: a missing value is an error, never
a default. There is no fallback account ID anywhere in this codebase. If the
environment is not set up, every command stops before it reaches Meta.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIRNAME = "meta-ads"
CONFIG_FILENAME = "campaign.json"
ENV_FILENAME = ".env"

REQUIRED_ENV = (
    "META_SYSTEM_USER_TOKEN",
    "META_AD_ACCOUNT_ID",
    "META_PAGE_ID",
)


class ConfigError(Exception):
    """Raised before any network call when the setup is incomplete."""


def config_dir(start: Path | None = None) -> Path:
    """Where this machine's campaign settings and secrets live.

    Deliberately NOT inside the plugin. A plugin directory is replaced wholesale
    on update, which would silently delete a token. Order of preference:

      1. $META_ADS_HOME, for anyone who wants it somewhere specific
      2. ./meta-ads/ in the current project
      3. ~/.meta-ads/
    """
    override = os.environ.get("META_ADS_HOME")
    if override:
        return Path(override).expanduser()

    local = (start or Path.cwd()) / CONFIG_DIRNAME
    if local.is_dir():
        return local
    return Path.home() / f".{CONFIG_DIRNAME}"


def load_env(directory: Path | None = None) -> dict:
    """Read KEY=VALUE lines. Values are never logged or echoed."""
    directory = directory or config_dir()
    path = directory / ENV_FILENAME
    if not path.is_file():
        raise ConfigError(
            f"No credentials file at {path}.\n"
            f"Run /meta-connect to set one up, or copy .env.example there and fill it in."
        )

    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def require_env(directory: Path | None = None) -> dict:
    """Load the environment and fail loudly on anything missing or unfilled."""
    values = load_env(directory)
    missing = [
        key
        for key in REQUIRED_ENV
        if not values.get(key) or values[key].startswith("<")
    ]
    if missing:
        raise ConfigError(
            "These values are missing from your .env file: "
            + ", ".join(missing)
            + "\nNothing was sent to Meta. Fill them in and re-run."
        )

    account = values["META_AD_ACCOUNT_ID"]
    if not account.startswith("act_"):
        values["META_AD_ACCOUNT_ID"] = f"act_{account}"
    return values


def load_campaign(directory: Path | None = None) -> dict:
    """Read campaign.json, the settings-as-data file."""
    directory = directory or config_dir()
    path = directory / CONFIG_FILENAME
    if not path.is_file():
        raise ConfigError(
            f"No campaign settings at {path}.\n"
            f"Copy campaign.example.json there and edit it."
        )
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc}") from None
