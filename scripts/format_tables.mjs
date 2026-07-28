#!/usr/bin/env node
// Align GFM table pipes the way remark-lint-table-pipe-alignment@4 measures them:
// in UTF-16 code units (the rule pads by source offsets, NOT visual width — so
// emoji/CJK cells are fine as-is). Produces the "padded" cell style, satisfying
// remark-lint-table-cell-padding ['error','consistent'] at the same time.
//
// Usage: node scripts/format_tables.mjs [--check] <file...>
//   --check: exit 1 if any file would change (CI mode), without writing.

import {readFileSync, writeFileSync} from 'node:fs';

const args = process.argv.slice(2);
const check = args.includes('--check');
const files = args.filter(a => a !== '--check');
if (files.length === 0) {
  console.error('usage: node scripts/format_tables.mjs [--check] <file...>');
  process.exit(2);
}

const DELIM_RE = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;

function splitCells(line) {
  // Split a table row on unescaped pipes; strip the outer empties from the
  // leading/trailing pipe. Returns trimmed cell contents.
  const parts = [];
  let cur = '';
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '\\' && line[i + 1] === '|') {
      cur += '\\|';
      i++;
    } else if (ch === '|') {
      parts.push(cur);
      cur = '';
    } else {
      cur += ch;
    }
  }
  parts.push(cur);
  if (parts.length && parts[0].trim() === '') parts.shift();
  if (parts.length && parts[parts.length - 1].trim() === '') parts.pop();
  return parts.map(c => c.trim());
}

function alignOf(cell) {
  const c = cell.trim();
  const left = c.startsWith(':');
  const right = c.endsWith(':');
  if (left && right) return 'center';
  if (right) return 'right';
  if (left) return 'left';
  return 'none';
}

function delimCell(align, width) {
  // width = content width; the cell is emitted padded (' ' + marks + ' ') so the
  // table-cell-padding 'consistent' style stays uniformly padded, delimiter row
  // included (the rule counts alignment-row cells too).
  let marks;
  if (align === 'center') marks = ':' + '-'.repeat(Math.max(1, width - 2)) + ':';
  else if (align === 'right') marks = '-'.repeat(Math.max(1, width - 1)) + ':';
  else if (align === 'left') marks = ':' + '-'.repeat(Math.max(1, width - 1));
  else marks = '-'.repeat(width);
  return ' ' + marks + ' ';
}

function formatTable(lines) {
  const rows = lines.map(splitCells);
  const aligns = rows[1].map(alignOf);
  const nCols = Math.max(...rows.map(r => r.length));
  const widths = [];
  for (let c = 0; c < nCols; c++) {
    let w = 3; // delimiter minimum
    rows.forEach((r, i) => {
      if (i === 1) return; // delimiter row doesn't set content width
      const len = (r[c] ?? '').length;
      if (len > w) w = len;
    });
    widths[c] = w;
  }
  return rows.map((r, i) => {
    const cells = [];
    for (let c = 0; c < nCols; c++) {
      if (i === 1) {
        cells.push(delimCell(aligns[c] ?? 'none', widths[c]));
      } else {
        const content = r[c] ?? '';
        cells.push(' ' + content + ' '.repeat(widths[c] - content.length + 1));
      }
    }
    return '|' + cells.join('|') + '|';
  });
}

let dirty = false;
for (const file of files) {
  const src = readFileSync(file, 'utf8');
  const lines = src.split('\n');
  const out = [];
  let inFence = false;
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*(```|~~~)/.test(line)) inFence = !inFence;
    const isRow = !inFence && /^\s*\|/.test(line);
    if (isRow && i + 1 < lines.length && DELIM_RE.test(lines[i + 1]) && lines[i + 1].includes('|')) {
      const block = [line];
      let j = i + 1;
      while (j < lines.length && /^\s*\|/.test(lines[j])) {
        block.push(lines[j]);
        j++;
      }
      out.push(...formatTable(block));
      i = j;
    } else {
      out.push(line);
      i++;
    }
  }
  const result = out.join('\n');
  if (result !== src) {
    dirty = true;
    if (check) {
      console.error(`${file}: tables not aligned (run: node scripts/format_tables.mjs ${file})`);
    } else {
      writeFileSync(file, result);
      console.log(`${file}: tables aligned`);
    }
  }
}
process.exit(check && dirty ? 1 : 0);
