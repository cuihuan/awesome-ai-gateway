"""Unit tests for build_compare_html.py pure logic (no filesystem)."""

import unittest

from build_compare_html import (
    build_sitemap,
    extract_description,
    extract_lastmod,
    extract_title,
    md_to_html,
    render_hub,
    render_inline,
    rewrite_link,
    slug_lang,
)


class TestRewriteLink(unittest.TestCase):
    def test_absolute_and_anchor_unchanged(self):
        self.assertEqual(rewrite_link("https://x.com/a"), "https://x.com/a")
        self.assertEqual(rewrite_link("#section"), "#section")
        self.assertEqual(rewrite_link("mailto:a@b.c"), "mailto:a@b.c")

    def test_sibling_md_becomes_html(self):
        self.assertEqual(rewrite_link("litellm-alternatives-2026.md"), "litellm-alternatives-2026.html")
        self.assertEqual(rewrite_link("foo.md#bar"), "foo.html#bar")

    def test_parent_md_goes_to_github_blob(self):
        self.assertEqual(
            rewrite_link("../README.md"),
            "https://github.com/cuihuan/awesome-ai-gateway/blob/main/README.md",
        )
        self.assertEqual(
            rewrite_link("../BENCHMARKS.md#part-4--scorecard"),
            "https://github.com/cuihuan/awesome-ai-gateway/blob/main/BENCHMARKS.md#part-4--scorecard",
        )

    def test_repo_relative_script(self):
        self.assertEqual(
            rewrite_link("../scripts/canary_check.py"),
            "https://github.com/cuihuan/awesome-ai-gateway/blob/main/scripts/canary_check.py",
        )


class TestRenderInline(unittest.TestCase):
    def test_bold_code_link(self):
        self.assertEqual(render_inline("**bold**"), "<strong>bold</strong>")
        self.assertEqual(render_inline("`x<y`"), "<code>x&lt;y</code>")
        self.assertEqual(render_inline("[t](https://x.com)"), '<a href="https://x.com">t</a>')

    def test_bold_wrapping_link(self):
        self.assertEqual(
            render_inline("**[LiteLLM](https://x.com)**"),
            '<strong><a href="https://x.com">LiteLLM</a></strong>',
        )

    def test_link_with_bold_label(self):
        self.assertEqual(
            render_inline("[**LiteLLM**](https://x.com)"),
            '<a href="https://x.com"><strong>LiteLLM</strong></a>',
        )

    def test_sibling_link_rewritten(self):
        self.assertEqual(
            render_inline("see [alts](litellm-alternatives-2026.md)"),
            'see <a href="litellm-alternatives-2026.html">alts</a>',
        )

    def test_html_escaped(self):
        self.assertEqual(render_inline("a < b & c"), "a &lt; b &amp; c")

    def test_italic(self):
        self.assertEqual(render_inline("the *small* number"), "the <em>small</em> number")
        # bold is not mistaken for two italics
        self.assertEqual(render_inline("**bold**"), "<strong>bold</strong>")

    def test_code_content_not_bolded(self):
        # ** inside a code span must stay literal, not become <strong>
        self.assertEqual(render_inline("`**not bold**`"), "<code>**not bold**</code>")


class TestMdToHtml(unittest.TestCase):
    def test_skips_leading_h1_renders_h2(self):
        html = md_to_html("# Title\n\n## Section\n\nbody text")
        self.assertNotIn("Title", html)          # H1 handled by the page template
        self.assertIn("<h2>Section</h2>", html)
        self.assertIn("<p>body text</p>", html)

    def test_paragraph_joins_wrapped_lines(self):
        self.assertEqual(md_to_html("a\nb\nc").strip(), "<p>a b c</p>")

    def test_bullet_and_ordered_lists(self):
        self.assertIn("<ul><li>one</li><li>two</li></ul>", md_to_html("- one\n- two"))
        self.assertIn("<ol><li>first</li><li>second</li></ol>", md_to_html("1. first\n2. second"))

    def test_blockquote_and_hr(self):
        self.assertIn("<blockquote>quote line</blockquote>", md_to_html("> quote line"))
        self.assertIn("<hr>", md_to_html("---"))

    def test_table(self):
        out = md_to_html("| A | B |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<thead><tr><th>A</th><th>B</th></tr></thead>", out)
        self.assertIn("<tr><td>1</td><td>2</td></tr>", out)

    def test_no_markdown_artifacts_leak(self):
        sample = "# T\n\n## Heading\n\nSome **bold** and a [link](https://x.com) and `code`.\n\n- item **b**\n\n| H |\n|---|\n| **v** |"
        out = md_to_html(sample)
        self.assertNotIn("**", out)
        self.assertNotIn("](", out)
        self.assertNotIn("\x00", out)  # no leftover placeholders

    def test_star_spans_collapse_to_display_text(self):
        """Live star spans (kept fresh by update_readme.py) must render as their
        display text — an unstripped marker would be HTML-escaped and visible."""
        sample = (
            "# T\n\nMost starred (<!--s:BerriAI/litellm-->⭐ 54.8k<!--/s-->).\n\n"
            "| G | Stars |\n|---|---|\n| **B** | <!--s:maximhq/bifrost-->⭐ 6.8k<!--/s--> |"
        )
        out = md_to_html(sample)
        self.assertIn("(⭐ 54.8k)", out)
        self.assertIn("<td>⭐ 6.8k</td>", out)
        self.assertNotIn("s:BerriAI/litellm", out)
        self.assertNotIn("&lt;!--", out)


class TestMetadata(unittest.TestCase):
    def test_extract_title(self):
        self.assertEqual(extract_title("# Hello **World**\n\nbody"), "Hello World")
        self.assertEqual(extract_title("no heading"), "Untitled")

    def test_extract_description_first_paragraph(self):
        md = "# T\n\nThis is the lede paragraph with a [link](u) and **bold**.\n\n## Next"
        self.assertEqual(extract_description(md), "This is the lede paragraph with a link and bold.")

    def test_extract_description_skips_italic_byline(self):
        md = ("# T\n\n*Last updated 2026-06-16 · Part of [Awesome AI Gateway](../README.md).*\n\n"
              "The real lede paragraph that should become the description.\n\n## Next")
        self.assertEqual(extract_description(md),
                         "The real lede paragraph that should become the description.")

    def test_extract_description_strips_star_spans(self):
        md = "# T\n\nLiteLLM (<!--s:BerriAI/litellm-->⭐ 54.8k<!--/s-->) leads the pack today.\n\n## Next"
        self.assertEqual(extract_description(md), "LiteLLM (⭐ 54.8k) leads the pack today.")

    def test_extract_description_truncates_on_word_boundary(self):
        md = "# T\n\n" + "word " * 60
        d = extract_description(md, limit=40)
        self.assertTrue(d.endswith("…"))
        self.assertLessEqual(len(d), 41)
        self.assertNotIn("wor…", d)  # cut at a space, not mid-word

    def test_slug_lang(self):
        self.assertEqual(slug_lang("litellm-alternatives-2026.md"), ("litellm-alternatives-2026", "en"))
        self.assertEqual(slug_lang("one-api-vs-new-api-vs-litellm.zh-CN.md"),
                         ("one-api-vs-new-api-vs-litellm.zh-CN", "zh-CN"))


class TestLastmod(unittest.TestCase):
    def test_extracts_byline_date(self):
        self.assertEqual(extract_lastmod("# T\n\n*Last updated 2026-06-16 · Part of X.*"), "2026-06-16")
        self.assertEqual(extract_lastmod("# T\n\n*最近更新：2026-06-13*"), "2026-06-13")

    def test_none_when_absent(self):
        self.assertIsNone(extract_lastmod("# T\n\nNo date here."))


class TestHub(unittest.TestCase):
    ARTICLES = [
        {"slug": "older", "title": "Older Article", "description": "Older desc.", "lastmod": "2026-06-10"},
        {"slug": "newer", "title": "Newer Article", "description": "Newer desc.", "lastmod": "2026-06-20"},
        {"slug": "nodate", "title": "No Date Article", "description": "No date desc.", "lastmod": None},
    ]

    def test_lists_every_article_with_link_and_description(self):
        html = render_hub(self.ARTICLES)
        for a in self.ARTICLES:
            self.assertIn(f'href="{a["slug"]}.html"', html)
            self.assertIn(a["title"], html)
            self.assertIn(a["description"], html)

    def test_newest_first(self):
        html = render_hub(self.ARTICLES)
        self.assertLess(html.index("Newer Article"), html.index("Older Article"))

    def test_canonical_and_itemlist_jsonld(self):
        html = render_hub(self.ARTICLES)
        self.assertIn('<link rel="canonical" href="https://cuihuan.github.io/awesome-ai-gateway/compare/"', html)
        self.assertIn('"@type":"ItemList"', html)
        self.assertIn('"@type":"CollectionPage"', html)

    def test_no_markdown_or_placeholder_leak(self):
        html = render_hub(self.ARTICLES)
        self.assertNotIn("\x00", html)


class TestSitemap(unittest.TestCase):
    def test_includes_home_and_articles_sorted(self):
        xml = build_sitemap([("b-article", None), ("a-article", "2026-06-16")])
        self.assertIn("<loc>https://cuihuan.github.io/awesome-ai-gateway/</loc>", xml)
        ia = xml.index("a-article.html")
        ib = xml.index("b-article.html")
        self.assertLess(ia, ib)  # sorted
        self.assertIn("<priority>0.8</priority>", xml)
        self.assertIn("cost-calculator.html", xml)  # interactive tool is in the sitemap
        self.assertTrue(xml.strip().endswith("</urlset>"))

    def test_lastmod_emitted_only_when_present(self):
        xml = build_sitemap([("dated", "2026-06-16"), ("undated", None)])
        self.assertIn("<lastmod>2026-06-16</lastmod>", xml)
        # the undated article must not borrow another's lastmod
        undated_block = xml.split("compare/undated.html")[1].split("</url>")[0]
        self.assertNotIn("<lastmod>", undated_block)


if __name__ == "__main__":
    unittest.main()
