#!/usr/bin/env python3
"""Daily content refresher for awesome-ai-gateway.

Updates, in README.md, README.zh-CN.md and compare/*.md:
  1. Star counts inside ``<!--s:owner/repo-->...<!--/s-->`` markers and the
     OpenRouter model count inside ``<!--omc-->...<!--/omc-->`` markers
     (canonical value: data/models.json ``openrouter_model_count``) — in the
     READMEs *and* every compare/*.md source, so no reader-facing count is
     ever hand-typed (the compare HTML is rebuilt from the md by
     scripts/build_compare_html.py, which renders each span's display text).
  2. READMEs only: the "Top gateways (by stars)" table between
     ``<!-- TOP-GATEWAYS:START -->`` and ``<!-- TOP-GATEWAYS:END -->`` — rows
     re-sorted descending so the heading's by-stars promise survives the
     refreshed counts.
  3. READMEs only: the "Recent releases" block between
     ``<!-- RELEASES:START -->`` and ``<!-- RELEASES:END -->`` (latest
     releases of repos listed in data/projects.json).

Also writes data/releases.json for programmatic consumers.

Stdlib only. Uses GITHUB_TOKEN from the environment when present
(unauthenticated requests hit GitHub's 60 req/h limit fast).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README_FILES = [ROOT / "README.md", ROOT / "README.zh-CN.md"]
COMPARE_DIR = ROOT / "compare"
PROJECTS_FILE = ROOT / "data" / "projects.json"
MODELS_FILE = ROOT / "data" / "models.json"
RELEASES_FILE = ROOT / "data" / "releases.json"

STAR_MARKER_RE = re.compile(r"<!--s:([\w.\-]+/[\w.\-]+)-->.*?<!--/s-->", re.DOTALL)
RELEASES_START = "<!-- RELEASES:START -->"
RELEASES_END = "<!-- RELEASES:END -->"
TOP_GATEWAYS_START = "<!-- TOP-GATEWAYS:START -->"
TOP_GATEWAYS_END = "<!-- TOP-GATEWAYS:END -->"
DISPLAYED_STARS_RE = re.compile(r"<!--s:[\w.\-]+/[\w.\-]+-->[^0-9<]*([0-9.]+)\s*(k?)", re.IGNORECASE)
# OpenRouter model count — single-sourced from data/models.json (openrouter_model_count).
OMC_MARKER_RE = re.compile(r"<!--omc-->.*?<!--/omc-->", re.DOTALL)
MAX_RELEASES_SHOWN = 12
API_BASE = "https://api.github.com"


def format_stars(count: int) -> str:
    """Render a star count the way GitHub does: 823, 5.7k, 50.3k."""
    if count < 1000:
        return str(count)
    value = count / 1000
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text}k"


def star_span_files(root: Path = ROOT) -> list[Path]:
    """Every file whose ``<!--s:-->`` spans the refresh owns: the two READMEs
    plus each compare/*.md source. Compare pages quote star counts in prose
    and tables; giving those spans too means one pipeline feeds every
    reader-facing count instead of leaving hand-typed copies to rot."""
    readmes = [root / p.name for p in README_FILES]
    return readmes + sorted((root / "compare").glob("*.md"))


def collect_marked_repos(text: str) -> list[str]:
    """Unique owner/repo slugs referenced by star markers, in order."""
    seen: list[str] = []
    for match in STAR_MARKER_RE.finditer(text):
        slug = match.group(1)
        if slug not in seen:
            seen.append(slug)
    return seen


def replace_star_markers(text: str, stars: dict[str, int]) -> str:
    """Rewrite every marker whose repo has a fetched count; keep others as-is."""

    def repl(match: re.Match) -> str:
        slug = match.group(1)
        if slug not in stars:
            return match.group(0)
        return f"<!--s:{slug}-->⭐ {format_stars(stars[slug])}<!--/s-->"

    return STAR_MARKER_RE.sub(repl, text)


def render_openrouter_model_count(count: int) -> str:
    """Display form of the OpenRouter model count: 342 → '~340'.

    Rounded to the nearest 10 because the live list moves week to week; the
    exact count and its source/date live in data/models.json.
    """
    return f"~{round(count, -1)}"


def replace_model_count_markers(text: str, display: str) -> str:
    """Rewrite every ``<!--omc-->…<!--/omc-->`` span to the canonical display.

    The READMEs once said '~340 models' in one table and '400+' (the vendor's
    marketing figure) three sections later; rendering every mention from
    data/models.json makes that class of self-contradiction unrepresentable.
    """
    return OMC_MARKER_RE.sub(f"<!--omc-->{display}<!--/omc-->", text)


def load_openrouter_model_count(models_file: Path = MODELS_FILE) -> int:
    return json.loads(models_file.read_text(encoding="utf-8"))["openrouter_model_count"]["count"]


def parse_displayed_stars(row: str) -> int | None:
    """Approximate count from a row's rendered star span: '⭐ 54.8k' → 54800.

    Reads the display text (not the API) so sorting works offline and stays
    consistent with what the reader actually sees.
    """
    match = DISPLAYED_STARS_RE.search(row)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return round(value * 1000) if match.group(2) else round(value)


def sort_top_gateways_table(text: str) -> str:
    """Re-sort the 'Top gateways (by stars)' table rows, highest stars first.

    The heading promises a by-stars ordering, but hand-inserted rows and the
    daily star refresh let the table drift out of order — so the same script
    that refreshes the numbers restores the promise. The table sits between
    the TOP-GATEWAYS markers; the header and separator rows stay put, data
    rows are sorted descending by their displayed count, and rows without a
    parsable count sink to the bottom in their original relative order.
    Raises ValueError when the markers are missing so a README restructure
    cannot silently drop the guarantee.
    """
    pattern = re.compile(
        re.escape(TOP_GATEWAYS_START) + r"(.*?)" + re.escape(TOP_GATEWAYS_END),
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise ValueError(f"markers {TOP_GATEWAYS_START!r}/{TOP_GATEWAYS_END!r} not found")
    lines = match.group(1).strip("\n").split("\n")
    if len(lines) < 3:  # header + separator + at least one data row
        return text
    header, separator, rows = lines[0], lines[1], lines[2:]

    def key(row: str) -> int:
        stars = parse_displayed_stars(row)
        return -1 if stars is None else stars

    body = "\n".join([header, separator] + sorted(rows, key=key, reverse=True))
    return pattern.sub(
        lambda _: f"{TOP_GATEWAYS_START}\n{body}\n{TOP_GATEWAYS_END}", text, count=1
    )


def replace_between_markers(text: str, start: str, end: str, body: str) -> str:
    """Replace content between two literal markers (markers stay in place)."""
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"markers {start!r}/{end!r} not found")
    return pattern.sub(f"{start}\n{body}\n{end}", text)


def render_releases_block(releases: list[dict]) -> str:
    """Markdown bullets for the releases section, newest first."""
    if not releases:
        return "*No recent releases fetched yet.*"
    lines = []
    for rel in releases[:MAX_RELEASES_SHOWN]:
        date = rel["published_at"][:10]
        title = rel.get("name") or rel["tag"]
        # Collapse whitespace/newlines that some projects put in release names.
        title = " ".join(title.split())
        if len(title) > 80:
            title = title[:77] + "..."
        lines.append(f"- **{date}** · [{rel['repo']} {rel['tag']}]({rel['url']}) — {title}")
    return "\n".join(lines)


def github_get(path: str) -> dict | None:
    request = urllib.request.Request(f"{API_BASE}{path}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "awesome-ai-gateway-updater")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        print(f"warn: GET {path} -> HTTP {err.code}", file=sys.stderr)
        return None
    except (urllib.error.URLError, TimeoutError) as err:
        print(f"warn: GET {path} -> {err}", file=sys.stderr)
        return None


def fetch_stars(repos: list[str]) -> dict[str, int]:
    stars: dict[str, int] = {}
    for slug in repos:
        data = github_get(f"/repos/{slug}")
        if data and isinstance(data.get("stargazers_count"), int):
            stars[slug] = data["stargazers_count"]
    return stars


def fetch_latest_releases(repos: list[str]) -> list[dict]:
    releases: list[dict] = []
    for slug in repos:
        data = github_get(f"/repos/{slug}/releases/latest")
        if not data or not data.get("published_at"):
            continue
        releases.append(
            {
                "repo": slug,
                "tag": data.get("tag_name", ""),
                "name": data.get("name") or data.get("tag_name", ""),
                "published_at": data["published_at"],
                "url": data.get("html_url", f"https://github.com/{slug}/releases"),
            }
        )
    releases.sort(key=lambda r: r["published_at"], reverse=True)
    return releases


def main() -> int:
    tracked = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))["release_tracked_repos"]

    span_files = star_span_files()
    marked_repos: list[str] = []
    for path in span_files:
        for slug in collect_marked_repos(path.read_text(encoding="utf-8")):
            if slug not in marked_repos:
                marked_repos.append(slug)

    print(f"fetching stars for {len(marked_repos)} repos...")
    stars = fetch_stars(marked_repos)
    print(f"fetching latest releases for {len(tracked)} repos...")
    releases = fetch_latest_releases(tracked)

    block = render_releases_block(releases)
    model_count_display = render_openrouter_model_count(load_openrouter_model_count())
    changed_files = []
    for path in span_files:
        original = path.read_text(encoding="utf-8")
        updated = replace_star_markers(original, stars)
        updated = replace_model_count_markers(updated, model_count_display)
        if path in README_FILES:  # table + releases blocks only exist there
            updated = sort_top_gateways_table(updated)
            updated = replace_between_markers(updated, RELEASES_START, RELEASES_END, block)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_files.append(path.name)

    RELEASES_FILE.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "stars": stars,
                "releases": releases,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"stars fetched: {len(stars)}/{len(marked_repos)}; releases: {len(releases)}")
    print(f"updated: {', '.join(changed_files) if changed_files else 'no README changes'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
