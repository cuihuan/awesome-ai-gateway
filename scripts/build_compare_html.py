#!/usr/bin/env python3
"""Render compare/*.md into standalone HTML pages (+ refresh sitemap.xml).

The deep-dive comparison articles target high-intent search queries ("litellm
alternatives 2026", "cloudflare vs vercel ai gateway"). As raw .md they only
exist as GitHub blobs, so their SEO value accrues to github.com, not the Pages
site. This builds a real HTML page per article — with title/description,
canonical, Open Graph, Twitter and JSON-LD Article/Breadcrumb metadata — that
lives on the Pages domain and is listed in sitemap.xml.

Stdlib only. The markdown→HTML conversion + link rewriting + metadata extraction
are pure and unit-tested; only build_all() touches the filesystem.

The supported markdown is exactly what these articles use (verified): H1/H2,
paragraphs, bullet/ordered lists, blockquotes, `---` rules, GFM tables, and
inline **bold** / `code` / [links](url). No code fences, images, nested lists,
H3+, or raw HTML.

Usage:
  python scripts/build_compare_html.py          # write compare/*.html + sitemap.xml
  python scripts/build_compare_html.py --check   # fail if any output is stale (CI)
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPARE = ROOT / "compare"
SITE = "https://cuihuan.github.io/awesome-ai-gateway/"
REPO_BLOB = "https://github.com/cuihuan/awesome-ai-gateway/blob/main/"
OG_IMAGE = SITE + "assets/cost-spread.png"


# ── Link rewriting ───────────────────────────────────────────────────────────

def rewrite_link(href: str) -> str:
    """Rewrite a markdown link target for the built HTML page.

    - absolute / anchor / mailto: unchanged
    - a sibling compare article `slug.md[#a]` → `slug.html[#a]` (stays on Pages)
    - anything else relative (../README.md, ../BENCHMARKS.md#x, scripts/x.py) →
      the GitHub blob URL, so reference links still resolve.
    """
    if href.startswith(("http://", "https://", "#", "mailto:", "//")):
        return href
    path, sep, frag = href.partition("#")
    frag = ("#" + frag) if sep else ""
    if "/" not in path and path.endswith(".md"):
        return path[:-3] + ".html" + frag
    clean = path.lstrip("./")
    while clean.startswith("../"):
        clean = clean[3:]
    clean = clean.lstrip("/")
    return REPO_BLOB + clean + frag


# ── Inline rendering ─────────────────────────────────────────────────────────

# Live-data spans (kept fresh by scripts/update_readme.py) collapse to their
# display text: the HTML page shows "⭐ 54.8k" / "~340", never the comment
# markers — md_to_html escapes literal text, so an unstripped marker would
# render visibly. Covers star counts (s:owner/repo) and the OpenRouter model
# count (omc, canonical value in data/models.json).
_STAR_SPAN = re.compile(
    r"<!--(?:s:[\w.\-]+/[\w.\-]+|omc)-->\s*(.*?)\s*<!--/(?:s|omc)-->", re.DOTALL
)

_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^()]*(?:\([^()]*\)[^()]*)*)\)")  # tolerate one level of ()s in the URL
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")  # single-asterisk emphasis, not part of **


def _emph(text: str) -> str:
    """Apply **bold** then *italic* (bold first so it isn't eaten by the italic rule)."""
    return _ITALIC.sub(r"<em>\1</em>", _BOLD.sub(r"<strong>\1</strong>", text))


def render_inline(text: str) -> str:
    """Convert inline markdown (code, links, bold, italic) in already-plain text to
    HTML, HTML-escaping all literal text. Order-safe for **[link](url)** and [**x**](u)."""
    codes: list[str] = []
    links: list[tuple[str, str]] = []

    def stash_code(m):
        codes.append("<code>" + html.escape(m.group(1)) + "</code>")
        return f"\x00C{len(codes) - 1}\x00"

    def stash_link(m):
        links.append((m.group(1), rewrite_link(m.group(2))))
        return f"\x00L{len(links) - 1}\x00"

    text = _CODE.sub(stash_code, text)
    text = _LINK.sub(stash_link, text)
    text = html.escape(text)
    text = _emph(text)

    def restore_link(m):
        label, url = links[int(m.group(1))]
        inner = _emph(html.escape(label))
        return f'<a href="{html.escape(url, quote=True)}">{inner}</a>'

    text = re.sub(r"\x00L(\d+)\x00", restore_link, text)
    text = re.sub(r"\x00C(\d+)\x00", lambda m: codes[int(m.group(1))], text)
    return text


# ── Block parsing ────────────────────────────────────────────────────────────

def _table(rows: list[str]) -> str:
    """rows: consecutive '| ... |' lines; row[1] is the |---| separator."""
    def cells(line):
        return [c.strip() for c in line.strip().strip("|").split("|")]

    head = cells(rows[0])
    body = [cells(r) for r in rows[2:]]  # skip header + separator
    out = ["<table>", "<thead><tr>"]
    out += [f"<th>{render_inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def md_to_html(md: str) -> str:
    """Convert the supported markdown subset to an HTML fragment (the <article>
    body). Pure — no I/O. Skips a leading H1 (it becomes the page <h1>/title)."""
    lines = _STAR_SPAN.sub(r"\1", md.replace("\r\n", "\n")).split("\n")
    out: list[str] = []
    i = 0
    seen_h1 = False
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        # headings
        if s.startswith("# "):
            if not seen_h1:        # the first H1 is the page title, rendered separately
                seen_h1 = True
                i += 1
                continue
            out.append(f"<h2>{render_inline(s[2:].strip())}</h2>")
            i += 1
            continue
        if s.startswith("## "):
            out.append(f"<h2>{render_inline(s[3:].strip())}</h2>")
            i += 1
            continue
        if re.fullmatch(r"-{3,}", s):
            out.append("<hr>")
            i += 1
            continue
        # table: a run of lines starting with '|'
        if s.startswith("|"):
            j = i
            while j < n and lines[j].strip().startswith("|"):
                j += 1
            out.append(_table([lines[k] for k in range(i, j)]))
            i = j
            continue
        # blockquote
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote>" + render_inline(" ".join(buf)) + "</blockquote>")
            continue
        # ordered list
        if re.match(r"\d+\.\s", s):
            buf = []
            while i < n and re.match(r"\d+\.\s", lines[i].strip()):
                buf.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            out.append("<ol>" + "".join(f"<li>{render_inline(x)}</li>" for x in buf) + "</ol>")
            continue
        # bullet list
        if re.match(r"[-*]\s", s):
            buf = []
            while i < n and re.match(r"[-*]\s", lines[i].strip()):
                buf.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            out.append("<ul>" + "".join(f"<li>{render_inline(x)}</li>" for x in buf) + "</ul>")
            continue
        # paragraph: gather until blank / next block
        buf = []
        while i < n and lines[i].strip() and not re.match(r"(#{1,2}\s|>|[-*]\s|\d+\.\s|\|)", lines[i].strip()) and not re.fullmatch(r"-{3,}", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + render_inline(" ".join(buf)) + "</p>")
    return "\n".join(out)


# ── Metadata extraction ──────────────────────────────────────────────────────

_STRIP_MD = [
    (_STAR_SPAN, r"\1"),  # first, so the inner "⭐ n" text survives for the rules below
    (re.compile(r"`([^`]+)`"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
    (re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)"), r"\1"),
]


def _plain(md_text: str) -> str:
    for pat, repl in _STRIP_MD:
        md_text = pat.sub(repl, md_text)
    return re.sub(r"\s+", " ", md_text).strip()


def extract_title(md: str) -> str:
    for line in md.splitlines():
        if line.strip().startswith("# "):
            return _plain(line.strip()[2:])
    return "Untitled"


def _desc_blocks(md: str):
    """Yield (raw, plain) for each text block (a run of prose/list/quote lines),
    splitting on blank lines, headings, tables and `---` rules."""
    cur: list[str] = []
    for line in md.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("|") or re.fullmatch(r"-{3,}", s):
            if cur:
                raw = " ".join(cur)
                yield raw, _plain(raw)
                cur = []
            continue
        s = re.sub(r"^>\s?", "", s)
        s = re.sub(r"^[-*]\s+", "", s)
        s = re.sub(r"^\d+\.\s+", "", s)
        cur.append(s)
    if cur:
        raw = " ".join(cur)
        yield raw, _plain(raw)


def extract_description(md: str, limit: int = 155) -> str:
    """First substantial prose block, markdown-stripped, truncated on a word
    boundary — skipping the italic '*Last updated … *' byline these articles open
    with (a single-asterisk-wrapped line, or one starting with 'Last updated')."""
    text = ""
    for raw, plain in _desc_blocks(md):
        if not plain:
            continue
        is_italic_byline = raw.startswith("*") and raw.rstrip().endswith("*") and not raw.startswith("**")
        if is_italic_byline or plain.lower().startswith(("last updated", "最近更新", "更新于")):
            continue
        text = plain
        break
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:") + "…"


_LASTMOD = re.compile(r"(?:Last updated|最近更新|更新于)\D*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def extract_lastmod(md: str) -> str | None:
    """The article's own '*Last updated YYYY-MM-DD*' byline date, for sitemap
    <lastmod>. None if the article carries no such date (no fabricated date)."""
    m = _LASTMOD.search(md)
    return m.group(1) if m else None


def slug_lang(filename: str) -> tuple[str, str]:
    """('litellm-alternatives-2026.md') → (slug, lang). '.zh-CN.md' → lang 'zh-CN'."""
    name = filename[:-3] if filename.endswith(".md") else filename
    if name.endswith(".zh-CN"):
        return name[: -len(".zh-CN")] + ".zh-CN", "zh-CN"
    return name, "en"


# ── Page template ────────────────────────────────────────────────────────────

def render_page(md: str, filename: str) -> str:
    slug, lang = slug_lang(filename)
    title = extract_title(md)
    desc = extract_description(md)
    body = md_to_html(md)
    url = f"{SITE}compare/{slug}.html"
    e = lambda s: html.escape(s, quote=True)
    # Machine-readable freshness — emitted only from the article's own "Last updated"
    # byline (never fabricated). AI answer engines (esp. Perplexity) weight recency, and
    # this content is genuinely refreshed; surface that as a parseable signal.
    lastmod = extract_lastmod(md)
    date_fields = (
        f'"datePublished":"{lastmod}","dateModified":"{lastmod}",' if lastmod else ""
    )
    modified_meta = (
        f'<meta property="article:modified_time" content="{lastmod}T00:00:00Z" />\n'
        if lastmod else ""
    )
    breadcrumb = (
        '{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":['
        f'{{"@type":"ListItem","position":1,"name":"Awesome AI Gateway","item":"{SITE}"}},'
        f'{{"@type":"ListItem","position":2,"name":{_json(title)},"item":"{url}"}}]}}'
    )
    article_ld = (
        '{"@context":"https://schema.org","@type":"Article",'
        f'"headline":{_json(title)},"description":{_json(desc)},'
        f'{date_fields}'
        f'"inLanguage":"{lang}","mainEntityOfPage":"{url}",'
        '"author":{"@type":"Organization","name":"Awesome AI Gateway"},'
        '"publisher":{"@type":"Organization","name":"Awesome AI Gateway"},'
        f'"isPartOf":"{SITE}","url":"{url}"}}'
    )
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}" />
<link rel="canonical" href="{url}" />
{modified_meta}<meta name="theme-color" content="#0d1117" />
<meta property="og:type" content="article" />
<meta property="og:site_name" content="Awesome AI Gateway" />
<meta property="og:url" content="{url}" />
<meta property="og:title" content="{e(title)}" />
<meta property="og:description" content="{e(desc)}" />
<meta property="og:image" content="{OG_IMAGE}" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{e(title)}" />
<meta name="twitter:description" content="{e(desc)}" />
<meta name="twitter:image" content="{OG_IMAGE}" />
<script type="application/ld+json">{article_ld}</script>
<script type="application/ld+json">{breadcrumb}</script>
<style>
  :root{{--bg:#0d1117;--card:#161b22;--border:#30363d;--fg:#f0f6fc;--mut:#8b949e;--blue:#58a6ff;--green:#3fb950;--red:#f85149}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
  a{{color:var(--blue);text-decoration:none}}a:hover{{text-decoration:underline}}
  .wrap{{max-width:820px;margin:0 auto;padding:28px 20px 80px}}
  nav.bc{{font-size:13px;color:var(--mut);margin-bottom:18px}}
  h1{{font-size:30px;line-height:1.25;margin:0 0 18px}}
  h2{{font-size:21px;margin:34px 0 10px;padding-top:6px;border-top:1px solid var(--border)}}
  p{{margin:0 0 14px}}
  ul,ol{{margin:0 0 16px;padding-left:22px}}li{{margin:4px 0}}
  blockquote{{margin:0 0 16px;padding:2px 16px;border-left:3px solid var(--blue);color:var(--mut)}}
  code{{background:var(--card);border:1px solid var(--border);border-radius:5px;padding:1px 5px;font-size:13px}}
  hr{{border:0;border-top:1px solid var(--border);margin:26px 0}}
  table{{width:100%;border-collapse:collapse;font-size:14px;margin:0 0 18px;display:block;overflow-x:auto}}
  th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:top}}
  th{{color:var(--mut);font-weight:600;white-space:nowrap}}
  footer{{margin-top:44px;color:var(--mut);font-size:13px;border-top:1px solid var(--border);padding-top:16px}}
</style>
</head>
<body>
<div class="wrap">
<nav class="bc"><a href="{SITE}">Awesome AI Gateway</a> › Comparisons</nav>
<article>
<h1>{e(title)}</h1>
{body}
</article>
<footer>
Part of <a href="{SITE}">Awesome AI Gateway</a> — a curated, bilingual, independently-benchmarked list of AI gateways.
<a href="https://github.com/cuihuan/awesome-ai-gateway">Star it on GitHub ★</a>
</footer>
</div>
</body>
</html>
"""


def render_hub(articles: list[dict]) -> str:
    """Render compare/index.html — the hub page listing every deep-dive comparison
    (newest first). `articles`: [{slug, title, description, lastmod}, ...]."""
    items = sorted(articles, key=lambda a: (a.get("lastmod") or "", a["title"]), reverse=True)
    url = SITE + "compare/"
    title = "AI Gateway Comparisons (2026) — data-backed head-to-heads"
    desc = ("Independent, data-backed AI gateway comparisons: LiteLLM vs OpenRouter vs Portkey, "
            "LiteLLM & OpenRouter alternatives, Cloudflare vs Vercel, best self-hosted, one-api vs new-api.")
    e = lambda s: html.escape(s, quote=True)
    cards, ld = [], []
    for i, a in enumerate(items, 1):
        date = f' · <span class="d">updated {a["lastmod"]}</span>' if a.get("lastmod") else ""
        cards.append(
            f'<li><a class="t" href="{a["slug"]}.html">{e(a["title"])}</a>{date}'
            f'<p>{e(a["description"])}</p></li>'
        )
        ld.append(f'{{"@type":"ListItem","position":{i},"url":"{SITE}compare/{a["slug"]}.html","name":{_json(a["title"])}}}')
    collection_ld = (
        '{"@context":"https://schema.org","@type":"CollectionPage",'
        f'"name":{_json(title)},"description":{_json(desc)},"url":"{url}",'
        f'"isPartOf":"{SITE}","mainEntity":{{"@type":"ItemList","itemListElement":[{",".join(ld)}]}}}}'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}" />
<link rel="canonical" href="{url}" />
<meta name="theme-color" content="#0d1117" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="Awesome AI Gateway" />
<meta property="og:url" content="{url}" />
<meta property="og:title" content="{e(title)}" />
<meta property="og:description" content="{e(desc)}" />
<meta property="og:image" content="{OG_IMAGE}" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{e(title)}" />
<meta name="twitter:description" content="{e(desc)}" />
<meta name="twitter:image" content="{OG_IMAGE}" />
<script type="application/ld+json">{collection_ld}</script>
<style>
  :root{{--bg:#0d1117;--card:#161b22;--border:#30363d;--fg:#f0f6fc;--mut:#8b949e;--blue:#58a6ff}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
  a{{color:var(--blue);text-decoration:none}}a:hover{{text-decoration:underline}}
  .wrap{{max-width:820px;margin:0 auto;padding:28px 20px 80px}}
  nav.bc{{font-size:13px;color:var(--mut);margin-bottom:18px}}
  h1{{font-size:28px;margin:0 0 8px}}
  .sub{{color:var(--mut);margin:0 0 22px}}
  ul.cards{{list-style:none;margin:0;padding:0}}
  ul.cards li{{border:1px solid var(--border);background:var(--card);border-radius:10px;padding:14px 16px;margin:0 0 12px}}
  a.t{{font-size:18px;font-weight:600}}
  .d{{color:var(--mut);font-size:12px}}
  ul.cards p{{margin:6px 0 0;color:var(--mut);font-size:14px}}
  footer{{margin-top:40px;color:var(--mut);font-size:13px;border-top:1px solid var(--border);padding-top:16px}}
</style>
</head>
<body>
<div class="wrap">
<nav class="bc"><a href="{SITE}">Awesome AI Gateway</a> &rsaquo; Comparisons</nav>
<h1>AI Gateway Comparisons (2026)</h1>
<p class="sub">Data-backed head-to-heads for the gateway questions people actually search — each grounded in the same <a href="{SITE}">reproducible cost benchmark and scorecard</a>.</p>
<ul class="cards">
{"".join(cards)}
</ul>
<footer>
Part of <a href="{SITE}">Awesome AI Gateway</a> — a curated, bilingual, independently-benchmarked list of AI gateways.
<a href="https://github.com/cuihuan/awesome-ai-gateway">Star it on GitHub &#9733;</a>
</footer>
</div>
</body>
</html>
"""


def _json(s: str) -> str:
    """JSON-string-encode for inline JSON-LD (escapes quotes/backslashes/<)."""
    return '"' + (s.replace("\\", "\\\\").replace('"', '\\"')
                  .replace("\n", "\\n").replace("\r", "\\r").replace("<", "\\u003c")) + '"'


# ── Sitemap ──────────────────────────────────────────────────────────────────

def build_sitemap(articles: list[tuple[str, str | None]]) -> str:
    """articles: [(slug, lastmod_or_None), ...]. The home page has no lastmod
    (its 'daily' changefreq already signals freshness)."""
    # litellm-vs-openrouter.html, openrouter-alternatives.html and
    # self-hosted-llm-gateway.html are deliberately absent: they canonicalize to
    # their compare/ successors (same query, one indexed winner), and a sitemap
    # should list canonical URLs only. Their zh-CN twins remain canonical pages.
    rows = [(SITE, "1.0", "daily", None)]
    rows.append((SITE + "litellm-vs-openrouter.zh-CN.html", "0.6", "monthly", None))  # zh-CN localization
    rows.append((SITE + "openrouter-alternatives.zh-CN.html", "0.6", "monthly", None))  # zh-CN localization
    rows.append((SITE + "self-hosted-llm-gateway.zh-CN.html", "0.6", "monthly", None))  # zh-CN localization
    rows.append((SITE + "reduce-llm-api-costs.html", "0.7", "monthly", None))  # guide article
    rows.append((SITE + "reduce-llm-api-costs.zh-CN.html", "0.6", "monthly", None))  # zh-CN localization
    rows.append((SITE + "gateway-picker.html", "0.8", "monthly", None))   # interactive decision tool
    rows.append((SITE + "cost-calculator.html", "0.8", "monthly", None))  # interactive tool
    lastmods = [lm for _, lm in articles if lm]
    rows.append((SITE + "compare/", "0.7", "weekly", max(lastmods) if lastmods else None))
    for slug, lastmod in sorted(articles):
        rows.append((f"{SITE}compare/{slug}.html", "0.8", "monthly", lastmod))
    parts = []
    for loc, pr, cf, lm in rows:
        lm_line = f"\n    <lastmod>{lm}</lastmod>" if lm else ""
        parts.append(
            f"  <url>\n    <loc>{loc}</loc>{lm_line}\n    <changefreq>{cf}</changefreq>\n    <priority>{pr}</priority>\n  </url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(parts)
        + "\n</urlset>\n"
    )


# ── Build / check ────────────────────────────────────────────────────────────

def _targets():
    files = sorted(p for p in COMPARE.glob("*.md"))
    return files


def build_all(check: bool = False) -> int:
    files = _targets()
    metas = []
    stale = []

    def diff(path, content):
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(str(path.relative_to(ROOT)))

    for md_path in files:
        md = md_path.read_text(encoding="utf-8")
        slug, lang = slug_lang(md_path.name)
        metas.append({"slug": slug, "lang": lang, "title": extract_title(md),
                      "description": extract_description(md), "lastmod": extract_lastmod(md)})
        html_path = COMPARE / f"{slug}.html"
        rendered = render_page(md, md_path.name)
        if check:
            diff(html_path, rendered)
        else:
            html_path.write_text(rendered, encoding="utf-8")

    hub = render_hub(metas)
    sitemap = build_sitemap([(m["slug"], m["lastmod"]) for m in metas])
    if check:
        diff(COMPARE / "index.html", hub)
        diff(ROOT / "sitemap.xml", sitemap)
        if stale:
            print("::error::stale generated files — run 'python scripts/build_compare_html.py':", file=sys.stderr)
            for s in stale:
                print(f"  - {s}", file=sys.stderr)
            return 1
        print(f"compare HTML + hub + sitemap up to date ({len(metas)} articles)")
        return 0

    (COMPARE / "index.html").write_text(hub, encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"built {len(metas)} compare pages + hub + sitemap.xml")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render compare/*.md to HTML and refresh sitemap.xml.")
    ap.add_argument("--check", action="store_true", help="fail if any output is stale (don't write)")
    a = ap.parse_args(argv)
    return build_all(check=a.check)


if __name__ == "__main__":
    sys.exit(main())
