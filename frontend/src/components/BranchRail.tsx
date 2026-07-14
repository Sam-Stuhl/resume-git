import type { VersionMeta } from "../types";
import { branchName, ref, shortDate } from "../lib/git";

interface Props {
  versions: VersionMeta[];
  selected: number | null;
  current: number | null;
  onSelect: (v: number) => void;
  onOpen?: (v: number) => void;
}

/**
 * Git-styled history: the `main` spine (base commits) with tailored branches
 * indented under the commit they forked from. HEAD marks the checked-out
 * version. Clicking a node views it; checkout happens elsewhere.
 */
export function BranchRail({ versions, selected, current, onSelect, onOpen }: Props) {
  // Newest first, same as the API returns.
  return (
    <div>
      <p className="rail-title">Branches &amp; commits</p>
      {versions.map((v, i) => {
        const isHead = v.version === current;
        const last = i === versions.length - 1;
        return (
          <button
            key={v.version}
            className={
              "rail-node" +
              (v.version === selected ? " selected" : "") +
              (v.is_base ? "" : " branch")
            }
            onClick={() => onSelect(v.version)}
            onDoubleClick={() => onOpen?.(v.version)}
            title={(v.is_base ? "commit on main" : `branch · ${branchName(v)}`) + " — double-click for details"}
          >
            <span className="rail-graph">
              <span
                className={
                  "node-dot " + (isHead ? "head" : v.is_base ? "commit" : "branch")
                }
              />
              {!last && <span className="rail-line" />}
            </span>
            <span className="rail-body">
              <span className="rail-msg">{v.label || "(no message)"}</span>
              <span className="rail-meta">
                {v.is_base ? "main" : branchName(v)} · {ref(v.version)}
                {v.forked_from ? ` · from ${ref(v.forked_from)}` : ""} · {shortDate(v.created_at)}
              </span>
            </span>
            {isHead && (
              <span className="rail-head">
                <span className="badge head">HEAD</span>
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
