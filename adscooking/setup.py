"""Everything that happens before the first call to Meta.

Three jobs, all offline:

  1. Say whether this machine can run the kit at all.
  2. Create the config folder, and prove the secrets file is hidden from git.
  3. Turn a Business Portfolio id into the exact Meta URLs for each setup step.

The reason this is code and not a paragraph in a skill file: the steps here are
the ones that are unrecoverable when skipped. A token committed to git cannot be
un-committed, and "the assistant was told to check .gitignore" is not the same
guarantee as a check that runs. The rest of the kit already works this way; the
setup did not.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from .config import CONFIG_FILENAME, ENV_FILENAME, REQUIRED_ENV, load_env

MIN_PYTHON = (3, 10)

# The seven the token needs. Fewer than these and setup appears to succeed, then
# fails later at a step that never mentions a missing scope.
SCOPES = (
    "ads_management",
    "ads_read",
    "business_management",
    "leads_retrieval",
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_ads",
)


def python_ready(version: tuple[int, ...] | None = None) -> tuple[bool, str]:
    """Is the interpreter new enough, and if not, what does the user do?

    Checked first, before anything else, because on a Mac that has never had
    developer tools installed `python3` is a stub that opens an Apple installer
    dialog. Without this the first thing a new user meets is that dialog rather
    than a sentence from us.
    """
    version = version or sys.version_info[:2]
    if tuple(version[:2]) >= MIN_PYTHON:
        return True, f"Python {version[0]}.{version[1]} is fine."
    return False, (
        f"This needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer, and this machine has "
        f"{version[0]}.{version[1]}.\n"
        "  On a Mac: install the developer tools with `xcode-select --install`, or get a\n"
        "  current Python from https://www.python.org/downloads/. Nothing else is needed:\n"
        "  no pip install, no virtualenv."
    )


def git_ignores(path: Path) -> bool | None:
    """Is this path hidden from git?

    True yes, False no, None only when there is genuinely no repository here.

    The distinction matters more than it looks. `git rev-parse` exits 128 both
    for "not a git repository" and for a repository it refuses to touch, such as
    one owned by another user (`safe.directory`). Treating every 128 as "no
    repository" turns a folder git *would* commit into a reassuring line of
    output, on the one check in this codebase that cannot be undone. So only the
    message that actually says so counts as no repository; anything else we
    could not establish is reported as unsafe.
    """
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path.parent, capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        # No git on this machine at all, so nothing can commit anything.
        return None
    except (OSError, subprocess.SubprocessError):
        return False

    if inside.returncode != 0:
        return None if "not a git repository" in (inside.stderr or "").lower() else False
    if inside.stdout.strip() != "true":
        return None

    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=path.parent, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    # 0 ignored, 1 not ignored, anything else is an error we must not read as a pass.
    return result.returncode == 0 if result.returncode in (0, 1) else False


class Scaffolded(NamedTuple):
    """What happened, and whether it is safe to carry on.

    `blocked` exists because the dangerous case is silent: a config folder that
    is inside a git repository and not ignored looks completely normal, and the
    only signal is a line of output. A caller must be able to act on it rather
    than print it and move on.
    """

    lines: list[str]
    blocked: bool


def scaffold(directory: Path, examples: Path) -> Scaffolded:
    """Create the config folder, and lock the secrets file down.

    Never overwrites: re-running this on a working setup must not be the way
    somebody loses a token.
    """
    lines: list[str] = []
    blocked = False
    directory = Path(directory).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, stat.S_IRWXU)

    for source_name, target_name in ((".env.example", ENV_FILENAME),
                                     ("campaign.example.json", CONFIG_FILENAME)):
        target = directory / target_name
        if target.exists():
            lines.append(f"  Kept your existing {target_name}. Nothing was overwritten.")
            continue
        shutil.copyfile(Path(examples) / source_name, target)
        lines.append(f"  Created {target_name}.")

    env_path = directory / ENV_FILENAME
    # Owner read/write only. The other files here are settings; this one is a
    # key to somebody's advertising budget.
    os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
    lines.append(f"  Locked {ENV_FILENAME} to you only.")

    ignored = git_ignores(env_path)
    if ignored is True:
        lines.append("  Git is ignoring it, so it cannot be committed by accident.")
    elif ignored is False:
        blocked = True
        lines.append(
            f"  STOP. {env_path} is inside a git repository and is NOT ignored.\n"
            f"  Add `{directory.name}/` to that repository's .gitignore before you put a\n"
            f"  token in it. A token in git history is the one mistake here you cannot undo."
        )
    else:
        lines.append("  Not inside a git repository, so there is nothing to commit it to.")

    lines.append(f"\n  It all lives in {directory}")
    return Scaffolded(lines, blocked)


def missing_values(directory: Path) -> list[str]:
    """Which of the three required values are still blank. Values never printed."""
    try:
        values = load_env(Path(directory))
    except Exception:
        return list(REQUIRED_ENV)
    return [key for key in REQUIRED_ENV
            if not values.get(key) or values[key].startswith("<")]


# Every URL below is one of these. The rule exists because the first version of
# this list deep-linked to four Business Settings sections written from memory,
# and a link that 404s is worse than the "go and find it" instruction it
# replaced: it costs the same time and it also makes the tool look wrong.
#
# So a deep link goes in here only once someone has opened it. Meta renames
# these sections, and it moves them between Business Manager and Business Suite.
# Anything not checked gets the Business Settings root, which lands in the right
# portfolio, plus the sidebar clicks in words.
VERIFIED_PATHS = (
    # developers.facebook.com/docs/marketing-api/system-users/create-retrieve-update
    "https://business.facebook.com/settings/system-users",
    # No path at all: the SPA root, which cannot be renamed out from under us.
    "https://business.facebook.com/settings",
    # Both were in this repo before, written from a real end-to-end setup.
    "https://developers.facebook.com/apps/",
    "https://www.facebook.com/legal/leadgen/tos/",
    # Landing pages, not deep links.
    "https://developers.facebook.com/",
    "https://www.facebook.com/business/help/",
    "https://adsmanager.facebook.com",
)


def setup_links(business_id: str | None = None,
                page_id: str | None = None,
                app_id: str | None = None) -> list[tuple[str, str, str]]:
    """The setup steps in order, as (what, where, why) with the ids filled in.

    The Business Portfolio id is asked for first because almost every later URL
    is scoped to it. Without it a user is told to "go to Business Settings and
    find X", which is where the time goes; with it, each step is a link.

    An id that is not known yet leaves a visible <placeholder> in the URL rather
    than a broken link, so it is obvious what still has to be filled in.
    """
    business = business_id or "<BUSINESS_ID>"
    page = page_id or "<PAGE_ID>"
    app = app_id or "<APP_ID>"
    settings = "https://business.facebook.com/settings"
    scoped = f"{settings}?business_id={business}" if business_id else settings
    scopes = ", ".join(SCOPES)

    return [
        (
            "Find your Business Portfolio id",
            settings,
            "Business info in the left sidebar. The number under your portfolio name. "
            "Every link below is scoped to it, so it comes first.",
        ),
        (
            "Accept the developer terms",
            "https://developers.facebook.com/",
            "A legal agreement, so it has to be you. One click, once per account.",
        ),
        (
            "Create the app",
            "https://developers.facebook.com/apps/creation/",
            "Type 'Business'. It will ask for your password. Note the App ID it gives you.",
        ),
        (
            "Create a system user",
            f"{settings}/system-users?business_id={business}",
            "Add, name it, role Admin. This is what keeps the connection alive when a "
            "person changes their password or leaves.",
        ),
        (
            "Give the system user the ad account",
            scoped,
            "Left sidebar, Accounts, Ad accounts. Pick the account, Assign people, your "
            "system user, Manage campaigns. Your ad account id is on this screen too, and "
            "it is the number in the panel, not the one in the address bar.",
        ),
        (
            "Give the system user the Page",
            scoped,
            "Left sidebar, Accounts, Pages. Pick the Page, Assign people, your system user, "
            "MANAGE or ADVERTISE. Skipping this is the most common mistake here: everything "
            "works until lead forms, which live on the Page, not the account.",
        ),
        (
            "Generate the token",
            f"{settings}/system-users?business_id={business}",
            f"Your system user, Generate token, pick the app, tick all seven: {scopes}. "
            "Meta shows it once. Paste it straight into .env, not into chat.",
        ),
        (
            "Set a privacy policy and take the app Live",
            f"https://developers.facebook.com/apps/{app}/settings/basic/",
            "A development-mode app cannot create ad creatives, and the failure only shows "
            "up at the last step of your first publish, after the video has uploaded.",
        ),
        (
            "Accept the lead ads terms for the Page",
            f"https://www.facebook.com/legal/leadgen/tos/?page_id={page}",
            "One click, once per Page. Without it, creating a lead form fails with "
            "'Terms of Service Not Accepted'.",
        ),
    ]


def render_links(steps: list[tuple[str, str, str]]) -> str:
    out = []
    for number, (what, where, why) in enumerate(steps, start=1):
        out.append(f"  {number}. {what}\n     {where}\n     {why}")
    return "\n\n".join(out)
