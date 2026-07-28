#!/usr/bin/env node
// Regenerate the `## Contents` block as the strict mirror of the heading tree
// that awesome-lint's `awesome-toc` rule validates: one item per h2 after
// Contents (minus the rule's denylist), nested items for that section's h3s,
// link text exactly equal to the heading text, slugs produced by the very same
// github-slugger the rule uses (all headings slugged in document order, VS16
// stripped — matching the rule's buildHeadingLinks).
//
// Usage: node scripts/build_toc.mjs [--check] README.md

import {readFileSync, writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';

const require = createRequire(import.meta.url);
let GitHubSlugger;
try {
  GitHubSlugger = (await import('github-slugger')).default;
} catch {
  // Fall back to a copy inside the local npx cache (where awesome-lint ran from).
  const {execSync} = require('node:child_process');
  const hit = execSync(
    'ls -d "$HOME"/.npm/_npx/*/node_modules/github-slugger/index.js 2>/dev/null | head -1',
    {encoding: 'utf8', shell: '/bin/bash'}
  ).trim();
  if (!hit) {
    console.error('github-slugger not found; run: npm i --no-save github-slugger');
    process.exit(2);
  }
  GitHubSlugger = (await import(hit)).default;
}

const DENYLIST = new Set(['Contributing', 'Footnotes', 'Related Lists']);

const args = process.argv.slice(2);
const check = args.includes('--check');
const file = args.find(a => a !== '--check') ?? 'README.md';

const src = readFileSync(file, 'utf8');
const lines = src.split('\n');

// Collect headings (skip fenced code), slugging EVERY heading in order so the
// slugger's dedupe counters match the lint rule's pass over the full document.
const slugger = new GitHubSlugger();
const headings = [];
let inFence = false;
for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  if (/^\s*(```|~~~)/.test(line)) { inFence = !inFence; continue; }
  if (inFence) continue;
  const m = /^(#{1,6})\s+(.*)$/.exec(line);
  if (!m) continue;
  // Approximate mdast toString: drop badge images/links markup, keep text.
  let text = m[2].trim();
  text = text.replace(/\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)/g, '').trim(); // badge links
  text = text.replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').trim();           // plain links
  const slug = slugger.slug(text.replaceAll('️', ''));
  headings.push({depth: m[1].length, text, slug, lineIndex: i});
}

const contents = headings.find(h => h.depth === 2 && h.text === 'Contents');
if (!contents) {
  console.error('No `## Contents` heading found');
  process.exit(2);
}

const after = headings.filter(h => h.lineIndex > contents.lineIndex);
const toc = [];
for (let i = 0; i < after.length; i++) {
  const h = after[i];
  if (h.depth === 2) {
    if (DENYLIST.has(h.text)) continue;
    toc.push(`- [${h.text}](#${h.slug})`);
  } else if (h.depth === 3) {
    // Nested only if its parent h2 is in the ToC.
    const parent = [...after.slice(0, i)].reverse().find(x => x.depth === 2);
    if (parent && !DENYLIST.has(parent.text)) {
      toc.push(`  - [${h.text}](#${h.slug})`);
    }
  }
}

// Replace the block between `## Contents` and the next h2.
const start = contents.lineIndex;
let end = lines.length;
for (const h of after) {
  if (h.depth === 2) { end = h.lineIndex; break; }
}
const replacement = ['## Contents', '', ...toc, ''];
const out = [...lines.slice(0, start), ...replacement, ...lines.slice(end)].join('\n');

if (out !== src) {
  if (check) {
    console.error(`${file}: ToC out of date (run: node scripts/build_toc.mjs ${file})`);
    process.exit(1);
  }
  writeFileSync(file, out);
  console.log(`${file}: ToC regenerated (${toc.length} items)`);
} else {
  console.log(`${file}: ToC already current`);
}
