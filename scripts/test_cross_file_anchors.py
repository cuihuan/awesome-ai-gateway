"""Every relative link and #anchor in the docs must resolve.

awesome-lint validates the README's own table of contents, and the link
checker validates external URLs — neither follows a link from one file in
this repo to a heading in another. That gap let a link to
`BENCHMARKS.md#pricing-gotchas-a-gateway-buyer-must-know` pass every gate,
even though the target is bold text rather than a heading and the anchor
does not exist.

Anchors are resolved with GitHub's own slugging rules, including the
`<a name="...">` form the handbook chapters use for failure-mode targets.
"""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = sorted(
    [ROOT / n for n in ("README.md", "README.zh-CN.md", "BENCHMARKS.md",
                        "BENCHMARKS.zh-CN.md", "HANDBOOK.md", "CONTRIBUTING.md")]
    + list((ROOT / "docs").glob("*.md"))
    + list((ROOT / "compare").glob("*.md"))
)

_NODE = r"""
(async () => {
  const {execSync} = require('node:child_process');
  let hit = '';
  try {
    hit = execSync('ls -d "$HOME"/.npm/_npx/*/node_modules/github-slugger/index.js 2>/dev/null | head -1',
                   {encoding: 'utf8', shell: '/bin/bash'}).trim();
  } catch (e) {}
  if (!hit) { console.log('NO_SLUGGER'); return; }
  const S = (await import(hit)).default;
  const fs = require('fs'), path = require('path');
  const files = JSON.parse(process.argv[1]);
  const cache = {};
  const slugsOf = (f) => {
    if (cache[f]) return cache[f];
    const s = fs.readFileSync(f, 'utf8'), sl = new S(), out = new Set();
    for (const m of s.matchAll(/^#{1,6}\s+(.*)$/gm)) {
      const t = m[1].replace(/\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)/g, '')
                    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').trim();
      out.add(sl.slug(t.replaceAll('️', '')));
    }
    for (const m of s.matchAll(/<a name="([^"]+)"/g)) out.add(m[1]);
    cache[f] = out; return out;
  };
  const bad = [];
  for (const f of files) {
    const body = fs.readFileSync(f, 'utf8').replace(/```[\s\S]*?```/g, '').replace(/`[^`\n]*`/g, '');
    for (const m of body.matchAll(/\]\((?!https?:|mailto:)([^)\s]+)\)/g)) {
      const [fp, anchor] = m[1].split('#');
      const base = fp ? path.normalize(path.join(path.dirname(f), fp)) : f;
      if (fp && !fs.existsSync(base)) { bad.push(`${path.basename(f)} -> ${m[1]} (missing file)`); continue; }
      if (anchor && !slugsOf(base).has(anchor)) bad.push(`${path.basename(f)} -> ${m[1]} (no such anchor)`);
    }
  }
  console.log(JSON.stringify(bad));
})()
"""


class TestCrossFileAnchors(unittest.TestCase):
    def test_all_relative_links_and_anchors_resolve(self):
        result = subprocess.run(
            ["node", "-e", _NODE, "--", str([str(p) for p in FILES]).replace("'", '"')],
            capture_output=True, text=True, cwd=ROOT,
        )
        out = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        if out == "NO_SLUGGER":
            self.skipTest("github-slugger not available (run npx awesome-lint once to populate the cache)")
        self.assertTrue(out.startswith("["), f"anchor checker failed: {result.stderr[:400]}")
        import json
        broken = json.loads(out)
        self.assertEqual(broken, [], "\n".join(broken[:25]))


if __name__ == "__main__":
    unittest.main()
