"""The monitor. Read-only, and the evaluation logic is a pure function."""

import unittest

from metaads.pulse import (ALERT, EXIT_CODES, INFO, WARN, evaluate, gather,
                           snapshot_state, token_days_left, worst)
from tests.fake_graph import FakeGraph

MONITOR = {
    "account_id": "act_000",
    "ids": {"campaign_id": "c1", "ad_set_id": "as1", "ad_id": "ad1"},
    "no_edit_window_until": "",
    "benchmarks": {"cpl_band_usd": [25, 35]},
    "thresholds": {
        "warn_spend_no_lead_usd": 105,
        "alert_spend_no_lead_usd": 210,
        "cpl_warn_usd": 70,
        "min_leads_for_cpl_verdict": 3,
        "budget_step_warn_pct": 20,
        "token_warn_days": 14,
    },
}


def snapshot(spend=0.0, leads=0, status="ACTIVE", **extra):
    actions = [{"action_type": "leadgen.other", "value": str(leads)}] if leads else []
    base = {
        "campaign": {"effective_status": status, "updated_time": "T0"},
        "adset": {"effective_status": status, "updated_time": "T0", "daily_budget": "2000"},
        "ad": {"effective_status": status, "updated_time": "T0", "creative": {"id": "cr1"}},
        "account": {"account_status": 1},
        "token": {"data": {}},
        "today": {"spend": "1.00"},
        "yesterday": {},
        "maximum": {"spend": str(spend), "actions": actions},
    }
    base.update(extra)
    return base


class TestReadOnly(unittest.TestCase):
    """The property that matters most, asserted rather than assumed."""

    def test_gather_never_writes(self):
        api = FakeGraph(allow_writes=False)   # any POST or upload raises
        gather(api, MONITOR)
        self.assertEqual(api.posts, [])
        self.assertEqual(api.uploads, [])
        self.assertTrue(api.gets, "it should still have read something")


class TestCostPerLead(unittest.TestCase):
    def test_inside_the_band_is_informational(self):
        findings = evaluate(snapshot(spend=90.0, leads=3), MONITOR, None)
        self.assertEqual(worst(findings), INFO)

    def test_above_the_warn_line_warns(self):
        findings = evaluate(snapshot(spend=300.0, leads=4), MONITOR, None)
        self.assertEqual(worst(findings), WARN)

    def test_too_few_leads_gives_no_verdict(self):
        """Two leads is not evidence. Saying so is better than a false verdict."""
        findings = evaluate(snapshot(spend=60.0, leads=2), MONITOR, None)
        text = " ".join(t for _, t in findings)
        self.assertIn("too few to judge", text)

    def test_spend_with_no_leads_warns_then_alerts(self):
        self.assertEqual(worst(evaluate(snapshot(spend=120.0), MONITOR, None)), WARN)
        self.assertEqual(worst(evaluate(snapshot(spend=250.0), MONITOR, None)), ALERT)


class TestEditDetection(unittest.TestCase):
    def test_an_edit_since_last_run_is_reported(self):
        previous = {"adset_updated": "T0", "ad_updated": "T0", "campaign_updated": "T0"}
        current = snapshot()
        current["adset"]["updated_time"] = "T1"
        findings = evaluate(current, MONITOR, previous)
        self.assertIn("edited", " ".join(t for _, t in findings))

    def test_an_edit_inside_the_no_edit_window_is_an_alert(self):
        config = dict(MONITOR, no_edit_window_until="2099-01-01")
        previous = {"adset_updated": "T0"}
        current = snapshot()
        current["adset"]["updated_time"] = "T1"
        self.assertEqual(worst(evaluate(current, config, previous)), ALERT)

    def test_no_previous_state_reports_no_edits(self):
        self.assertNotIn("edited", " ".join(t for _, t in evaluate(snapshot(), MONITOR, None)))

    def test_a_large_budget_jump_warns(self):
        previous = {"adset_updated": "T0", "daily_budget": "2000"}
        current = snapshot()
        current["adset"]["daily_budget"] = "5000"
        self.assertIn("budget moved", " ".join(t for _, t in evaluate(current, MONITOR, previous)))

    def test_a_small_budget_nudge_does_not_warn(self):
        previous = {"adset_updated": "T0", "daily_budget": "2000"}
        current = snapshot()
        current["adset"]["daily_budget"] = "2200"
        self.assertNotIn("budget moved", " ".join(t for _, t in evaluate(current, MONITOR, previous)))


class TestHealth(unittest.TestCase):
    def test_delivery_issues_alert(self):
        current = snapshot()
        current["ad"]["issues_info"] = [{"error_summary": "Ad rejected"}]
        self.assertEqual(worst(evaluate(current, MONITOR, None)), ALERT)

    def test_a_disabled_account_alerts(self):
        current = snapshot()
        current["account"]["account_status"] = 2
        self.assertEqual(worst(evaluate(current, MONITOR, None)), ALERT)

    def test_no_spend_today_on_an_active_adset_warns(self):
        current = snapshot(status="ACTIVE")
        current["today"] = {"spend": "0"}
        self.assertIn("no spend", " ".join(t for _, t in evaluate(current, MONITOR, None)))

    def test_a_paused_adset_with_no_spend_is_not_flagged(self):
        current = snapshot(status="PAUSED")
        current["today"] = {"spend": "0"}
        self.assertNotIn("no spend", " ".join(t for _, t in evaluate(current, MONITOR, None)))


class TestToken(unittest.TestCase):
    def test_a_token_with_no_expiry_returns_none(self):
        """A never-expiring token is a valid setup, not a missing value."""
        self.assertIsNone(token_days_left({"data": {}}))

    def test_an_expiring_token_warns_before_it_dies(self):
        import time
        soon = int(time.time()) + 5 * 86400
        current = snapshot(token={"data": {"expires_at": soon}})
        self.assertIn("token expires", " ".join(t for _, t in evaluate(current, MONITOR, None)))


class TestExitCodes(unittest.TestCase):
    def test_severity_maps_to_a_shell_exit_code(self):
        self.assertEqual(EXIT_CODES[INFO], 0)
        self.assertEqual(EXIT_CODES[WARN], 1)
        self.assertEqual(EXIT_CODES[ALERT], 2)

    def test_state_captures_what_edit_detection_compares(self):
        state = snapshot_state(snapshot())
        for key in ("adset_updated", "ad_updated", "campaign_updated", "daily_budget", "creative_id"):
            self.assertIn(key, state)



class TestExpiryDate(unittest.TestCase):
    def test_the_warning_names_a_date_not_just_a_count(self):
        """A day count is not something you can put in a calendar."""
        import time
        from metaads.pulse import token_expiry_date
        soon = int(time.time()) + 5 * 86400
        current = snapshot(token={"data": {"expires_at": soon}})
        text = " ".join(t for _, t in evaluate(current, MONITOR, None))
        self.assertIn(token_expiry_date({"data": {"expires_at": soon}}), text)

    def test_a_never_expiring_token_reports_never(self):
        from metaads.pulse import token_expiry_date
        self.assertEqual(token_expiry_date({"data": {}}), "never")

if __name__ == "__main__":
    unittest.main()
