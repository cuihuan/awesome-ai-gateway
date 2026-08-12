"""Unit tests for the pure functions in update_readme.py (no network)."""

import re
import unittest
from datetime import datetime, timezone
from pathlib import Path

from update_readme import (
    OMC_MARKER_RE,
    RVD_MARKER_RE,
    STAR_MARKER_RE,
    collect_marked_repos,
    format_stars,
    load_openrouter_model_count,
    load_retention_as_of,
    parse_displayed_stars,
    render_openrouter_model_count,
    days_since,
    quiet_entries,
    render_maintenance_block,
    render_releases_block,
    replace_between_markers,
    replace_model_count_markers,
    replace_retention_date_markers,
    replace_star_markers,
    sort_top_gateways_table,
    star_span_files,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestFormatStars(unittest.TestCase):
    def test_below_thousand_is_plain(self):
        self.assertEqual(format_stars(0), "0")
        self.assertEqual(format_stars(823), "823")

    def test_thousands_get_one_decimal(self):
        self.assertEqual(format_stars(5712), "5.7k")
        self.assertEqual(format_stars(1234), "1.2k")

    def test_round_thousands_drop_decimal(self):
        self.assertEqual(format_stars(50000), "50k")
        self.assertEqual(format_stars(50049), "50k")

    def test_large_counts(self):
        self.assertEqual(format_stars(50349), "50.3k")


class TestStarMarkers(unittest.TestCase):
    SAMPLE = (
        "| [A](https://github.com/o/a) | <!--s:o/a-->⭐ ~1k<!--/s--> |\n"
        "- [B](https://github.com/o/b) <!--s:o/b-->⭐ old<!--/s--> text\n"
        "- [A again](https://github.com/o/a) <!--s:o/a-->⭐ ~1k<!--/s-->\n"
    )

    def test_collect_unique_in_order(self):
        self.assertEqual(collect_marked_repos(self.SAMPLE), ["o/a", "o/b"])

    def test_replace_known_repos(self):
        out = replace_star_markers(self.SAMPLE, {"o/a": 1500, "o/b": 230})
        self.assertIn("<!--s:o/a-->⭐ 1.5k<!--/s-->", out)
        self.assertIn("<!--s:o/b-->⭐ 230<!--/s-->", out)
        self.assertNotIn("old", out)

    def test_unknown_repo_left_untouched(self):
        out = replace_star_markers(self.SAMPLE, {"o/a": 1500})
        self.assertIn("<!--s:o/b-->⭐ old<!--/s-->", out)

    def test_replace_is_idempotent(self):
        once = replace_star_markers(self.SAMPLE, {"o/a": 1500, "o/b": 230})
        twice = replace_star_markers(once, {"o/a": 1500, "o/b": 230})
        self.assertEqual(once, twice)


class TestReplaceBetweenMarkers(unittest.TestCase):
    def test_replaces_content_and_keeps_markers(self):
        text = "head\n<!-- X:START -->\nold\n<!-- X:END -->\ntail"
        out = replace_between_markers(text, "<!-- X:START -->", "<!-- X:END -->", "new")
        self.assertEqual(out, "head\n<!-- X:START -->\nnew\n<!-- X:END -->\ntail")

    def test_missing_markers_raise(self):
        with self.assertRaises(ValueError):
            replace_between_markers("no markers", "<!-- X:START -->", "<!-- X:END -->", "x")


class TestStarSpanFiles(unittest.TestCase):
    def test_covers_readmes_landing_page_then_every_compare_source(self):
        files = star_span_files()
        self.assertEqual(
            [p.name for p in files[:3]],
            ["README.md", "README.zh-CN.md", "index.html"],
            "index.html carries the FAQPage JSON-LD that AI answers quote verbatim; if it "
            "leaves the refresh set, its numbers go back to being hand-typed and drifting",
        )
        compare_sources = sorted((REPO_ROOT / "compare").glob("*.md"))
        self.assertTrue(compare_sources, "compare/*.md sources vanished?")
        self.assertEqual(files[3:], compare_sources)


class TestNoHandTypedStarCounts(unittest.TestCase):
    """Every reader-facing star count must live inside a ``<!--s:-->`` span.

    Hand-typed counts rot silently — the compare pages said 51k★ while the
    daily-refreshed README said 54.8k for the same repo. Strip the live spans,
    then fail on any star-count-shaped text left behind. (Rubric scores like
    '★4.5' put the star glyph first and are not matched.)
    """

    HAND_TYPED = re.compile(
        r"[\d][\d.,]*\s*k?\s*★"                        # '51k★', '4★', '约 40k★'
        r"|⭐\s*~?[\d]"                                 # span display text outside a span
        r"|[\d][\d.,]*k\s+(?:GitHub\s+)?[Ss]tars?\b"   # '51k stars'
    )

    def test_readmes_and_compare_sources_carry_no_hand_typed_counts(self):
        offenders = []
        for path in star_span_files():
            text = STAR_MARKER_RE.sub("", path.read_text(encoding="utf-8"))
            for lineno, line in enumerate(text.split("\n"), 1):
                for match in self.HAND_TYPED.finditer(line):
                    offenders.append(f"{path.name}:{lineno}: {match.group(0)!r}")
        self.assertEqual(
            offenders,
            [],
            "hand-typed star counts outside <!--s:--> spans:\n" + "\n".join(offenders),
        )


class TestOpenRouterModelCount(unittest.TestCase):
    def test_render_rounds_to_the_nearest_ten(self):
        self.assertEqual(render_openrouter_model_count(342), "~340")
        self.assertEqual(render_openrouter_model_count(347), "~350")
        self.assertEqual(render_openrouter_model_count(400), "~400")

    def test_replace_rewrites_stale_spans(self):
        text = "OpenRouter (<!--omc-->400+<!--/omc--> models), again <!--omc-->old<!--/omc-->."
        self.assertEqual(
            replace_model_count_markers(text, "~340"),
            "OpenRouter (<!--omc-->~340<!--/omc--> models), again <!--omc-->~340<!--/omc-->.",
        )

    def test_every_rendered_mention_matches_the_canonical_count(self):
        """The READMEs once said ~340 and 400+ for the same thing three sections
        apart. Every <!--omc--> span must equal what data/models.json declares."""
        expected = f"<!--omc-->{render_openrouter_model_count(load_openrouter_model_count())}<!--/omc-->"
        for path in star_span_files():
            for match in OMC_MARKER_RE.finditer(path.read_text(encoding="utf-8")):
                self.assertEqual(match.group(0), expected, path.name)

    def test_both_readmes_carry_spans(self):
        for path in star_span_files()[:2]:
            self.assertIn("<!--omc-->", path.read_text(encoding="utf-8"), path.name)


class TestRetentionVerifiedDate(unittest.TestCase):
    def test_replace_rewrites_stale_spans(self):
        text = "primary sources, verified <!--rvd-->2026-01-01<!--/rvd-->."
        self.assertEqual(
            replace_retention_date_markers(text, "2026-07-08"),
            "primary sources, verified <!--rvd-->2026-07-08<!--/rvd-->.",
        )

    def test_readme_dates_match_the_json_as_of(self):
        """The 'verified <date>' prose next to the retention matrix must equal
        data/data_retention.json's as_of — it drifted silently before."""
        expected = f"<!--rvd-->{load_retention_as_of()}<!--/rvd-->"
        for path in star_span_files():
            for match in RVD_MARKER_RE.finditer(path.read_text(encoding="utf-8")):
                self.assertEqual(match.group(0), expected, path.name)

    def test_both_readmes_carry_the_span(self):
        for path in star_span_files()[:2]:
            self.assertIn("<!--rvd-->", path.read_text(encoding="utf-8"), path.name)


class TestParseDisplayedStars(unittest.TestCase):
    def test_thousands_suffix(self):
        row = "| [A](https://github.com/o/a) | <!--s:o/a-->⭐ 54.8k<!--/s--> | x |"
        self.assertEqual(parse_displayed_stars(row), 54800)

    def test_round_thousands(self):
        row = "| [A](https://github.com/o/a) | <!--s:o/a-->⭐ 36k<!--/s--> | x |"
        self.assertEqual(parse_displayed_stars(row), 36000)

    def test_plain_count(self):
        row = "- [B](https://github.com/o/b) <!--s:o/b-->⭐ 823<!--/s-->"
        self.assertEqual(parse_displayed_stars(row), 823)

    def test_row_without_span_is_none(self):
        self.assertIsNone(parse_displayed_stars("| [C](https://c.example) | — | x |"))


class TestSortTopGatewaysTable(unittest.TestCase):
    @staticmethod
    def table(*rows):
        return (
            "intro text\n\n"
            "<!-- TOP-GATEWAYS:START -->\n"
            "| Gateway | Stars | What it is | Jump to |\n"
            "|---|---|---|---|\n" + "".join(f"{row}\n" for row in rows) +
            "<!-- TOP-GATEWAYS:END -->\n\n"
            "> footer note\n"
        )

    ROW_SMALL = "| [Small](https://github.com/o/small) | <!--s:o/small-->⭐ 823<!--/s--> | tiny | [S](#s) |"
    ROW_MID = "| [Mid](https://github.com/o/mid) | <!--s:o/mid-->⭐ 36k<!--/s--> | middle | [M](#m) |"
    ROW_BIG = "| [Big](https://github.com/o/big) | <!--s:o/big-->⭐ 45.1k<!--/s--> | large | [B](#b) |"
    ROW_NO_SPAN = "| [Hosted](https://hosted.example) | — | SaaS, no repo | [H](#h) |"

    def test_out_of_order_rows_get_sorted_descending(self):
        out = sort_top_gateways_table(self.table(self.ROW_MID, self.ROW_SMALL, self.ROW_BIG))
        self.assertEqual(out, self.table(self.ROW_BIG, self.ROW_MID, self.ROW_SMALL))

    def test_sorted_input_is_unchanged(self):
        text = self.table(self.ROW_BIG, self.ROW_MID, self.ROW_SMALL)
        self.assertEqual(sort_top_gateways_table(text), text)

    def test_rows_without_a_count_sink_to_the_bottom(self):
        out = sort_top_gateways_table(
            self.table(self.ROW_NO_SPAN, self.ROW_SMALL, self.ROW_BIG)
        )
        self.assertEqual(out, self.table(self.ROW_BIG, self.ROW_SMALL, self.ROW_NO_SPAN))

    def test_content_outside_markers_is_untouched(self):
        out = sort_top_gateways_table(self.table(self.ROW_MID, self.ROW_BIG))
        self.assertTrue(out.startswith("intro text\n\n"))
        self.assertTrue(out.endswith("> footer note\n"))

    def test_missing_markers_raise(self):
        with self.assertRaises(ValueError):
            sort_top_gateways_table("| Gateway | Stars |\n|---|---|\n| a | 1 |\n")

    def test_both_readmes_carry_markers_and_stay_sorted(self):
        """The real files must keep the markers and the by-stars promise."""
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        for name in ("README.md", "README.zh-CN.md"):
            text = (root / name).read_text(encoding="utf-8")
            self.assertEqual(
                sort_top_gateways_table(text), text, f"{name}: top-gateways table is out of order"
            )


class TestRenderReleases(unittest.TestCase):
    def test_empty_list_renders_placeholder(self):
        self.assertIn("No recent releases", render_releases_block([]))

    def test_renders_date_repo_and_link(self):
        block = render_releases_block(
            [
                {
                    "repo": "o/a",
                    "tag": "v1.2.0",
                    "name": "Big   release\nwith newline",
                    "published_at": "2026-06-10T12:00:00Z",
                    "url": "https://github.com/o/a/releases/tag/v1.2.0",
                }
            ]
        )
        # Plain-text date (not bold): items starting with a text node are
        # skipped by awesome-lint's list-item rule, keeping the block green.
        self.assertIn("- 2026-06-10 · ", block)
        self.assertNotIn("**2026-06-10**", block)
        self.assertIn("[o/a v1.2.0](https://github.com/o/a/releases/tag/v1.2.0)", block)
        self.assertIn("Big release with newline", block)

    def test_caps_at_twelve_entries(self):
        releases = [
            {
                "repo": f"o/r{i}",
                "tag": "v1",
                "name": "r",
                "published_at": f"2026-06-{i + 1:02d}T00:00:00Z",
                "url": "https://example.com",
            }
            for i in range(20)
        ]
        block = render_releases_block(releases)
        self.assertEqual(block.count("\n") + 1, 12)


if __name__ == "__main__":
    unittest.main()


class TestMaintenanceSignal(unittest.TestCase):
    """The quiet/archived table — the one number stars cannot give you.

    Stars are cumulative: a project that stopped shipping keeps its 36k and reads
    as healthy. LANDSCAPE.md tells readers to check the last commit before the
    feature matrix, so the list has to actually publish that check.
    """

    NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)

    def _activity(self):
        return {
            "live/active": {"pushed_at": "2026-08-11T00:00:00Z", "archived": False},
            "quiet/sixmonths": {"pushed_at": "2026-01-09T00:00:00Z", "archived": False},
            "dead/archived": {"pushed_at": "2026-06-11T00:00:00Z", "archived": True},
        }

    def test_days_since_counts_whole_days(self):
        self.assertEqual(days_since("2026-08-02T00:00:00Z", self.NOW), 10)

    def test_active_repo_is_not_listed(self):
        rows = quiet_entries(self._activity(), now=self.NOW)
        self.assertNotIn("live/active", [r["repo"] for r in rows])

    def test_archived_sorts_before_merely_quiet(self):
        rows = quiet_entries(self._activity(), now=self.NOW)
        self.assertEqual([r["repo"] for r in rows], ["dead/archived", "quiet/sixmonths"])

    def test_archived_is_listed_even_when_recently_pushed(self):
        """An archive can be days old — recency must not hide it."""
        rows = quiet_entries(
            {"x/y": {"pushed_at": "2026-08-10T00:00:00Z", "archived": True}}, now=self.NOW
        )
        self.assertEqual(len(rows), 1)

    def test_render_marks_archived_and_quiet_differently(self):
        block = render_maintenance_block(quiet_entries(self._activity(), now=self.NOW))
        self.assertIn("archived", block.lower())
        self.assertIn("Quiet for", block)

    def test_render_says_so_when_everything_is_healthy(self):
        self.assertIn("No listed project", render_maintenance_block([]))
        self.assertIn("没有条目", render_maintenance_block([], zh=True))

    def test_both_readmes_carry_the_markers(self):
        for name in ("README.md", "README.zh-CN.md"):
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertIn("<!-- MAINTENANCE:START -->", text)
                self.assertIn("<!-- MAINTENANCE:END -->", text)
