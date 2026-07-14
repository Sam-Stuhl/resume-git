import type { VersionMeta } from "../types";
import { branchName, ref } from "../lib/git";

const X0 = 60, XS = 100, LANE = 60, R = 7;

/** GitHub-style network: `main` runs left→right; tailored branches arc off. */
export function NetworkGraph({
  versions, current, selected, onSelect,
}: {
  versions: VersionMeta[];
  current: number | null;
  selected: number | null;
  onSelect: (v: number) => void;
}) {
  const asc = [...versions].sort((a, b) => a.version - b.version);
  const idx = new Map<number, number>();
  asc.forEach((v, i) => idx.set(v.version, i));

  // Assign tailored branches to staggered lanes above main.
  let t = 0;
  const laneOf = new Map<number, number>();
  for (const v of asc) if (!v.is_base) laneOf.set(v.version, 1 + (t++ % 2));

  const maxLane = Math.max(1, ...[...laneOf.values()]);
  const height = maxLane * LANE + 90;
  const mainY = height - 46;
  const width = X0 + (asc.length - 1) * XS + 60;

  const xOf = (v: number) => X0 + (idx.get(v) ?? 0) * XS;
  const yOf = (v: VersionMeta) => (v.is_base ? mainY : mainY - (laneOf.get(v.version) ?? 1) * LANE);

  const baseXs = asc.filter((v) => v.is_base).map((v) => xOf(v.version));
  const spineFrom = Math.min(...baseXs, X0);
  const spineTo = Math.max(...baseXs, X0);

  return (
    <div className="card" style={{ overflowX: "auto" }}>
      <p className="section-title">Network</p>
      <svg width={width} height={height} style={{ display: "block", minWidth: "100%" }}>
        {/* main spine */}
        <line x1={spineFrom} y1={mainY} x2={spineTo} y2={mainY} stroke="var(--commit)" strokeWidth={2.5} />
        {/* branch arcs */}
        {asc.filter((v) => !v.is_base && v.forked_from).map((v) => {
          const fx = xOf(v.forked_from!), nx = xOf(v.version), ny = yOf(v);
          return (
            <path
              key={"e" + v.version}
              d={`M ${fx} ${mainY} C ${fx + XS * 0.4} ${mainY} ${nx - XS * 0.4} ${ny} ${nx} ${ny}`}
              fill="none" stroke="var(--branch)" strokeWidth={2}
            />
          );
        })}
        {/* nodes */}
        {asc.map((v) => {
          const x = xOf(v.version), y = yOf(v);
          const isHead = v.version === current;
          const isSel = v.version === selected;
          return (
            <g key={v.version} className="gnode" onClick={() => onSelect(v.version)} style={{ cursor: "pointer" }}>
              {isSel && <circle cx={x} cy={y} r={R + 5} fill="none" stroke="var(--accent)" strokeWidth={1.5} />}
              <circle
                cx={x} cy={y} r={isHead ? R + 1 : R}
                fill={isHead ? "var(--bg)" : v.is_base ? "var(--commit)" : "var(--branch)"}
                stroke={isHead ? "var(--commit)" : "none"} strokeWidth={3}
              />
              <text x={x} y={v.is_base ? y + 22 : y - 14} textAnchor="middle" fontSize={11} fill="var(--muted)" fontFamily="var(--mono)">
                {ref(v.version)}
              </text>
              {!v.is_base && (
                <text x={x} y={y - 26} textAnchor="middle" fontSize={10} fill="var(--branch)" fontFamily="var(--mono)">
                  {branchName(v)}
                </text>
              )}
            </g>
          );
        })}
        <text x={spineFrom - 4} y={mainY + 4} textAnchor="end" fontSize={11} fill="var(--commit)" fontFamily="var(--mono)">main</text>
      </svg>
      <p className="muted" style={{ fontSize: 12 }}>Click a node to select it. Green = commits on main; purple = tailored branches. Ringed = HEAD.</p>
    </div>
  );
}
