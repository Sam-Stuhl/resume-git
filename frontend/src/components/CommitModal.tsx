import { useEffect, useState } from "react";
import { api } from "../api";
import type { DiffOut, VersionDetail, VersionMeta } from "../types";
import { branchName, ref, shortDate } from "../lib/git";
import { DiffLines, Summary } from "./DiffView";

/**
 * Commit detail: full message + the diff of this commit against its parent
 * (a base diffs vs the previous base; a branch vs the base it forked from),
 * plus the saved job description for tailored commits.
 */
export function CommitModal({
  versions, version, onClose,
}: {
  versions: VersionMeta[];
  version: number;
  onClose: () => void;
}) {
  const meta = versions.find((v) => v.version === version);
  const [detail, setDetail] = useState<VersionDetail | null>(null);
  const [diff, setDiff] = useState<DiffOut | null>(null);
  const [state, setState] = useState<"loading" | "noparent" | "ready">("loading");

  const parent = meta
    ? meta.is_base
      ? Math.max(0, ...versions.filter((v) => v.is_base && v.version < version).map((v) => v.version))
      : meta.forked_from ?? 0
    : 0;

  useEffect(() => {
    api.version(version).then(setDetail).catch(() => {});
    if (parent) {
      api.diff(parent, version).then((d) => { setDiff(d); setState("ready"); }).catch(() => setState("ready"));
    } else {
      setState("noparent");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  if (!meta) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div style={{ minWidth: 0 }}>
            <div className="modal-title">{meta.label || "(no message)"}</div>
            <div className="gsub" style={{ marginTop: 4 }}>
              <span className="mono">{ref(version)}</span>{" · "}
              {meta.is_base ? <span className="on-main">main</span> : <span className="on-branch">{branchName(meta)}</span>}
              {meta.forked_from ? <span className="mono">{"  ⑃ from " + ref(meta.forked_from)}</span> : null}
              {"  ·  " + shortDate(meta.created_at)}
            </div>
          </div>
          <button className="mini ghost" onClick={onClose} title="close (Esc)">✕</button>
        </div>

        {detail?.jd_text && (
          <details className="modal-jd">
            <summary className="muted" style={{ cursor: "pointer" }}>Job description</summary>
            <pre className="jd-text">{detail.jd_text}</pre>
          </details>
        )}

        <div className="modal-body">
          {state === "loading" && <p className="muted">Loading diff…</p>}
          {state === "noparent" && <p className="muted">Initial commit — no parent to diff against.</p>}
          {state === "ready" && diff && (
            <>
              <p className="section-title">
                Changes vs {meta.is_base ? `previous base ${ref(parent)}` : `fork point ${ref(parent)}`}
              </p>
              <Summary items={diff.summary} />
              <div style={{ marginTop: 12 }}>
                <DiffLines lines={diff.lines} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
