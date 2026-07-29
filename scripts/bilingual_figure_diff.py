#!/usr/bin/env python3
"""Advisory: list figures that appear in a chapter but not in its Chinese twin.

The recurring defect here is not a wrong number — it is a number corrected in
English and left stale in Chinese. It has happened to the measured overheads, a
study's denominator and a section's divergence count, each time surviving lint,
tests and the link checker, because all of those read one file at a time.

This is deliberately NOT a test. Translation reorders sentences, renders large
magnitudes with 万, and moves figures between prose and link text, so exact
parity produces far more noise than signal — a gate that cries wolf gets
ignored, which is worse than no gate. It prints candidates for a human to scan
after editing a chapter; `scripts/regen.sh` runs it as the last advisory step.

Usage: python3 scripts/bilingual_figure_diff.py [--all]
       (--all includes README/BENCHMARKS, whose twins are not literal
        translations and therefore diverge legitimately)
"""

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHAPTERS = [
    "docs/protocol-translation", "docs/gateway-anatomy", "docs/failover-reliability",
    "docs/caching-economics", "docs/virtual-keys-metering", "docs/mcp-agent-gateways",
    "docs/routing-landscape", "docs/observability-landscape",
]
WIDE = ["README", "BENCHMARKS"]

# Figures worth flagging: a number carrying a unit (%, ×, ms, $) or two or more
# decimal places — i.e. a measurement, multiplier or price. Deliberately
# excluded because they are noise, not claims: arXiv identifiers (2604.08407)
# and single-decimal section references (§3.1), which a translation renumbers
# or drops freely.
ARXIV = re.compile(r"\b\d{4}\.\d{4,5}\b")
TOKEN = re.compile(r"\$?\d+\.\d{2,}|\d+(?:\.\d+)?\s?(?:%|×|倍|ms|美元)")


def figures(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", " ", text)
    # Link targets BEFORE bare URLs: `https?://\S+` is greedy to whitespace, so
    # it swallows the closing paren of `](url)` and leaves an unclosed `](`,
    # after which the link-target pattern eats everything up to the next `)`
    # anywhere in the file. That silently deleted whole paragraphs — and the
    # figures in them — making this tool invent differences that did not exist.
    text = re.sub(r"\]\([^)\s]*\)", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = ARXIV.sub(" ", text)
    return Counter(t.strip() for t in TOKEN.findall(text))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    stems = CHAPTERS + (WIDE if "--all" in argv else [])
    total = 0
    for stem in stems:
        en, zh = f"{stem}.md", f"{stem}.zh-CN.md"
        if not (ROOT / zh).exists():
            continue
        a, b = figures(en), figures(zh)
        diffs = [(t, a[t], b[t]) for t in sorted(set(a) | set(b)) if a[t] != b[t]]
        if diffs:
            total += len(diffs)
            print(f"\n{stem}:")
            for token, x, y in diffs:
                print(f"   {token:>8}  EN×{x}  中文×{y}")
    if total:
        print(f"\n{total} figure(s) differ between a chapter and its twin — check whether a "
              f"correction landed in only one language, or the wording legitimately differs.")
    else:
        print("Chapter figures match their Chinese twins.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
