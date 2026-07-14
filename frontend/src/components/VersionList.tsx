import type { VersionMeta } from "../types";

interface Props {
  versions: VersionMeta[];
  selected: number | null;
  current: number | null;
  onSelect: (v: number) => void;
}

const vlabel = (n: number) => "v" + String(n).padStart(4, "0");

export function VersionList({ versions, selected, current, onSelect }: Props) {
  return (
    <div>
      <p className="section-title">History</p>
      {versions.map((v) => (
        <button
          key={v.version}
          className={
            "vitem" +
            (v.version === selected ? " selected" : "") +
            (v.is_base ? "" : " fork")
          }
          onClick={() => onSelect(v.version)}
        >
          <div className="row1">
            <span className="ver">{vlabel(v.version)}</span>
            <span className={"badge " + (v.is_base ? "base" : "tailor")}>
              {v.is_base ? "base" : "tailor"}
            </span>
            {v.version === current && <span className="badge cur">current</span>}
          </div>
          <div className="label">{v.label || "—"}</div>
          <div className="date">
            {v.created_at.replace("T", " ").slice(0, 16)}
            {v.forked_from ? `  ·  forked from ${vlabel(v.forked_from)}` : ""}
          </div>
        </button>
      ))}
    </div>
  );
}
