#!/usr/bin/env python3
"""Daily content refresher for awesome-ai-gateway.

Updates, in README.md, README.zh-CN.md and compare/*.md:
  1. Live-data spans — in the READMEs *and* every compare/*.md source, so no
     reader-facing number is ever hand-typed (the compare HTML is rebuilt from
     the md by scripts/build_compare_html.py, which renders each span's
     display text):
       - star counts inside ``<!--s:owner/repo-->...<!--/s-->``;
       - the OpenRouter model count inside ``<!--omc-->...<!--/omc-->``
         (canonical value: data/models.json ``openrouter_model_count``);
       - the data-retention matrix's verified-date inside
         ``<!--rvd-->...<!--/rvd-->`` (canonical value:
         data/data_retention.json ``as_of``).
  2. READMEs only: the "Top gateways (by stars)" table between
     ``<!-- TOP-GATEWAYS:START -->`` and ``<!-- TOP-GATEWAYS:END -->`` — rows
     re-sorted descending so the heading's by-stars promise survives the
     refreshed counts.
  3. READMEs only: the "Recent releases" block between
     ``<!-- RELEASES:START -->`` and ``<!-- RELEASES:END -->`` (latest
     releases of repos listed in data/projects.json).
  4. READMEs only: the "Maintenance signal" table between
     ``<!-- MAINTENANCE:START -->`` and ``<!-- MAINTENANCE:END -->`` — every
     tracked repo that is archived or has taken no commit in QUIET_AFTER_DAYS.
     Star counts only ever go up, so a project that stopped shipping looks
     identical to one that did not; this is the correction, and it comes from
     the same /repos/{slug} response the star refresh already fetches.

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
RETENTION_FILE = ROOT / "data" / "data_retention.json"
RELEASES_FILE = ROOT / "data" / "releases.json"

STAR_MARKER_RE = re.compile(r"<!--s:([\w.\-]+/[\w.\-]+)-->.*?<!--/s-->", re.DOTALL)
RELEASES_START = "<!-- RELEASES:START -->"
RELEASES_END = "<!-- RELEASES:END -->"
MAINTENANCE_START = "<!-- MAINTENANCE:START -->"
MAINTENANCE_END = "<!-- MAINTENANCE:END -->"
#: A project this long without a commit is a selection signal, not a footnote.
QUIET_AFTER_DAYS = 180
TOP_GATEWAYS_START = "<!-- TOP-GATEWAYS:START -->"
TOP_GATEWAYS_END = "<!-- TOP-GATEWAYS:END -->"
DISPLAYED_STARS_RE = re.compile(r"<!--s:[\w.\-]+/[\w.\-]+-->[^0-9<]*([0-9.]+)\s*(k?)", re.IGNORECASE)
# OpenRouter model count — single-sourced from data/models.json (openrouter_model_count).
OMC_MARKER_RE = re.compile(r"<!--omc-->.*?<!--/omc-->", re.DOTALL)
# Retention-matrix verified-date — single-sourced from data/data_retention.json as_of.
RVD_MARKER_RE = re.compile(r"<!--rvd-->.*?<!--/rvd-->", re.DOTALL)
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
    # index.html too: its FAQPage JSON-LD is the artifact built to be quoted verbatim
    # by AI answers, and it carried a hand-typed "400+ models" — OpenRouter's marketing
    # figure, which data/models.json explicitly records as marketing and contradicts.
    # A number in the citation surface that nothing refreshes is a number that will drift.
    landing = [root / "index.html"]
    return readmes + landing + sorted((root / "compare").glob("*.md"))


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


def load_retention_as_of(retention_file: Path = RETENTION_FILE) -> str:
    return json.loads(retention_file.read_text(encoding="utf-8"))["as_of"]


def replace_retention_date_markers(text: str, as_of: str) -> str:
    """Rewrite every ``<!--rvd-->…<!--/rvd-->`` span to the matrix's as_of date.

    The READMEs print 'verified <date>' next to the data-retention matrix; the
    date used to be hand-typed prose that nothing compared against
    data/data_retention.json. Rendering it from the JSON (whose as_of only a
    real re-review moves, enforced by check_freshness.py) means the prose can
    never claim a verification the data file doesn't back.
    """
    return RVD_MARKER_RE.sub(f"<!--rvd-->{as_of}<!--/rvd-->", text)


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
        # Plain-text date first: awesome-lint's list-item rule skips items that
        # start with a text node, so the generated block stays lint-green.
        lines.append(f"- {date} · [{rel['repo']} {rel['tag']}]({rel['url']}) — {title}")
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


def fetch_repo_meta(repos: list[str]) -> tuple[dict[str, int], dict[str, dict]]:
    """One pass over /repos/{slug}: star counts, plus last-push date and archived flag.

    The activity half costs nothing extra — it is in the same response the star
    refresh already fetches — and it is what the star count cannot tell you. A
    project can sit at 36k stars and not have taken a commit in seven months.
    """
    stars: dict[str, int] = {}
    activity: dict[str, dict] = {}
    for slug in repos:
        data = github_get(f"/repos/{slug}")
        if not data:
            continue
        if isinstance(data.get("stargazers_count"), int):
            stars[slug] = data["stargazers_count"]
        if data.get("pushed_at"):
            activity[slug] = {
                "pushed_at": data["pushed_at"],
                "archived": bool(data.get("archived")),
            }
    return stars, activity


def days_since(iso_ts: str, now: datetime | None = None) -> int:
    """Whole days between an ISO-8601 UTC timestamp and now."""
    then = datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - then).days


def quiet_entries(activity: dict[str, dict], quiet_after_days: int = QUIET_AFTER_DAYS,
                  now: datetime | None = None) -> list[dict]:
    """Tracked repos that are archived, or have taken no commit in a long while.

    Sorted worst-first: archived before merely quiet, then by how long it has been.
    """
    rows = []
    for slug, meta in activity.items():
        stale_days = days_since(meta["pushed_at"], now)
        if meta["archived"] or stale_days >= quiet_after_days:
            rows.append({
                "repo": slug,
                "days": stale_days,
                "last_commit": meta["pushed_at"][:10],
                "archived": meta["archived"],
            })
    rows.sort(key=lambda r: (not r["archived"], -r["days"]))
    return rows


def render_maintenance_block(rows: list[dict], zh: bool = False) -> str:
    """Markdown table of the quiet/archived entries, or an all-clear line."""
    if not rows:
        return ("*当前没有条目处于归档或长期停更状态。*" if zh
                else "*No listed project is currently archived or long-quiet.*")
    head = (["项目", "最后提交", "状态"] if zh else ["Project", "Last commit", "Status"])
    out = ["| " + " | ".join(head) + " |", "|---|---|---|"]
    for r in rows:
        months = r["days"] // 30
        if r["archived"]:
            status = "⛔ 仓库已归档（只读）" if zh else "⛔ Repo archived (read-only)"
        elif zh:
            status = f"⚠️ 已静默约 {months} 个月"
        else:
            status = f"⚠️ Quiet for ~{months} months"
        # Slug as code, not a link: every one of these repos is already linked from its
        # own entry, and awesome-lint (correctly) rejects a second link to the same URL.
        out.append(f"| `{r['repo']}` | {r['last_commit']} | {status} |")
    return "\n".join(out)


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
    stars, activity = fetch_repo_meta(marked_repos)
    quiet = quiet_entries(activity)
    print(f"quiet/archived among tracked repos: {len(quiet)}")
    print(f"fetching latest releases for {len(tracked)} repos...")
    releases = fetch_latest_releases(tracked)

    block = render_releases_block(releases)
    model_count_display = render_openrouter_model_count(load_openrouter_model_count())
    retention_as_of = load_retention_as_of()
    changed_files = []
    for path in span_files:
        original = path.read_text(encoding="utf-8")
        updated = replace_star_markers(original, stars)
        updated = replace_model_count_markers(updated, model_count_display)
        updated = replace_retention_date_markers(updated, retention_as_of)
        if path in README_FILES:  # table + releases blocks only exist there
            updated = sort_top_gateways_table(updated)
            updated = replace_between_markers(updated, RELEASES_START, RELEASES_END, block)
            updated = replace_between_markers(
                updated, MAINTENANCE_START, MAINTENANCE_END,
                render_maintenance_block(quiet, zh=path.name.endswith("zh-CN.md")),
            )
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_files.append(path.name)

    RELEASES_FILE.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "stars": stars,
                "activity": activity,
                "quiet": quiet,
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
