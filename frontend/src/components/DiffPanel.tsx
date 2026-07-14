import { useEffect, useState } from "react";
import { api } from "../api";
import type { DiffOut, VersionMeta } from "../types";
import { DiffLines, Summary } from "./DiffView";

export function DiffPanel({ versions, selected }: { versions: VersionMeta[]; selected: number }) {
  const sorted = [...versions].sort((a, b) => a.version - b.version);
  const [a, setA] = useState(() => (versions.length > 1 ? sorted[sorted.length - 2].version : selected));
  const [b, setB] = useState(selected);
  const [diff, setDiff] = useState<DiffOut | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (a === b) {
      setDiff(null);
      setErr("Pick two different versions.");
      return;
    }
    setErr("");
    api.diff(a, b).then(setDiff).catch((e) => setErr(String(e.message)));
  }, [a, b]);

  const opts = sorted.map((v) => (
    <option key={v.version} value={v.version}>
      v{String(v.version).padStart(4, "0")} — {v.is_base ? "base" : "tailor"} {v.label ? "· " + v.label : ""}
    </option>
  ));

  return (
    <div>
      <div className="card">
        <div className="row">
          <span className="muted">Compare</span>
          <select value={a} onChange={(e) => setA(Number(e.target.value))}>{opts}</select>
          <span className="muted">→</span>
          <select value={b} onChange={(e) => setB(Number(e.target.value))}>{opts}</select>
        </div>
      </div>
      {err && <p className="err">{err}</p>}
      {diff && (
        <div className="card">
          <p className="section-title">Summary</p>
          <Summary items={diff.summary} />
          <p className="section-title" style={{ marginTop: 12 }}>Line-by-line</p>
          <DiffLines lines={diff.lines} />
        </div>
      )}
    </div>
  );
}
