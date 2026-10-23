#!/usr/bin/env node
// One settle rule for every tracker value the gate reports.
//
// rule: the median of the nonzero block-end Hz values at t >= 1.0 s.
// Blocks that read exactly 0 are excluded, because a silent or
// unconfident block is not a pitch reading and would drag the median to
// 0. When a render has no nonzero block at or after 1.0 s, the value is
// reported as null, never as 0.
//
// usage: node tools/pitch-gate/settle.mjs <trace.txt> [<trace.txt> ...]
import fs from "node:fs";
import path from "node:path";

const SETTLE_S = 1.0;

function median(values) {
  if (values.length === 0) return null;
  const v = values.slice().sort((a, b) => a - b);
  return v[v.length >> 1];
}

function settle(file) {
  const rows = [];
  for (const line of fs.readFileSync(file, "utf8").split("\n")) {
    const p = line.trim().split(/\s+/);
    if (p.length !== 2) continue;
    const t = Number(p[0]);
    const hz = Number(p[1]);
    if (!Number.isFinite(t) || !Number.isFinite(hz)) continue;
    rows.push([t, hz]);
  }
  if (rows.length === 0) throw new Error(`empty trace ${file}`);
  const settled = rows.filter(([t]) => t >= SETTLE_S - 1e-9).map(([, hz]) => hz);
  const nonzero = settled.filter((hz) => hz > 0);
  return {
    file: path.basename(file),
    blocks: rows.length,
    settled_blocks: settled.length,
    nonzero_blocks: nonzero.length,
    settle_hz: median(nonzero),
  };
}

const files = process.argv.slice(2);
if (files.length === 0) {
  console.error("usage: node tools/pitch-gate/settle.mjs <trace.txt> [<trace.txt> ...]");
  process.exit(2);
}
const cols = ["file", "blocks", "settled_blocks", "nonzero_blocks", "settle_hz"];
console.log(cols.join("\t"));
for (const f of files) {
  const r = settle(f);
  console.log(cols.map((c) => (r[c] === null ? "null" : r[c])).join("\t"));
}
