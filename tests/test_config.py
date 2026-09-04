"""Config loading, and the rule that it never guesses.

The bug these tests exist to prevent: a script with `env.get("AD_ACCOUNT", "act_12345")`
in it. That runs happily against whoever's account is baked into the default
when the environment is not set up, and you find out from the billing.
"""

import tempfile
import unittest
from pathlib import Path

from adscooking import config
from adscooking.config import ConfigError, load_campaign, require_env


class ConfigFolder(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def write_env(self, text):
        (self.dir / ".env").write_text(text)


class TestNeverGuesses(ConfigFolder):
    def test_no_env_file_is_an_error(self):
        with self.assertRaises(ConfigError) as caught:
            require_env(self.dir)
        self.assertIn("No credentials file", str(caught.exception))

    def test_missing_token_is_an_error(self):
        self.write_env("META_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n")
        with self.assertRaises(ConfigError) as caught:
            require_env(self.dir)
        self.assertIn("META_SYSTEM_USER_TOKEN", str(caught.exception))

    def test_missing_account_is_an_error_with_no_fallback(self):
        self.write_env("META_SYSTEM_USER_TOKEN=t\nMETA_PAGE_ID=2\n")
        with self.assertRaises(ConfigError) as caught:
            require_env(self.dir)
        self.assertIn("META_AD_ACCOUNT_ID", str(caught.exception))

    def test_unfilled_placeholder_counts_as_missing(self):
        """Someone copies .env.example and only fills in some of it."""
        self.write_env(
            "META_SYSTEM_USER_TOKEN=<paste it here>\n"
            "META_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n"
        )
        with self.assertRaises(ConfigError):
            require_env(self.dir)

    def test_no_account_id_is_hardcoded_anywhere_in_the_package(self):
        """A regression guard, not a style check.

        Every ad account id looks like act_ followed by digits. None should
        appear in the shipped code, only in tests and examples.
        """
        import re
        package = Path(__file__).parent.parent / "adscooking"
        offenders = [
            f"{path.name}: {match}"
            for path in package.glob("*.py")
            for match in re.findall(r"act_\d{4,}", path.read_text())
        ]
        self.assertEqual(offenders, [], f"hardcoded ad account id found: {offenders}")


class TestNormalising(ConfigFolder):
    def test_act_prefix_is_added_when_missing(self):
        self.write_env("META_SYSTEM_USER_TOKEN=t\nMETA_AD_ACCOUNT_ID=12345\nMETA_PAGE_ID=2\n")
        self.assertEqual(require_env(self.dir)["META_AD_ACCOUNT_ID"], "act_12345")

    def test_act_prefix_is_left_alone_when_present(self):
        self.write_env("META_SYSTEM_USER_TOKEN=t\nMETA_AD_ACCOUNT_ID=act_12345\nMETA_PAGE_ID=2\n")
        self.assertEqual(require_env(self.dir)["META_AD_ACCOUNT_ID"], "act_12345")

    def test_comments_and_blank_lines_are_ignored(self):
        self.write_env(
            "# a comment\n\nMETA_SYSTEM_USER_TOKEN=t\n"
            "META_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n"
        )
        self.assertEqual(require_env(self.dir)["META_SYSTEM_USER_TOKEN"], "t")

    def test_a_token_containing_equals_survives(self):
        self.write_env(
            "META_SYSTEM_USER_TOKEN=abc=def==\nMETA_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n"
        )
        self.assertEqual(require_env(self.dir)["META_SYSTEM_USER_TOKEN"], "abc=def==")


class TestCampaignFile(ConfigFolder):
    def test_missing_campaign_file_names_the_fix(self):
        with self.assertRaises(ConfigError) as caught:
            load_campaign(self.dir)
        self.assertIn("campaign.example.json", str(caught.exception))

    def test_broken_json_is_reported_clearly(self):
        (self.dir / "campaign.json").write_text("{not json")
        with self.assertRaises(ConfigError) as caught:
            load_campaign(self.dir)
        self.assertIn("not valid JSON", str(caught.exception))

    def test_the_shipped_example_is_valid(self):
        example = Path(__file__).parent.parent / "campaign.example.json"
        (self.dir / "campaign.json").write_text(example.read_text())
        self.assertIn("campaign", load_campaign(self.dir))


class TestConfigLocation(unittest.TestCase):
    def test_env_var_wins(self):
        import os
        os.environ["ADS_COOKING_HOME"] = "/tmp/somewhere-specific"
        self.addCleanup(os.environ.pop, "ADS_COOKING_HOME", None)
        self.assertEqual(config.config_dir(), Path("/tmp/somewhere-specific"))

    def test_falls_back_to_home_when_no_local_folder(self):
        import os
        os.environ.pop("ADS_COOKING_HOME", None)
        empty = Path(tempfile.mkdtemp())
        self.assertEqual(config.config_dir(empty), Path.home() / ".ads-cooking")


class TestTheShippedExample(unittest.TestCase):
    """.env.example is the setup instructions. It has to match the code.

    Adding a required variable and forgetting the example is the kind of drift
    nobody notices until someone new tries to set the thing up.
    """

    def setUp(self):
        self.example = (Path(__file__).parent.parent / ".env.example").read_text()

    def test_it_lists_every_required_variable(self):
        from adscooking.config import REQUIRED_ENV
        for key in REQUIRED_ENV:
            self.assertIn(f"{key}=", self.example, f"{key} is required but not in .env.example")

    def test_it_lists_no_variable_the_code_ignores(self):
        import re
        declared = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", self.example, re.M))
        from adscooking.config import REQUIRED_ENV
        self.assertEqual(declared, set(REQUIRED_ENV),
                         "the example and the code disagree about which variables exist")

    def test_it_ships_with_no_values_filled_in(self):
        """A committed example with a real value in it is a leaked credential."""
        import re
        for key, value in re.findall(r"^([A-Z][A-Z0-9_]+)=(.*)$", self.example, re.M):
            self.assertEqual(value.strip(), "", f"{key} has a value in the committed example")

    def test_copying_it_unfilled_gives_a_useful_error(self):
        """The real first-run path: copy the example, run something, read the error."""
        from adscooking.config import ConfigError, require_env
        directory = Path(tempfile.mkdtemp())
        (directory / ".env").write_text(self.example)
        with self.assertRaises(ConfigError) as caught:
            require_env(directory)
        message = str(caught.exception)
        for key in ("META_SYSTEM_USER_TOKEN", "META_AD_ACCOUNT_ID", "META_PAGE_ID"):
            self.assertIn(key, message, "the error should name every variable still to fill in")
        self.assertIn("Nothing was sent to Meta", message)

    def test_the_scopes_it_lists_match_the_setup_guide(self):
        """Three files told a user three different scope lists. A token missing
        one works until it suddenly does not.

        `adscooking/setup.py` is the authority now, because it is what prints the
        list during setup. A file naming no scopes is fine: it defers to the
        command. A file naming some of them has to name all seven, which is the
        drift this catches.
        """
        import re
        from adscooking.setup import SCOPES
        root = Path(__file__).parent.parent
        pattern = re.compile(r"\b(" + "|".join(SCOPES) + r")\b")
        sources = {
            "adscooking/setup.py": (root / "adscooking" / "setup.py").read_text(),
            ".env.example": self.example,
            "connecting-your-account.md": (root / "context" / "connecting-your-account.md").read_text(),
            "connect/SKILL.md": (root / "skills" / "connect" / "SKILL.md").read_text(),
        }
        found = {name: set(pattern.findall(text)) for name, text in sources.items()}
        self.assertEqual(found["adscooking/setup.py"], set(SCOPES))
        partial = {name: sorted(scopes) for name, scopes in found.items()
                   if scopes and scopes != set(SCOPES)}
        self.assertEqual(partial, {},
                         f"these name only some of the seven scopes: {partial}")


if __name__ == "__main__":
    unittest.main()
