"""Unit tests for canary_check.py pure logic (no network)."""

import json
import unittest

from canary_check import (
    USER_AGENT,
    Reply,
    build_request,
    capability_hit,
    fingerprint_summary,
    is_temperature_refusal,
    normalize,
    parse_models,
    parse_reply,
    token_similarity,
    verdict,
)


class TestNormalize(unittest.TestCase):
    def test_lowercase_collapse_strip_punct(self):
        self.assertEqual(normalize("  The  Ball: $0.05!! "), "the ball 005")

    def test_empty(self):
        self.assertEqual(normalize(""), "")
        self.assertEqual(normalize(None), "")


class TestTokenSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(token_similarity("the ball is 5", "the ball is 5"), 1.0)

    def test_disjoint(self):
        self.assertEqual(token_similarity("alpha beta", "gamma delta"), 0.0)

    def test_both_empty_is_one(self):
        self.assertEqual(token_similarity("", ""), 1.0)

    def test_one_empty_is_zero(self):
        self.assertEqual(token_similarity("hello", ""), 0.0)

    def test_partial_jaccard(self):
        # {a,b,c} vs {a,b,d} -> intersection 2 / union 4 = 0.5
        self.assertAlmostEqual(token_similarity("a b c", "a b d"), 0.5)

    def test_punctuation_ignored(self):
        self.assertEqual(token_similarity("0.05", "$0.05!"), 1.0)


class TestCapabilityHit(unittest.TestCase):
    def test_hit_substring_normalized(self):
        self.assertTrue(capability_hit("The ball costs $0.05.", "0.05"))

    def test_miss(self):
        self.assertFalse(capability_hit("The ball costs $0.10.", "0.05"))

    def test_compare_only_returns_none(self):
        self.assertIsNone(capability_hit("anything", None))


class TestVerdict(unittest.TestCase):
    def test_downgrade_when_relay_fails_a_probe_ref_passes(self):
        rows = [
            {"id": "reason", "similarity": 0.8, "relay_hit": False, "ref_hit": True},
            {"id": "echo", "similarity": 0.9, "relay_hit": True, "ref_hit": True},
        ]
        v = verdict(rows)
        self.assertIn("SUSPICIOUS", v["label"])
        self.assertEqual(v["downgrade_flags"], ["reason"])

    def test_suspicious_on_low_similarity(self):
        rows = [{"id": "a", "similarity": 0.2, "relay_hit": None, "ref_hit": None}]
        self.assertIn("SUSPICIOUS", verdict(rows)["label"])

    def test_inconclusive_mid_band(self):
        rows = [{"id": "a", "similarity": 0.6, "relay_hit": None, "ref_hit": None}]
        self.assertIn("INCONCLUSIVE", verdict(rows)["label"])

    def test_ok_high_similarity(self):
        rows = [
            {"id": "a", "similarity": 0.95, "relay_hit": True, "ref_hit": True},
            {"id": "b", "similarity": 0.85, "relay_hit": None, "ref_hit": None},
        ]
        v = verdict(rows)
        self.assertIn("OK", v["label"])
        self.assertEqual(v["downgrade_flags"], [])

    def test_mean_similarity_reported(self):
        rows = [{"id": "a", "similarity": 0.4, "relay_hit": None, "ref_hit": None},
                {"id": "b", "similarity": 0.6, "relay_hit": None, "ref_hit": None}]
        self.assertEqual(verdict(rows)["mean_similarity"], 0.5)


class TestParseReply(unittest.TestCase):
    def test_full_body(self):
        r = parse_reply({
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"prompt_tokens": 42, "completion_tokens": 3},
            "system_fingerprint": "fp_abc",
        })
        self.assertEqual(r, Reply(content="hello", system_fingerprint="fp_abc", prompt_tokens=42))

    def test_missing_fields_tolerated(self):
        r = parse_reply({"choices": [{}]})
        self.assertEqual(r, Reply(content="", system_fingerprint=None, prompt_tokens=None))
        self.assertEqual(parse_reply({}), Reply(content="", system_fingerprint=None, prompt_tokens=None))
        self.assertEqual(parse_reply(None), Reply(content="", system_fingerprint=None, prompt_tokens=None))

    def test_blank_fingerprint_is_none(self):
        r = parse_reply({"choices": [{"message": {"content": "x"}}], "system_fingerprint": ""})
        self.assertIsNone(r.system_fingerprint)


class TestParseModels(unittest.TestCase):
    def test_splits_trims_dedupes_preserving_order(self):
        self.assertEqual(parse_models("gpt-5.5, claude-opus-4-8 ,gpt-5.5"), ["gpt-5.5", "claude-opus-4-8"])

    def test_single(self):
        self.assertEqual(parse_models("gpt-4o"), ["gpt-4o"])

    def test_empty(self):
        self.assertEqual(parse_models(""), [])
        self.assertEqual(parse_models(" , "), [])


class TestFingerprintSummary(unittest.TestCase):
    def _r(self, fp=None, pt=None):
        return Reply(content="x", system_fingerprint=fp, prompt_tokens=pt)

    def test_no_metadata_is_not_comparable(self):
        s = fingerprint_summary([(self._r(), self._r())])
        self.assertEqual(s["comparable"], 0)
        self.assertEqual(s["flags"], [])
        self.assertIsNone(s["fp_mismatch"])
        self.assertIsNone(s["max_prompt_token_skew"])

    def test_matching_fingerprint_and_tokens_clean(self):
        s = fingerprint_summary([(self._r("fp_a", 100), self._r("fp_a", 100))])
        self.assertEqual(s["flags"], [])
        self.assertFalse(s["fp_mismatch"])
        self.assertEqual(s["max_prompt_token_skew"], 0.0)
        self.assertEqual(s["comparable"], 1)

    def test_fingerprint_mismatch_flagged(self):
        s = fingerprint_summary([(self._r("fp_a", 100), self._r("fp_b", 100))])
        self.assertTrue(s["fp_mismatch"])
        self.assertIn("system_fingerprint", s["flags"])

    def test_prompt_token_skew_beyond_tolerance_flagged(self):
        # 100 vs 130 = 30% skew > default 15% tolerance → tokenizer tell
        s = fingerprint_summary([(self._r(pt=130), self._r(pt=100))])
        self.assertIn("prompt_tokens", s["flags"])
        self.assertEqual(s["max_prompt_token_skew"], 0.3)

    def test_small_skew_within_tolerance_not_flagged(self):
        s = fingerprint_summary([(self._r(pt=105), self._r(pt=100))])
        self.assertEqual(s["flags"], [])
        self.assertEqual(s["max_prompt_token_skew"], 0.05)

    def test_max_skew_across_canaries(self):
        s = fingerprint_summary([
            (self._r(pt=102), self._r(pt=100)),  # 2%
            (self._r(pt=140), self._r(pt=100)),  # 40%
        ])
        self.assertEqual(s["max_prompt_token_skew"], 0.4)
        self.assertIn("prompt_tokens", s["flags"])


class TestBuildRequest(unittest.TestCase):
    """Two canary reporters had to patch this script before it would run at all
    (#70, #82). These tests pin the two things they had to change."""

    def _req(self, **kw):
        return build_request("https://relay.example/v1/", "sk-secret", "gpt-5.5", "hi", **kw)

    def test_sends_an_explicit_user_agent(self):
        # the default Python-urllib UA is what the WAFs rejected
        self.assertEqual(self._req().get_header("User-agent"), USER_AGENT)
        self.assertNotIn("urllib", USER_AGENT.lower())

    def test_url_joined_without_double_slash(self):
        self.assertEqual(self._req().full_url, "https://relay.example/v1/chat/completions")

    def test_temperature_zero_by_default(self):
        self.assertEqual(json.loads(self._req().data)["temperature"], 0)

    def test_temperature_omitted_entirely_when_none(self):
        # not "temperature": null — models that refuse the field reject that too
        self.assertNotIn("temperature", json.loads(self._req(temperature=None).data))

    def test_key_travels_in_the_header_not_the_body(self):
        self.assertNotIn("sk-secret", self._req().data.decode())


class TestIsTemperatureRefusal(unittest.TestCase):
    def test_openai_wording(self):
        self.assertTrue(is_temperature_refusal(
            '{"error":{"message":"Unsupported value: \'temperature\' does not support 0 '
            'with this model. Only the default (1) value is supported."}}'))

    def test_generic_unsupported_wording(self):
        self.assertTrue(is_temperature_refusal("temperature is not supported for this model"))

    def test_unrelated_error_is_not_a_refusal(self):
        # a dead key or a missing model must not silently drop temperature
        self.assertFalse(is_temperature_refusal('{"error":{"message":"Invalid API key"}}'))
        self.assertFalse(is_temperature_refusal('{"error":{"message":"model not found"}}'))

    def test_unsupported_but_not_about_temperature(self):
        self.assertFalse(is_temperature_refusal("unsupported value: 'top_k' is not supported"))


if __name__ == "__main__":
    unittest.main()
