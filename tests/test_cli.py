"""Exit codes, because something is going to poll this."""

import contextlib
import io
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


if __name__ == "__main__":
    unittest.main()
