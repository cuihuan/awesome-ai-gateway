"""Guards against mechanical edit damage in the prose files.

Bulk find-and-replace is how most content edits happen here (agents and
humans alike), and a half-applied replacement leaves text that reads as
nonsense while every other gate — lint, tests, link check — stays green.
That happened three times in one day: a sentence left as "only one is safe
under concurrency — implemented by two survive concurrency", a clause
duplicated onto itself, and a blind date replace that rewrote two unrelated
dates. Each was caught by a reader, not by a check. These tests are that
check.

They are deliberately narrow: every pattern here has produced a real defect
in this repo. If a rule starts crying wolf, tighten it or delete it — a
noisy guard gets ignored, which is worse than no guard.

Known limit, stated so nobody mistakes green for safe: these catch
*structural* damage — duplication, truncated markers, links to files that
do not exist. They do NOT catch a replacement that leaves grammatical
nonsense ("implemented by two survive concurrency"), because the only
signal available for that — a content word repeating within a short window
— fires 800+ times on this corpus from link-text-versus-anchor pairs alone.
That class still needs a reader, or an adversarial verifier told to look
for it.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = sorted(
    [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "HANDBOOK.md",
     ROOT / "BENCHMARKS.md", ROOT / "BENCHMARKS.zh-CN.md", ROOT / "CONTRIBUTING.md"]
    + list((ROOT / "docs").glob("*.md"))
    + list((ROOT / "compare").glob("*.md"))
)

# Words that legitimately repeat in English prose ("had had", "that that"),
# plus tokens that repeat inside identifiers and release names.
DOUBLE_WORD_ALLOW = {
    "had", "that", "very", "no", "yes", "long", "sudo", "manifest", "router",
    "api", "gateway", "cache", "ai",
}


def _strip_code(text: str) -> str:
    """Blank out fenced blocks and inline code — identifiers legitimately
    repeat (`x` over `y` over `z`). They are replaced with a placeholder
    rather than deleted, so removing them can't fuse two words into a
    false "doubled word" or two dashes into a false empty pair."""
    text = re.sub(r"```.*?```", "\n", text, flags=re.S)
    # A non-word placeholder: two adjacent inline-code spans must not read as
    # a doubled word, and a stripped span must not fuse its neighbours.
    return re.sub(r"`[^`\n]*`", "\u27e6c\u27e7", text)


class TestNoEditDamage(unittest.TestCase):
    def test_no_duplicated_adjacent_phrase(self):
        """A replacement applied over its own output duplicates a clause."""
        for path in FILES:
            body = _strip_code(path.read_text(encoding="utf-8"))
            for match in re.finditer(r"([a-z][a-z ,'-]{18,60}?), \1", body):
                self.fail(f"{path.name}: duplicated phrase — …{match.group(0)[:90]}…")

    def test_no_doubled_word(self):
        for path in FILES:
            body = _strip_code(path.read_text(encoding="utf-8"))
            for match in re.finditer(r"\b([A-Za-z]{3,})\s+\1\b", body):
                if match.group(1).lower() in DOUBLE_WORD_ALLOW:
                    continue
                start = max(0, match.start() - 45)
                self.fail(f"{path.name}: doubled word — …{body[start:match.end() + 45]}…")

    def test_no_dangling_em_dash_pair(self):
        """Two dash runs separated by whitespace is a half-removed clause.

        Note the Chinese convention: "——" is a single piece of punctuation
        written as two em-dashes, so only dash runs with whitespace *between*
        them count, never adjacent ones."""
        for path in FILES:
            body = _strip_code(path.read_text(encoding="utf-8"))
            for match in re.finditer(r"—+[ \t]+—+", body):
                start = max(0, match.start() - 60)
                self.fail(f"{path.name}: empty dash pair — …{body[start:match.end() + 60]}…")

    def test_no_empty_or_placeholder_links(self):
        for path in FILES:
            body = path.read_text(encoding="utf-8")
            for pattern, label in ((r"\]\(\s*\)", "empty target"),
                                   (r"\]\(TODO|\]\(FIXME|\]\(#TODO", "placeholder target")):
                match = re.search(pattern, body)
                self.assertIsNone(match, f"{path.name}: link with {label}")

    def test_no_unbalanced_bold_marker(self):
        """An odd total of ** in a file is a truncated emphasis span.

        Counted per file, not per line: a bold span may legitimately wrap
        across a soft line break in these documents."""
        for path in FILES:
            body = _strip_code(path.read_text(encoding="utf-8"))
            self.assertEqual(body.count("**") % 2, 0,
                             f"{path.name}: odd number of ** markers — an emphasis span is truncated")


class TestRelativeLinksResolve(unittest.TestCase):
    """A language switcher or chapter link pointing at a file that does not
    exist yet is the most common casualty of shipping a translation late."""

    def test_relative_targets_exist(self):
        for path in FILES:
            body = _strip_code(path.read_text(encoding="utf-8"))
            for match in re.finditer(r"\]\((?!https?:|#|mailto:)([^)#\s]+)", body):
                target = (path.parent / match.group(1)).resolve()
                self.assertTrue(
                    target.exists(),
                    f"{path.name}: link to missing file {match.group(1)}",
                )


if __name__ == "__main__":
    unittest.main()
