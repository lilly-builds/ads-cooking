"""Changing a live ad. The order of operations is the whole point."""

import contextlib
import io
import unittest

from metaads.update import update_copy, update_form
from tests.fake_graph import FakeGraph

ENV = {"META_AD_ACCOUNT_ID": "act_000", "META_PAGE_ID": "page-000"}
LIVE = {"ad_id": "ad-1", "video_id": "vid-1", "thumbnail_hash": "hash-1", "form_id": "form-1"}
CONFIG = {
    "creative": {
        "creative_name": "v2",
        "primary_texts": ["one", "two"],
        "headlines": ["h1"],
    },
    "lead_form": {"name": "form v2", "locale": "en_US"},
}


class Quiet(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.addCleanup(stack.close)


class TestCopyChange(Quiet):
    def test_it_creates_a_creative_then_points_the_ad_at_it(self):
        api = FakeGraph()
        update_copy(CONFIG, ENV, LIVE, api)
        paths = [path for path, _, _ in api.posts]
        self.assertEqual(paths, ["act_000/adcreatives", "ad-1"])

    def test_the_ad_keeps_its_id(self):
        """Creatives are immutable, so a copy change is a swap. The ad id is
        stable, which is what preserves the ad's delivery history."""
        api = FakeGraph()
        update_copy(CONFIG, ENV, LIVE, api)
        swap = api.posted_to("ad-1")[0]
        self.assertEqual(swap["creative"]["creative_id"], "post-1")

    def test_it_reuses_the_existing_video_rather_than_re_uploading(self):
        api = FakeGraph()
        update_copy(CONFIG, ENV, LIVE, api)
        self.assertEqual(api.uploads, [], "a copy change should not re-upload the video")
        creative = api.posted_to("/adcreatives")[0]
        self.assertEqual(creative["object_story_spec"]["video_data"]["video_id"], "vid-1")

    def test_it_keeps_pointing_at_the_existing_form(self):
        api = FakeGraph()
        update_copy(CONFIG, ENV, LIVE, api)
        creative = api.posted_to("/adcreatives")[0]
        cta = creative["object_story_spec"]["video_data"]["call_to_action"]
        self.assertEqual(cta["value"]["lead_gen_form_id"], "form-1")


class TestFormChange(Quiet):
    def test_it_creates_a_new_form_because_forms_cannot_be_edited(self):
        api = FakeGraph()
        update_form(CONFIG, ENV, LIVE, api)
        paths = [path for path, _, _ in api.posts]
        self.assertEqual(paths, ["page-000/leadgen_forms", "act_000/adcreatives", "ad-1"])

    def test_the_new_creative_points_at_the_new_form_not_the_old_one(self):
        api = FakeGraph()
        update_form(CONFIG, ENV, LIVE, api)
        creative = api.posted_to("/adcreatives")[0]
        cta = creative["object_story_spec"]["video_data"]["call_to_action"]
        self.assertEqual(cta["value"]["lead_gen_form_id"], "post-1")
        self.assertNotEqual(cta["value"]["lead_gen_form_id"], LIVE["form_id"])

    def test_the_form_is_created_with_the_page_token(self):
        api = FakeGraph()
        update_form(CONFIG, ENV, LIVE, api)
        self.assertEqual(api.token_used_for("/leadgen_forms"), "fake-page-token")

    def test_the_old_form_is_never_deleted(self):
        """It still holds the leads it collected."""
        api = FakeGraph()
        update_form(CONFIG, ENV, LIVE, api)
        self.assertNotIn("form-1", [path for path, _, _ in api.posts])


if __name__ == "__main__":
    unittest.main()
