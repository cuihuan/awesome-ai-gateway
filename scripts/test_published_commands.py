#!/usr/bin/env python3
"""Every runnable command this repo publishes must actually run.

The whole claim of this list is "check every number yourself". For months the
docs told readers to verify their gateway with:

    node probe/fidelity.mjs
    node probe/xformat.mjs

Both exit immediately with ``--gateway <name> required``. The one command that
distinguishes this repo from a vendor blog post did not work — in four places,
in both languages, while the surrounding prose promised "no API keys needed".

So the shape of a published probe invocation is pinned here. This cannot execute
the probes (they live in a sibling repository), but it can enforce what the probe
sources require, which is what actually rotted: a bare invocation with no flags.

Verified 2026-08-12 by cloning llm-gateway-bench and running them:
  - ``node probe/fidelity.mjs``                     -> Error: --gateway <name> required
  - ``node probe/fidelity.mjs --gateway self-test`` -> 3/3, standalone, no keys
  - ``node probe/xformat.mjs --gateway self-test``  -> Error: --messages-url required
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Any published `node probe/<name>.mjs ...` invocation. Shell line-continuations are
#: folded first, so a flag on the next line still counts as part of the same command.
PROBE_CALL_RE = re.compile(r"node\s+probe/(fidelity|xformat)\.mjs([^\n`]*)")
CONTINUATION_RE = re.compile(r"\\\n\s*")

#: Flags each probe's main() refuses to start without.
REQUIRED_FLAGS = {
    # --gateway self-test short-circuits the URL requirement (it targets the mock itself).
    "fidelity": ("--gateway",),
    "xformat": ("--gateway", "--messages-url"),
}

SEARCH_GLOBS = ("*.md", "docs/*.md", "compare/*.md")


def published_calls() -> list[tuple[Path, str, str]]:
    """(file, probe_name, argument_text) for every probe invocation in the docs."""
    out: list[tuple[Path, str, str]] = []
    seen: set[Path] = set()
    for pattern in SEARCH_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            text = CONTINUATION_RE.sub(" ", path.read_text(encoding="utf-8"))
            for m in PROBE_CALL_RE.finditer(text):
                out.append((path, m.group(1), m.group(2)))
    return out


class PublishedProbeCommands(unittest.TestCase):
    def test_docs_still_publish_the_probe(self):
        self.assertTrue(
            published_calls(),
            "no probe invocation found in the docs — if the self-test was removed, "
            "delete this guard deliberately rather than letting it pass vacuously",
        )

    def test_every_published_invocation_carries_its_required_flags(self):
        for path, probe, argtext in published_calls():
            for flag in REQUIRED_FLAGS[probe]:
                if "--help" in argtext:
                    continue
                with self.subTest(file=path.name, probe=probe, flag=flag):
                    self.assertIn(
                        flag,
                        argtext,
                        f"{path.name} publishes `node probe/{probe}.mjs{argtext}` — it exits "
                        f"immediately without {flag}. A reader following this doc sees an error, "
                        f"not a measurement.",
                    )

    def test_the_standalone_example_uses_self_test(self):
        """At least one published fidelity call must be the no-setup one.

        `--gateway self-test` is the only invocation a reader can run straight after
        cloning; everything else needs their gateway wired to the mock upstream first.
        Losing it turns a 30-second check into a configuration exercise.
        """
        fidelity_args = [a for _, p, a in published_calls() if p == "fidelity"]
        self.assertTrue(
            any("self-test" in a for a in fidelity_args),
            "no `node probe/fidelity.mjs --gateway self-test` example is published; "
            "readers lose the one probe command that runs with nothing configured",
        )


if __name__ == "__main__":
    unittest.main()
