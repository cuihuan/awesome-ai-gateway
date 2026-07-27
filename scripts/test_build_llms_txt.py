"""Unit tests for build_llms_txt.py (renders against the real compare/*.md)."""

import re
import unittest

import build_llms_txt
from build_llms_txt import render


class TestLlmsTxt(unittest.TestCase):
    def setUp(self):
        self.txt = render()

    def test_llmstxt_shape(self):
        # spec: starts with an H1, then a blockquote summary
        self.assertTrue(self.txt.startswith("# Awesome AI Gateway\n"))
        self.assertIn("\n> ", self.txt)

    def test_required_sections_present(self):
        for h in ["## Core", "## Comparisons", "## Guides", "## Tools (interactive)",
                  "## Data (machine-readable, CC0)", "## Companion tools (same author)"]:
            self.assertIn(h, self.txt)

    def test_guides_and_tools_list_canonical_pages_only(self):
        # The interactive tools and the one canonical guide must be present…
        for url in ("reduce-llm-api-costs.html", "gateway-picker.html", "cost-calculator.html"):
            self.assertIn(f"https://cuihuan.github.io/awesome-ai-gateway/{url}", self.txt)
        # …while the three guides that canonicalize to compare/ successors stay out
        # (their winners are already listed under Comparisons).
        for gone in ("litellm-vs-openrouter.html", "openrouter-alternatives.html",
                     "self-hosted-llm-gateway.html"):
            self.assertNotIn(f"awesome-ai-gateway/{gone}", self.txt)

    def test_every_comparison_listed_with_absolute_url(self):
        articles = build_llms_txt._articles()
        self.assertGreaterEqual(len(articles), 1)
        for a in articles:
            self.assertIn(f"https://cuihuan.github.io/awesome-ai-gateway/compare/{a['slug']}.html", self.txt)

    def test_companion_tools_linked(self):
        self.assertIn("https://github.com/cuihuan/llm-gateway-bench", self.txt)
        self.assertIn("https://github.com/cuihuan/modelprobe", self.txt)

    def test_links_are_absolute(self):
        # every markdown link target in llms.txt must be an absolute URL
        for target in re.findall(r"\]\(([^)]+)\)", self.txt):
            self.assertTrue(target.startswith("https://"), f"non-absolute link: {target}")

    def test_ends_with_single_newline(self):
        self.assertTrue(self.txt.endswith("\n"))
        self.assertFalse(self.txt.endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()
