import type { VersionMeta } from "../types";
import { branchName, ref } from "../lib/git";
import { ChevronIcon } from "./icons";

interface Props {
  versions: VersionMeta[];
  selected: number | null;
  current: number | null;
  onSelect: (v: number) => void;
  onOpen?: (v: number) => void;
  onCollapse: () => void;
}

/** Clean, collapsible commit history. Double-click a row for the detail modal. */
export function BranchRail({ versions, selected, current, onSelect, onOpen, onCollapse }: Props) {
  return (
    <div className="rail">
      <div className="rail-header">
        <span className="rail-title">History</span>
        <button className="icon-btn ghost" onClick={onCollapse} title="Collapse history">
          <ChevronIcon size={14} className="chev-left" />
        </button>
      </div>
      <div className="rail-list">
        {versions.map((v, i) => {
          const isHead = v.version === current;
          const last = i === versions.length - 1;
          return (
            <button
              key={v.version}
              className={"rnode" + (v.version === selected ? " sel" : "") + (v.is_base ? "" : " branch")}
              onClick={() => onSelect(v.version)}
              onDoubleClick={() => onOpen?.(v.version)}
              title={(v.is_base ? "commit on main" : `branch · ${branchName(v)}`) + " — double-click for details"}
            >
              <span className="rgraph">
                <span className={"rdot " + (isHead ? "head" : v.is_base ? "commit" : "branch")} />
                {!last && <span className="rline" />}
              </span>
              <span className="rbody">
                <span className="rmsg">
                  <span className="rmsg-text">{v.label || "(no message)"}</span>
                  {isHead && <span className="badge head">HEAD</span>}
                </span>
                <span className="rmeta">
                  <span className="mono">{ref(v.version)}</span>{" · "}
                  {v.is_base ? <span className="on-main">main</span> : <span className="on-branch">{branchName(v)}</span>}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
