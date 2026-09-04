"""Error handling. Every branch here came from an error we actually hit."""

import json
import unittest

from adscooking.graph import Graph, GraphError
from tests.fake_graph import http_error


class TestErrorClassification(unittest.TestCase):
    def test_expired_token_is_recognised(self):
        error = http_error(190, "Session has expired")
        self.assertTrue(error.is_auth)
        self.assertIn("expired or was revoked", error.explain())

    def test_missing_permission_is_recognised(self):
        for code in (10, 200):
            self.assertTrue(http_error(code).is_permission)
        self.assertIn("never assigned to the system user", http_error(200).explain())

    def test_generic_code_1_is_treated_as_transient(self):
        """Meta's code 1 across every call means Meta is down, not that your
        setup is broken. Rebuilding at this point makes things worse."""
        error = http_error(1, "An unknown error occurred")
        self.assertTrue(error.is_transient)
        self.assertIn("outage", error.explain())
        self.assertIn("Do not", error.explain())

    def test_an_unknown_code_falls_back_to_metas_message(self):
        error = http_error(999, "Something specific and useful")
        self.assertFalse(error.is_auth or error.is_permission or error.is_transient)
        self.assertIn("Something specific and useful", error.explain())

    def test_a_non_json_body_does_not_crash_the_parser(self):
        error = GraphError("p", 502, "<html>Bad Gateway</html>")
        self.assertIsNone(error.code)
        self.assertIn("Bad Gateway", error.explain())


class TestTokenHandling(unittest.TestCase):
    def test_a_missing_token_is_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            Graph("")

    def test_the_token_is_not_in_the_repr(self):
        """A stray print or a traceback must not leak the token."""
        self.assertNotIn("secret-token-value", repr(Graph("secret-token-value")))


class TestNestedParameterEncoding(unittest.TestCase):
    """The bug that would have made every write fail.

    urlencode calls str() on a dict, which gives Python's repr with single
    quotes. Meta parses these fields as JSON and rejects single quotes as an
    invalid parameter. Nothing about the error message points at the cause.
    """

    def test_a_nested_dict_becomes_json_not_a_python_repr(self):
        from adscooking.graph import _encode_nested
        encoded = _encode_nested({"targeting": {"geo_locations": {"countries": ["US"]}}})
        self.assertNotIn("'", encoded["targeting"])
        self.assertEqual(json.loads(encoded["targeting"]),
                         {"geo_locations": {"countries": ["US"]}})

    def test_a_list_becomes_json(self):
        from adscooking.graph import _encode_nested
        self.assertEqual(json.loads(_encode_nested({"x": [1, 2]})["x"]), [1, 2])

    def test_booleans_become_json_not_python_capitalised(self):
        """Python's str(False) is "False". Meta wants "false"."""
        from adscooking.graph import _encode_nested
        self.assertEqual(_encode_nested({"x": False})["x"], "false")

    def test_a_string_that_is_already_json_is_left_alone(self):
        """lead_form.questions is hand-written as JSON in campaign.json.

        Double-encoding it would send an escaped string where Meta wants an
        array.
        """
        from adscooking.graph import _encode_nested
        original = '[{"type":"EMAIL"}]'
        self.assertEqual(_encode_nested({"questions": original})["questions"], original)

    def test_plain_values_pass_through(self):
        from adscooking.graph import _encode_nested
        self.assertEqual(_encode_nested({"name": "x", "n": 5}), {"name": "x", "n": 5})

    def test_the_whole_body_survives_urlencoding_as_valid_json(self):
        """End to end: what actually goes on the wire is parseable by Meta."""
        import urllib.parse
        from adscooking.graph import _encode_nested
        body = _encode_nested({"targeting": {"age_min": 30}, "name": "ad set"})
        round_tripped = dict(urllib.parse.parse_qsl(urllib.parse.urlencode(body)))
        self.assertEqual(json.loads(round_tripped["targeting"]), {"age_min": 30})


if __name__ == "__main__":
    unittest.main()
