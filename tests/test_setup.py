"""The setup path, which is where the unrecoverable mistakes live.

A token committed to git cannot be un-committed, so the checks that prevent it
have to be assertions, not instructions in a skill file that a model may or may
not follow on any given run.
"""

import contextlib
import io
import os
import socket
import stat
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from adscooking.__main__ import SETUP_PROBLEM, main
from adscooking.check import CAMPAIGN_PROBLEM, OK, run_check
from adscooking.check import SETUP_PROBLEM as CHECK_SETUP_PROBLEM
from adscooking.graph import GraphError
from adscooking.setup import (MIN_PYTHON, SCOPES, VERIFIED_PATHS, git_ignores,
                              missing_values, python_ready, render_links, scaffold,
                              setup_links)
from tests.fake_graph import FakeGraph

REPO = Path(__file__).resolve().parent.parent
TOKEN = "EAAsecretvaluethatmustneverbeprinted"


class TestPythonGuard(unittest.TestCase):
    """The first thing a new user meets on a Mac without developer tools."""

    def test_an_old_interpreter_is_refused_with_the_fix(self):
        ok, note = python_ready((3, 9))
        self.assertFalse(ok)
        self.assertIn("xcode-select --install", note)

    def test_a_current_interpreter_passes(self):
        self.assertTrue(python_ready(MIN_PYTHON)[0])
        self.assertTrue(python_ready((3, 14))[0])


class TestScaffold(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "ads-cooking"

    def test_it_creates_both_files_and_says_where(self):
        lines = "\n".join(scaffold(self.dir, REPO).lines)
        self.assertTrue((self.dir / ".env").is_file())
        self.assertTrue((self.dir / "campaign.json").is_file())
        self.assertIn(str(self.dir), lines)

    def test_the_secrets_file_is_readable_only_by_its_owner(self):
        scaffold(self.dir, REPO)
        mode = stat.S_IMODE(os.stat(self.dir / ".env").st_mode)
        self.assertEqual(mode, 0o600)

    def test_rerunning_it_never_overwrites_a_token(self):
        """Re-running setup must not be how somebody loses a working key."""
        scaffold(self.dir, REPO)
        (self.dir / ".env").write_text(f"META_SYSTEM_USER_TOKEN={TOKEN}\n")
        scaffold(self.dir, REPO)
        self.assertIn(TOKEN, (self.dir / ".env").read_text())

    def test_it_stops_you_when_the_folder_is_in_git_and_not_ignored(self):
        repo = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(repo)], check=True,
                       capture_output=True)
        result = scaffold(repo / "ads-cooking", REPO)
        lines = "\n".join(result.lines)
        self.assertIn("STOP", lines)
        self.assertIn("gitignore", lines)
        self.assertTrue(result.blocked, "a committable secrets file must be a blocker")

    def test_it_is_satisfied_when_the_folder_is_ignored(self):
        repo = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(repo)], check=True,
                       capture_output=True)
        (repo / ".gitignore").write_text("ads-cooking/\n")
        result = scaffold(repo / "ads-cooking", REPO)
        lines = "\n".join(result.lines)
        self.assertNotIn("STOP", lines)
        self.assertIn("cannot be committed", lines)
        self.assertFalse(result.blocked)

    def test_outside_a_repository_it_says_so_rather_than_passing_silently(self):
        lines = "\n".join(scaffold(self.dir, REPO).lines)
        self.assertIn("Not inside a git repository", lines)

    def test_git_ignores_returns_none_outside_a_repository(self):
        self.assertIsNone(git_ignores(Path(tempfile.mkdtemp()) / ".env"))

    def test_a_repository_git_refuses_to_read_is_treated_as_unsafe(self):
        """`git rev-parse` exits 128 for "not a repository" AND for one it will
        not touch, such as a checkout owned by another user. Reading the second
        as the first turns a committable file into a reassuring line of output.
        """
        refused = subprocess.CompletedProcess(
            args=[], returncode=128,
            stdout="", stderr="fatal: detected dubious ownership in repository at '/x'\n")
        with mock.patch.object(subprocess, "run", return_value=refused):
            self.assertIs(git_ignores(Path("/x/ads-cooking/.env")), False)

    def test_no_repository_is_still_reported_as_no_repository(self):
        absent = subprocess.CompletedProcess(
            args=[], returncode=128,
            stdout="", stderr="fatal: not a git repository (or any of the parent directories)\n")
        with mock.patch.object(subprocess, "run", return_value=absent):
            self.assertIsNone(git_ignores(Path("/x/ads-cooking/.env")))

    def test_a_check_ignore_error_is_not_read_as_ignored(self):
        confused = subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="boom")
        inside = subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr="")
        with mock.patch.object(subprocess, "run", side_effect=[inside, confused]):
            self.assertIs(git_ignores(Path("/x/ads-cooking/.env")), False)

    def test_missing_values_names_the_blanks_and_never_the_values(self):
        scaffold(self.dir, REPO)
        self.assertEqual(len(missing_values(self.dir)), 3)
        (self.dir / ".env").write_text(
            f"META_SYSTEM_USER_TOKEN={TOKEN}\nMETA_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n")
        self.assertEqual(missing_values(self.dir), [])


class TestSetupLinks(unittest.TestCase):
    def test_the_business_id_fills_in_every_link_scoped_to_it(self):
        rendered = render_links(setup_links(business_id="999999999999999"))
        self.assertIn("business_id=999999999999999", rendered)
        self.assertNotIn("<BUSINESS_ID>", rendered)

    def test_an_unknown_id_stays_an_obvious_placeholder(self):
        """A half-filled URL that looks complete is worse than one that does not."""
        rendered = render_links(setup_links())
        self.assertIn("<BUSINESS_ID>", rendered)
        self.assertIn("<PAGE_ID>", rendered)
        self.assertIn("<APP_ID>", rendered)

    def test_the_business_id_step_comes_first(self):
        self.assertIn("Business Portfolio id", setup_links()[0][0])

    def test_all_seven_scopes_are_named_at_the_token_step(self):
        """A token short one scope works until it suddenly does not."""
        rendered = render_links(setup_links())
        for scope in SCOPES:
            self.assertIn(scope, rendered)
        self.assertEqual(len(SCOPES), 7)

    def test_the_page_task_step_is_present_and_explains_why(self):
        rendered = render_links(setup_links())
        self.assertIn("MANAGE or ADVERTISE", rendered)

    def test_every_link_is_one_somebody_has_actually_opened(self):
        """The guard on the mistake that produced this list's first version.

        Four Business Settings sections were deep-linked from memory. A link
        that 404s costs the user the same time as no link and also makes the
        tool look wrong, so a deep link earns its place only once it has been
        checked. Adding one means opening it and adding it to VERIFIED_PATHS.
        """
        for what, url, _ in setup_links("999999999999999", "888888888888888",
                                        "123456789012345"):
            self.assertTrue(
                any(url.startswith(prefix) for prefix in VERIFIED_PATHS),
                f"'{what}' links to {url}, which is not in VERIFIED_PATHS. "
                f"Open it first, then add its prefix there.")

    def test_unchecked_business_settings_sections_are_not_deep_linked(self):
        """Named explicitly, because these three are the ones that were wrong."""
        rendered = render_links(setup_links("999999999999999"))
        for guess in ("/settings/info", "/settings/ad-accounts", "/settings/ad_accounts",
                      "/settings/pages"):
            self.assertNotIn(guess, rendered)

    def test_the_unlinkable_steps_say_where_to_click_instead(self):
        """Dropping the deep link must not drop the directions with it."""
        rendered = render_links(setup_links("999999999999999"))
        self.assertIn("Accounts, Ad accounts", rendered)
        self.assertIn("Accounts, Pages", rendered)
        self.assertIn("Business info in the left sidebar", rendered)

    def test_the_lead_terms_link_carries_the_page_id(self):
        rendered = render_links(setup_links(page_id="888888888888888"))
        self.assertIn("leadgen/tos/?page_id=888888888888888", rendered)


class TestConnectCommand(unittest.TestCase):
    def run_connect(self, directory, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(["--config-dir", str(directory), "connect", *extra])
        return code, out.getvalue()

    def test_it_runs_with_no_env_at_all(self):
        """connect is what you run when nothing is set up, so it cannot need a .env."""
        code, out = self.run_connect(Path(tempfile.mkdtemp()) / "ads-cooking")
        self.assertEqual(code, SETUP_PROBLEM)
        self.assertIn("Created .env", out)

    def test_it_reports_done_once_the_values_are_in(self):
        directory = Path(tempfile.mkdtemp()) / "ads-cooking"
        self.run_connect(directory)
        (directory / ".env").write_text(
            f"META_SYSTEM_USER_TOKEN={TOKEN}\nMETA_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n")
        code, out = self.run_connect(directory)
        self.assertEqual(code, 0)
        self.assertIn("Run `check`", out)

    def test_a_committable_secrets_file_is_never_a_clean_exit(self):
        """The hole this closes: it printed STOP and exited 0 saying all was well.

        Filling in all three values must not be able to override the git check.
        That combination is a real token sitting in a file git will commit.
        """
        repo = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
        directory = repo / "ads-cooking"
        directory.mkdir()
        (directory / ".env").write_text(
            f"META_SYSTEM_USER_TOKEN={TOKEN}\nMETA_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n")
        code, out = self.run_connect(directory)
        self.assertEqual(code, SETUP_PROBLEM)
        self.assertIn("STOP", out)
        self.assertNotIn("Run `check`", out)
        self.assertNotIn(TOKEN, out)

    def test_it_never_prints_the_token(self):
        """The one output rule that matters here."""
        directory = Path(tempfile.mkdtemp()) / "ads-cooking"
        self.run_connect(directory)
        (directory / ".env").write_text(
            f"META_SYSTEM_USER_TOKEN={TOKEN}\nMETA_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n")
        _, out = self.run_connect(directory, "--business-id", "999999999999999")
        self.assertNotIn(TOKEN, out)

    def test_it_sends_nothing_to_meta(self):
        """Offline by construction, asserted by taking the network away.

        Grepping the function body for `Graph(` would pass for a call added in
        setup.py or reached through any helper. Breaking the socket does not.
        """
        directory = Path(tempfile.mkdtemp()) / "ads-cooking"

        def no_network(*args, **kwargs):
            raise AssertionError("connect must not touch the network")

        with mock.patch.object(socket, "socket", no_network), \
                mock.patch.object(socket, "create_connection", no_network):
            code, out = self.run_connect(directory)
        self.assertEqual(code, SETUP_PROBLEM)
        self.assertIn("Created .env", out)


class TestCheckExitCodes(unittest.TestCase):
    """A dead key is a setup problem. It must not read as the ads being in trouble."""

    ENV = {"META_AD_ACCOUNT_ID": "act_1", "META_PAGE_ID": "2"}

    def run_check(self, api):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = run_check(api, self.ENV)
        return code, out.getvalue()

    def test_a_dead_token_is_a_setup_problem_not_a_campaign_problem(self):
        class Dead(FakeGraph):
            def get(self, path, **params):
                raise GraphError(path, 400, '{"error":{"message":"expired"}}')

        code, _ = self.run_check(Dead())
        self.assertEqual(code, CHECK_SETUP_PROBLEM)
        self.assertNotEqual(code, CAMPAIGN_PROBLEM)

    def test_a_working_setup_exits_clean(self):
        api = FakeGraph({"me": {"name": "sys"},
                         "act_1": {"name": "Acme", "account_status": 1, "currency": "USD"},
                         "2": {"name": "Acme Page"},
                         "leadgen_forms": {"data": []}})
        code, _ = self.run_check(api)
        self.assertEqual(code, OK)

    def test_it_tells_you_the_date_the_token_expires(self):
        """pulse warns 14 days out, but only on a token that still works.

        Seeded on purpose. An unseeded FakeGraph returns an empty debug_token
        payload, which reads as "never expires", so a test that accepts either
        branch never exercises the date at all.
        """
        expires = datetime.now(timezone.utc) + timedelta(days=45)
        api = FakeGraph({"me": {"name": "sys"},
                         "act_1": {"name": "Acme", "account_status": 1, "currency": "USD"},
                         "2": {"name": "Acme Page"},
                         "leadgen_forms": {"data": []},
                         "debug_token": {"data": {"expires_at": int(expires.timestamp())}}})
        _, out = self.run_check(api)
        self.assertIn("expires in 44 days", out)
        self.assertIn(expires.strftime("%-d %B %Y"), out)
        self.assertIn("Write that date down", out)

    def test_a_token_that_never_expires_says_so_rather_than_showing_a_date(self):
        api = FakeGraph({"me": {"name": "sys"},
                         "act_1": {"name": "Acme", "account_status": 1, "currency": "USD"},
                         "2": {"name": "Acme Page"},
                         "leadgen_forms": {"data": []},
                         "debug_token": {"data": {}}})
        _, out = self.run_check(api)
        self.assertIn("does not expire", out)

    def test_the_expiry_line_never_fails_the_check(self):
        class NoDebug(FakeGraph):
            def debug_self(self):
                raise GraphError("debug_token", 400, '{"error":{"message":"nope"}}')

        api = NoDebug({"me": {"name": "sys"},
                       "act_1": {"name": "Acme", "account_status": 1, "currency": "USD"},
                       "2": {"name": "Acme Page"},
                       "leadgen_forms": {"data": []}})
        code, out = self.run_check(api)
        self.assertEqual(code, OK)
        self.assertIn("Could not read its expiry", out)


if __name__ == "__main__":
    unittest.main()
