import { useEffect, useState } from "react";
import { api } from "../api";
import type { DiffOut, VersionMeta } from "../types";
import { branchName, ref } from "../lib/git";
import { DiffLines, Summary } from "./DiffView";

/** GitHub-style compare: base … compare, with a change summary + unified diff. */
export function Compare({ versions, selected }: { versions: VersionMeta[]; selected: number }) {
  const sorted = [...versions].sort((a, b) => a.version - b.version);
  const latestBase = [...versions].filter((v) => v.is_base).sort((a, b) => b.version - a.version)[0]?.version;
  const [base, setBase] = useState<number>(latestBase ?? sorted[0].version);
  const [compare, setCompare] = useState<number>(selected);
  const [diff, setDiff] = useState<DiffOut | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (base === compare) {
      setDiff(null);
      setErr("Pick two different commits to compare.");
      return;
    }
    setErr("");
    api.diff(base, compare).then(setDiff).catch((e) => setErr(String(e.message)));
  }, [base, compare]);

  const options = sorted.map((v) => (
    <option key={v.version} value={v.version}>
      {ref(v.version)} · {v.is_base ? "main" : branchName(v)}{v.label ? " · " + v.label : ""}
    </option>
  ));

  return (
    <div>
      <div className="card">
        <div className="compare-bar">
          <span className="muted">base</span>
          <select value={base} onChange={(e) => setBase(Number(e.target.value))}>{options}</select>
          <span className="compare-arrow">…</span>
          <span className="muted">compare</span>
          <select value={compare} onChange={(e) => setCompare(Number(e.target.value))}>{options}</select>
        </div>
      </div>
      {err && <p className="err">{err}</p>}
      {diff && (
        <>
          <div className="card">
            <p className="section-title">Changes · {ref(base)} … {ref(compare)}</p>
            <Summary items={diff.summary} />
          </div>
          <div className="card">
            <DiffLines lines={diff.lines} />
          </div>
        </>
      )}
    </div>
  );
}
