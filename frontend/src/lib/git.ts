import type { VersionMeta } from "../types";

/** Turn a friendly label into a git-style branch slug. */
export function slugify(label: string | null | undefined): string {
  const s = (label || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
  return s || "tailored";
}

/** Short commit ref like `v0006`. */
export function ref(version: number): string {
  return "v" + String(version).padStart(4, "0");
}

/** The branch a version lives on: `main` for base commits, else the slug. */
export function branchName(v: VersionMeta): string {
  return v.is_base ? "main" : slugify(v.label);
}

/** Human date, compact. */
export function shortDate(iso: string): string {
  return iso ? iso.replace("T", " ").slice(0, 16) : "";
}

// ── Per-row git-graph topology ──────────────────────────────────────────────
// Each commit becomes one row (newest first). For that row we compute which
// lanes carry a vertical line, where the node sits, and which branch lanes
// curve into main. Rendering row-by-row keeps the graph and labels aligned.
export interface GraphRow {
  meta: VersionMeta;
  nodeLane: number;
  through: number[];   // lanes drawn full-height
  downHalf: number[];  // lanes drawn from node center to bottom
  upHalf: number[];    // lanes drawn from top to node center
  curves: number[];    // branch lanes curving into lane 0 at this row (fork point)
  laneCount: number;
}

export function computeGraphRows(versions: VersionMeta[]): GraphRow[] {
  const rows = [...versions].sort((a, b) => b.version - a.version); // newest first
  const rowOf = new Map<number, number>();
  rows.forEach((v, i) => rowOf.set(v.version, i));

  const baseRows = rows.map((v, i) => (v.is_base ? i : -1)).filter((i) => i >= 0);
  const topMain = baseRows.length ? Math.min(...baseRows) : -1;
  const botMain = baseRows.length ? Math.max(...baseRows) : -1;

  // Assign each branch the lowest free lane over its [tip … fork] row span.
  const occupied: Array<Array<[number, number]>> = [];
  const laneOf = new Map<number, number>();
  const branches = rows
    .filter((v) => !v.is_base && v.forked_from != null && rowOf.has(v.forked_from))
    .sort((a, b) => rowOf.get(a.version)! - rowOf.get(b.version)!);
  for (const b of branches) {
    const tip = rowOf.get(b.version)!;
    const fork = rowOf.get(b.forked_from!)!;
    const [s, e] = [Math.min(tip, fork), Math.max(tip, fork)];
    let lane = 1;
    while ((occupied[lane] || []).some(([os, oe]) => !(e < os || s > oe))) lane++;
    (occupied[lane] || (occupied[lane] = [])).push([s, e]);
    laneOf.set(b.version, lane);
  }
  const laneCount = 1 + Math.max(0, ...[...laneOf.values()]);

  return rows.map((v, r) => {
    const through: number[] = [], downHalf: number[] = [], upHalf: number[] = [], curves: number[] = [];
    const nodeLane = v.is_base ? 0 : laneOf.get(v.version) ?? 1;

    if (topMain >= 0 && r >= topMain && r <= botMain) {
      if (r > topMain && r < botMain) through.push(0);
      else if (r === topMain && r !== botMain) downHalf.push(0);
      else if (r === botMain && r !== topMain) upHalf.push(0);
    }
    for (const b of branches) {
      const L = laneOf.get(b.version)!;
      const tip = rowOf.get(b.version)!;
      const fork = rowOf.get(b.forked_from!)!;
      if (r < Math.min(tip, fork) || r > Math.max(tip, fork)) continue;
      if (r === tip) downHalf.push(L);       // branch tip: line heads down to fork
      else if (r === fork) curves.push(L);    // fork commit: curve in from the branch lane
      else through.push(L);
    }
    return { meta: v, nodeLane, through, downHalf, upHalf, curves, laneCount };
  });
}
