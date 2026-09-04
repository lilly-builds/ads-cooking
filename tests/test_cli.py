"""Exit codes, because something is going to poll this."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from adscooking.__main__ import SETUP_PROBLEM, main


class TestExitCodes(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        stack = contextlib.ExitStack()
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.addCleanup(stack.close)

    def test_a_setup_problem_is_not_reported_as_a_campaign_alert(self):
        """Exit 2 means the campaign needs attention. A missing .env is not that.

        A daily check that pages someone because a config file moved is a check
        they will turn off.
        """
        code = main(["--config-dir", str(self.dir), "pulse"])
        self.assertEqual(code, SETUP_PROBLEM)
        self.assertNotEqual(code, 2)

    def test_publish_without_go_is_a_clean_exit(self):
        (self.dir / ".env").write_text(
            "META_SYSTEM_USER_TOKEN=t\nMETA_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n"
        )
        example = Path(__file__).parent.parent / "campaign.example.json"
        (self.dir / "campaign.json").write_text(example.read_text())
        (self.dir / "creative").mkdir()
        (self.dir / "creative" / "ad.mp4").write_bytes(b"x")
        (self.dir / "creative" / "thumbnail.jpg").write_bytes(b"x")
        self.assertEqual(main(["--config-dir", str(self.dir), "publish"]), 0)

    def test_changing_copy_before_anything_is_published_is_a_setup_problem(self):
        (self.dir / ".env").write_text(
            "META_SYSTEM_USER_TOKEN=t\nMETA_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n"
        )
        example = Path(__file__).parent.parent / "campaign.example.json"
        (self.dir / "campaign.json").write_text(example.read_text())
        self.assertEqual(main(["--config-dir", str(self.dir), "copy"]), SETUP_PROBLEM)


class TestResumeIsActuallyWired(unittest.TestCase):
    """publish must hand the live ids through, or a re-run duplicates everything.

    The resume logic inside publish() was correct and tested. main() never
    passed it anything, so on a real account a second `publish --go` would have
    built a second campaign, a second ad set and a second ad, and re-uploaded
    the video. Tests of a feature are worthless if nothing calls it.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        stack = contextlib.ExitStack()
        self.out = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.addCleanup(stack.close)

        (self.dir / ".env").write_text(
            "META_SYSTEM_USER_TOKEN=t\nMETA_AD_ACCOUNT_ID=act_1\nMETA_PAGE_ID=2\n"
        )
        config = json.loads((Path(__file__).parent.parent / "campaign.example.json").read_text())
        config["live"] = {
            "campaign_id": "c-1", "ad_set_id": "as-1", "ad_id": "ad-1",
            "video_id": "v-1", "thumbnail_hash": "h-1", "form_id": "f-1",
            "creative_id": "cr-1",
        }
        (self.dir / "campaign.json").write_text(json.dumps(config))
        (self.dir / "creative").mkdir()
        (self.dir / "creative" / "ad.mp4").write_bytes(b"x")
        (self.dir / "creative" / "thumbnail.jpg").write_bytes(b"x")

    def test_a_fully_published_campaign_is_not_rebuilt(self):
        main(["--config-dir", str(self.dir), "publish"])
        output = self.out.getvalue()
        self.assertIn("reusing c-1", output)
        self.assertIn("reusing ad-1", output)
        self.assertNotIn("dryrun-", output,
                         "nothing should have been created; every id was already known")


class TestFirstRunErrorNamesARealCommand(unittest.TestCase):
    def test_the_missing_env_message_points_at_a_command_that_exists(self):
        """This is the first thing a new user ever sees from this tool."""
        import io as _io
        from adscooking.config import ConfigError, require_env
        empty = Path(tempfile.mkdtemp())
        with self.assertRaises(ConfigError) as caught:
            require_env(empty)
        message = str(caught.exception)
        self.assertIn("/ads-cooking:connect", message)
        self.assertNotIn("/meta-connect", message)


class TestConfigFolderIsNotConfusedWithTheRepo(unittest.TestCase):
    """The config folder and the repo are both called ads-cooking.

    Running from the parent of a clone must not resolve the checkout itself as
    somebody's config folder.
    """

    def test_a_directory_of_the_right_name_but_no_config_is_ignored(self):
        import os
        from adscooking.config import config_dir
        os.environ.pop("ADS_COOKING_HOME", None)
        parent = Path(tempfile.mkdtemp())
        looks_like_the_repo = parent / "ads-cooking"
        (looks_like_the_repo / "adscooking").mkdir(parents=True)
        self.assertEqual(config_dir(parent), Path.home() / ".ads-cooking")

    def test_a_directory_holding_real_config_is_used(self):
        import os
        from adscooking.config import config_dir
        os.environ.pop("ADS_COOKING_HOME", None)
        parent = Path(tempfile.mkdtemp())
        real = parent / "ads-cooking"
        real.mkdir()
        (real / ".env").write_text("META_SYSTEM_USER_TOKEN=t\n")
        self.assertEqual(config_dir(parent), real)


if __name__ == "__main__":
    unittest.main()
