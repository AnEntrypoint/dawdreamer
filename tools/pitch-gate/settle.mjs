#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const SETTLE_START_S = 1.0;
const WINDOW_TOLERANCE_S = 1e-9;
const USAGE = "usage: node tools/pitch-gate/settle.mjs <trace.txt> [<trace.txt> ...]";
const OUTPUT_COLUMNS = ["file", "blocks", "settled_blocks", "nonzero_blocks", "settle_hz"];

function median(values) {
  if (values.length === 0) return null;
  const v = values.slice().sort((a, b) => a - b);
  return v[v.length >> 1];
}

function isPitchReading(hz) {
  return hz > 0;
}

function settleTrackerTrace(file) {
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
  const settledWindowHz = rows
    .filter(([t]) => t >= SETTLE_START_S - WINDOW_TOLERANCE_S)
    .map(([, hz]) => hz);
  const pitchReadings = settledWindowHz.filter(isPitchReading);
  return {
    file: path.basename(file),
    blocks: rows.length,
    settled_blocks: settledWindowHz.length,
    nonzero_blocks: pitchReadings.length,
    settle_hz: median(pitchReadings),
  };
}

const files = process.argv.slice(2);
if (files.length === 0) {
  console.error(USAGE);
  process.exit(2);
}
console.log(OUTPUT_COLUMNS.join("\t"));
for (const f of files) {
  const r = settleTrackerTrace(f);
  console.log(OUTPUT_COLUMNS.map((c) => (r[c] === null ? "null" : r[c])).join("\t"));
}
