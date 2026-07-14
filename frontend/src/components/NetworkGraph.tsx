import type { VersionMeta } from "../types";
import { branchName, computeGraphRows, ref } from "../lib/git";

const ROW_H = 40, LANE_W = 16, PAD = 14, DOT = 5.5;
const CY = ROW_H / 2;

/**
 * Live git-graph: one interactive row per commit (newest first). Each row draws
 * its own slice of the topology, so the graph and labels can never drift out of
 * alignment. Rows hover, select, and mark HEAD.
 */
export function NetworkGraph({
  versions, current, selected, onSelect,
}: {
  versions: VersionMeta[];
  current: number | null;
  selected: number | null;
  onSelect: (v: number) => void;
}) {
  const graphRows = computeGraphRows(versions);
  const laneCount = graphRows[0]?.laneCount ?? 1;
  const cellW = PAD + laneCount * LANE_W + 6;
  const xLane = (l: number) => PAD + l * LANE_W;
  const stroke = (l: number) => (l === 0 ? "var(--commit)" : "var(--branch)");

  return (
    <div className="git-graph-wrap">
      <div className="git-graph">
        {graphRows.map((gr) => {
          const v = gr.meta;
          const isHead = v.version === current;
          const isSel = v.version === selected;
          const nx = xLane(gr.nodeLane);
          return (
            <div
              key={v.version}
              className={"grow" + (isSel ? " sel" : "") + (isHead ? " head" : "")}
              onClick={() => onSelect(v.version)}
              title={`${ref(v.version)} · ${v.is_base ? "main" : branchName(v)}${v.label ? " · " + v.label : ""}`}
            >
              <svg className="gcell" width={cellW} height={ROW_H} aria-hidden="true">
                {gr.through.map((l) => <line key={"t" + l} x1={xLane(l)} y1={0} x2={xLane(l)} y2={ROW_H} stroke={stroke(l)} strokeWidth={2} />)}
                {gr.upHalf.map((l) => <line key={"u" + l} x1={xLane(l)} y1={0} x2={xLane(l)} y2={CY} stroke={stroke(l)} strokeWidth={2} />)}
                {gr.downHalf.map((l) => <line key={"d" + l} x1={xLane(l)} y1={CY} x2={xLane(l)} y2={ROW_H} stroke={stroke(l)} strokeWidth={2} />)}
                {gr.curves.map((l) => (
                  <path key={"c" + l} fill="none" stroke="var(--branch)" strokeWidth={2}
                    d={`M ${xLane(l)} 0 C ${xLane(l)} ${CY}, ${xLane(0)} ${CY - 8}, ${xLane(0)} ${CY}`} />
                ))}
                <circle
                  cx={nx} cy={CY} r={isHead ? DOT + 1 : DOT}
                  fill={isHead ? "var(--bg)" : gr.nodeLane === 0 ? "var(--commit)" : "var(--branch)"}
                  stroke={isHead ? "var(--commit)" : isSel ? "var(--accent)" : "none"}
                  strokeWidth={isHead ? 3 : 2}
                />
              </svg>
              <div className="glabel">
                <span className="gmsg">{v.label || "(no message)"}</span>
                <span className="gsub">
                  <span className="mono">{ref(v.version)}</span>{" · "}
                  {v.is_base ? <span className="on-main">main</span> : <span className="on-branch">{branchName(v)}</span>}
                  {v.forked_from ? <span className="mono" style={{ opacity: 0.7 }}>{"  ⑃ from " + ref(v.forked_from)}</span> : null}
                </span>
              </div>
              {isHead && <span className="badge head grow-head">HEAD</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
