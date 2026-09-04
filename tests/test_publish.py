"""Publishing is the workflow that spends money, so it gets the most tests."""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from metaads.publish import DryRun, build_adset, build_campaign, build_creative, publish
from tests.fake_graph import FakeGraph

CONFIG = json.loads((Path(__file__).parent.parent / "campaign.example.json").read_text())
ENV = {
    "META_SYSTEM_USER_TOKEN": "fake-token",
    "META_AD_ACCOUNT_ID": "act_000",
    "META_PAGE_ID": "page-000",
}


class CreativeOnDisk(unittest.TestCase):
    """Publishing reads the video and thumbnail off disk, so give it real files.

    This also proves the config paths resolve relative to the config folder
    rather than the working directory, which is the bug you get if you ever
    swap Path.cwd() back in.
    """

    def setUp(self):
        # These workflows narrate what they are doing, which is right at a
        # terminal and noise in a test run.
        stack = contextlib.ExitStack()
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.addCleanup(stack.close)

        self.base = Path(tempfile.mkdtemp())
        (self.base / "creative").mkdir()
        (self.base / "creative" / "ad.mp4").write_bytes(b"not really a video")
        (self.base / "creative" / "thumbnail.jpg").write_bytes(b"not really a jpeg")
        self.addCleanup(shutil.rmtree, self.base)


class TestSafetyRules(CreativeOnDisk):
    """The two rules that stop this tool spending money by accident."""

    def test_dry_run_sends_nothing(self):
        api = DryRun()
        publish(CONFIG, ENV, go=False, client=api, base_dir=self.base)
        self.assertTrue(api.calls, "the dry run should still build the payloads")
        # DryRun cannot reach the network at all: it has no token and no urllib.
        self.assertFalse(hasattr(api, "_token"))

    def test_everything_is_created_paused(self):
        api = FakeGraph()
        publish(CONFIG, ENV, go=True, client=api, base_dir=self.base)
        for suffix in ("/campaigns", "/adsets", "/ads"):
            payloads = api.posted_to(suffix)
            self.assertTrue(payloads, f"nothing was posted to {suffix}")
            self.assertEqual(
                payloads[0]["status"], "PAUSED",
                f"{suffix} must be created paused so a person decides when to spend",
            )

    def test_campaign_status_cannot_be_overridden_by_config(self):
        sneaky = json.loads(json.dumps(CONFIG))
        sneaky["campaign"]["status"] = "ACTIVE"
        self.assertEqual(build_campaign(sneaky["campaign"])["status"], "PAUSED")


class TestPayloads(unittest.TestCase):
    def test_budget_is_converted_to_cents(self):
        payload = build_adset({"name": "x", "daily_budget_usd": 20}, "c1", "p1")
        self.assertEqual(payload["daily_budget"], 2000)

    def test_fractional_budget_does_not_lose_a_cent_to_float_error(self):
        """20.005 * 100 is 2000.4999... as a float, which rounds to the wrong cent."""
        payload = build_adset({"name": "x", "daily_budget_usd": 20.005}, "c1", "p1")
        self.assertIsInstance(payload["daily_budget"], int)
        self.assertEqual(payload["daily_budget"], 2001)

    def test_budget_accepts_a_string_amount(self):
        payload = build_adset({"name": "x", "daily_budget_usd": "19.99"}, "c1", "p1")
        self.assertEqual(payload["daily_budget"], 1999)

    def test_targeting_omits_empty_optional_fields(self):
        payload = build_adset(
            {"name": "x", "daily_budget_usd": 5, "targeting": {"countries": ["GB"]}}, "c1", "p1"
        )
        self.assertNotIn("genders", payload["targeting"])
        self.assertEqual(payload["targeting"]["geo_locations"]["countries"], ["GB"])

    def test_creative_carries_every_text_variation(self):
        payload = build_creative(
            {
                "creative_name": "c",
                "primary_texts": ["a", "b", "c"],
                "headlines": ["h1", "h2"],
            },
            "page-1", "vid-1", "hash-1", "form-1",
        )
        self.assertEqual(len(payload["asset_feed_spec"]["bodies"]), 3)
        self.assertEqual(len(payload["asset_feed_spec"]["titles"]), 2)

    def test_creative_links_the_lead_form_to_the_cta(self):
        payload = build_creative(
            {"creative_name": "c", "primary_texts": ["a"], "headlines": ["h"]},
            "page-1", "vid-1", "hash-1", "form-42",
        )
        cta = payload["object_story_spec"]["video_data"]["call_to_action"]
        self.assertEqual(cta["value"]["lead_gen_form_id"], "form-42")


class TestThumbnailHash(CreativeOnDisk):
    """The /adimages response nests the hash under a filename Meta picks.

    Reading a top-level "hash" and defaulting to "" builds a creative with no
    image and no error, so these assert the value actually arrives.
    """

    def test_the_creative_gets_the_hash_from_the_upload(self):
        api = FakeGraph()
        publish(CONFIG, ENV, go=True, client=api, base_dir=self.base)
        creative = api.posted_to("/adcreatives")[0]
        self.assertEqual(creative["object_story_spec"]["video_data"]["image_hash"], "fake-hash")

    def test_an_empty_image_hash_never_reaches_the_creative(self):
        api = FakeGraph()
        publish(CONFIG, ENV, go=True, client=api, base_dir=self.base)
        creative = api.posted_to("/adcreatives")[0]
        self.assertTrue(creative["object_story_spec"]["video_data"]["image_hash"],
                        "an empty image hash means an ad with no thumbnail")

    def test_it_reads_the_nested_shape_meta_actually_sends(self):
        from metaads.publish import image_hash
        self.assertEqual(image_hash({"images": {"whatever.jpg": {"hash": "abc"}}}), "abc")

    def test_a_response_with_no_hash_raises_rather_than_returning_empty(self):
        from metaads.publish import image_hash
        with self.assertRaises(KeyError):
            image_hash({"images": {}})
        with self.assertRaises(KeyError):
            image_hash({})


class TestPageToken(CreativeOnDisk):
    """The mistake that costs an afternoon the first time you publish."""

    def test_lead_form_is_created_with_the_page_token(self):
        api = FakeGraph()
        publish(CONFIG, ENV, go=True, client=api, base_dir=self.base)
        self.assertEqual(
            api.token_used_for("/leadgen_forms"), "fake-page-token",
            "lead forms are page-owned and reject the system-user token",
        )

    def test_other_writes_use_the_default_token(self):
        api = FakeGraph()
        publish(CONFIG, ENV, go=True, client=api, base_dir=self.base)
        self.assertIsNone(api.token_used_for("/campaigns"))


class TestOrdering(CreativeOnDisk):
    def test_ad_is_created_last(self):
        """The ad references everything else, so it cannot be created first."""
        api = FakeGraph()
        publish(CONFIG, ENV, go=True, client=api, base_dir=self.base)
        paths = [path for path, _, _ in api.posts]
        self.assertTrue(paths[-1].endswith("/ads"))
        self.assertLess(paths.index("act_000/adcreatives"), len(paths) - 1)



class TestRequiredFieldsMetaDoesNotAskForClearly(unittest.TestCase):
    """Each of these is an error we hit once and should never hit again.

    The error messages Meta returns for these do not explain the fix, so the
    fix lives in code with a comment, and here so it stays.
    """

    def test_campaign_declares_where_the_budget_lives(self):
        # "Must specify True or False in is_adset_budget_sharing_enabled"
        self.assertIs(build_campaign({"name": "x"})["is_adset_budget_sharing_enabled"], False)

    def test_adset_sets_a_bid_strategy(self):
        # "Bid Amount Or Bid Constraints Required For Bid Strategy"
        payload = build_adset({"name": "x", "daily_budget_usd": 20}, "c", "p")
        self.assertEqual(payload["bid_strategy"], "LOWEST_COST_WITHOUT_CAP")

    def test_advantage_audience_flag_is_sent_even_when_off(self):
        # "Advantage Audience Flag Required". Off is not the same as absent.
        payload = build_adset({"name": "x", "daily_budget_usd": 20}, "c", "p")
        self.assertEqual(payload["targeting"]["targeting_automation"]["advantage_audience"], 0)

    def test_turning_advantage_audience_on_is_possible(self):
        payload = build_adset(
            {"name": "x", "daily_budget_usd": 20, "targeting": {"advantage_audience": True}},
            "c", "p",
        )
        self.assertEqual(payload["targeting"]["targeting_automation"]["advantage_audience"], 1)

    def test_an_exact_age_range_survives_with_advantage_off(self):
        """The reason to turn Advantage+ off: it forces ages 25 to 65 otherwise."""
        payload = build_adset(
            {"name": "x", "daily_budget_usd": 20, "targeting": {"age_min": 30, "age_max": 45}},
            "c", "p",
        )
        self.assertEqual((payload["targeting"]["age_min"], payload["targeting"]["age_max"]), (30, 45))


class TestResume(CreativeOnDisk):
    """A failure at step 5 should not mean re-uploading the video."""

    def test_an_existing_video_id_is_reused_not_re_uploaded(self):
        api = FakeGraph()
        publish(CONFIG, ENV, go=True, client=api, base_dir=self.base,
                resume={"campaign_id": "c-9", "ad_set_id": "as-9", "video_id": "v-9"})
        self.assertEqual(api.uploads and api.uploads[0][0], "act_000/adimages",
                         "the video should not have been uploaded again")
        self.assertEqual(len(api.uploads), 1, "only the thumbnail should still upload")

    def test_resumed_ids_are_used_by_the_later_steps(self):
        api = FakeGraph()
        publish(CONFIG, ENV, go=True, client=api, base_dir=self.base,
                resume={"campaign_id": "c-9", "ad_set_id": "as-9",
                        "video_id": "v-9", "thumbnail_hash": "h-9", "form_id": "f-9"})
        creative = api.posted_to("/adcreatives")[0]
        video = creative["object_story_spec"]["video_data"]
        self.assertEqual(video["video_id"], "v-9")
        self.assertEqual(video["image_hash"], "h-9")
        self.assertEqual(video["call_to_action"]["value"]["lead_gen_form_id"], "f-9")

    def test_empty_resume_values_are_ignored(self):
        """campaign.json ships with the live ids blank, not absent."""
        api = FakeGraph()
        publish(CONFIG, ENV, go=True, client=api, base_dir=self.base,
                resume={"campaign_id": "", "ad_set_id": None, "_comment": "notes"})
        self.assertTrue(api.posted_to("/campaigns"), "a blank id should not count as resumable")

    def test_a_fully_resumed_run_creates_nothing(self):
        api = FakeGraph()
        done = {"campaign_id": "c", "ad_set_id": "a", "video_id": "v", "thumbnail_hash": "h",
                "form_id": "f", "creative_id": "cr", "ad_id": "ad"}
        publish(CONFIG, ENV, go=True, client=api, base_dir=self.base, resume=done)
        self.assertEqual(api.posts, [])
        self.assertEqual(api.uploads, [])


class TestDryRunSummary(CreativeOnDisk):
    def test_it_warns_about_a_placeholder_privacy_policy(self):
        """Meta rejects the form, and it fails at step 5 after the video uploaded."""
        from metaads.publish import summarise
        api = DryRun()
        publish(CONFIG, ENV, go=False, client=api, base_dir=self.base)
        self.assertIn("example.com", summarise(CONFIG, api))

    def test_it_reports_the_monthly_spend_not_just_the_daily(self):
        from metaads.publish import summarise
        text = summarise(CONFIG, DryRun())
        self.assertIn("$20.00 a day", text)
        self.assertIn("$600 a month", text)

if __name__ == "__main__":
    unittest.main()
