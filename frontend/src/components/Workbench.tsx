import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import type { Resume, VersionDetail } from "../types";
import { branchName } from "../lib/git";
import { ResumeEditor } from "./editor/ResumeEditor";
import { LivePdfPreview } from "./LivePdfPreview";
import { CommitBar } from "./CommitBar";

/**
 * The build-first Workbench: continuous editor + live PDF preview + a
 * context-aware commit bar. Committing on a base commit writes a new base
 * (main); on a tailored branch it refines that branch.
 */
export function Workbench({ detail, onCommitted }: { detail: VersionDetail; onCommitted: (v: number) => void }) {
  const [working, setWorking] = useState<Resume>(detail.data as Resume);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    setWorking(detail.data as Resume);
    setLabel("");
    setErr("");
  }, [detail.version]);

  const onMain = detail.is_base;
  const dirty = useMemo(
    () => JSON.stringify(working) !== JSON.stringify(detail.data),
    [working, detail.data]
  );

  const commit = async () => {
    setBusy(true);
    setErr("");
    try {
      const res = onMain
        ? await api.createBase(working, label || "Update")
        : await api.createTailor(working, label || detail.label || "Tailored", detail.jd_text);
      onCommitted(res.version);
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(d?.problems ? "Schema problems:\n- " + d.problems.join("\n- ") : String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="wb-wrap">
      <div className="workbench">
        <div className="wb-editor">
          <ResumeEditor value={working} onChange={setWorking} />
          {err && <p className="err">{err}</p>}
        </div>
        <div className="wb-preview">
          <LivePdfPreview data={working} />
        </div>
      </div>
      <CommitBar
        dirty={dirty}
        onMain={onMain}
        branchName={branchName(detail)}
        label={label}
        onLabel={setLabel}
        onCommit={commit}
        onDiscard={() => setWorking(detail.data as Resume)}
        busy={busy}
      />
    </div>
  );
}
