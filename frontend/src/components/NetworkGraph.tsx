import type { VersionMeta } from "../types";
import { branchName, ref } from "../lib/git";

const X0 = 60, XS = 104, LANE = 64, R = 7;

const short = (s: string) => (s.length > 16 ? s.slice(0, 15) + "…" : s);

/**
 * GitHub-style network: `main` runs left→right along the bottom; every tailored
 * branch sits on a single lane above it and arcs off its fork point.
 */
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

  const height = LANE + 96;
  const mainY = height - 48;
  const branchY = mainY - LANE; // one lane, same height for all branches
  const width = X0 + (asc.length - 1) * XS + 60;

  const xOf = (v: number) => X0 + (idx.get(v) ?? 0) * XS;
  const yOf = (v: VersionMeta) => (v.is_base ? mainY : branchY);

  const baseXs = asc.filter((v) => v.is_base).map((v) => xOf(v.version));
  const spineFrom = Math.min(...baseXs, X0);
  const spineTo = Math.max(...baseXs, X0);

  return (
    <div className="card" style={{ overflowX: "auto" }}>
      <p className="section-title">Network</p>
      <svg width={width} height={height} style={{ display: "block", minWidth: "100%" }}>
        <line x1={spineFrom} y1={mainY} x2={spineTo} y2={mainY} stroke="var(--commit)" strokeWidth={2.5} />
        {asc.filter((v) => !v.is_base && v.forked_from).map((v) => {
          const fx = xOf(v.forked_from!), nx = xOf(v.version);
          return (
            <path
              key={"e" + v.version}
              d={`M ${fx} ${mainY} C ${fx + XS * 0.45} ${mainY} ${nx - XS * 0.45} ${branchY} ${nx} ${branchY}`}
              fill="none" stroke="var(--branch)" strokeWidth={2}
            />
          );
        })}
        {asc.map((v) => {
          const x = xOf(v.version), y = yOf(v);
          const isHead = v.version === current;
          const isSel = v.version === selected;
          return (
            <g key={v.version} onClick={() => onSelect(v.version)} style={{ cursor: "pointer" }}>
              <title>{ref(v.version)} · {v.is_base ? "main" : branchName(v)}{v.label ? " · " + v.label : ""}</title>
              {isSel && <circle cx={x} cy={y} r={R + 5} fill="none" stroke="var(--accent)" strokeWidth={1.5} />}
              <circle
                cx={x} cy={y} r={isHead ? R + 1 : R}
                fill={isHead ? "var(--bg)" : v.is_base ? "var(--commit)" : "var(--branch)"}
                stroke={isHead ? "var(--commit)" : "none"} strokeWidth={3}
              />
              <text x={x} y={mainY + 22} textAnchor="middle" fontSize={11} fill="var(--muted)" fontFamily="var(--mono)">
                {ref(v.version)}
              </text>
              {!v.is_base && (
                <text x={x} y={branchY - 15} textAnchor="middle" fontSize={10} fill="var(--branch)" fontFamily="var(--mono)">
                  {short(branchName(v))}
                </text>
              )}
            </g>
          );
        })}
        <text x={spineFrom - 6} y={mainY + 4} textAnchor="end" fontSize={11} fill="var(--commit)" fontFamily="var(--mono)">main</text>
      </svg>
      <p className="muted" style={{ fontSize: 12 }}>Click a node to select it. Green = commits on main; purple = tailored branches; ringed = HEAD. Hover for details.</p>
    </div>
  );
}
