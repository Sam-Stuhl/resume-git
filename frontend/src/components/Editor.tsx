import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { VersionDetail } from "../types";

export function Editor({
  detail,
  onSaved,
}: {
  detail: VersionDetail;
  onSaved: (v: number) => void;
}) {
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setText(JSON.stringify(detail.data, null, 2));
    setErr("");
    setLabel("");
  }, [detail.version]);

  function parsed(): unknown | null {
    try {
      return JSON.parse(text);
    } catch (e) {
      setErr("Invalid JSON: " + (e as Error).message);
      return null;
    }
  }

  async function save(kind: "base" | "tailor") {
    setErr("");
    const data = parsed();
    if (data === null) return;
    setBusy(true);
    try {
      const res =
        kind === "base"
          ? await api.createBase(data, label || "Manual edit")
          : await api.createTailor(data, label || "Manual edit", null);
      onSaved(res.version);
    } catch (e) {
      const ae = e as ApiError;
      const d: any = ae.detail;
      setErr(d?.problems ? "Schema problems:\n- " + d.problems.join("\n- ") : String(ae.message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="card">
        <p className="section-title">
          Editing v{String(detail.version).padStart(4, "0")} — {detail.is_base ? "base" : "tailored"}
        </p>
        <textarea rows={22} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} />
        {err && <p className="err">{err}</p>}
        <div className="field" style={{ marginTop: 10 }}>
          <label>Label for the new version</label>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Added new role" />
        </div>
        <div className="row">
          <button className="primary" disabled={busy} onClick={() => save("base")}>
            Save as new base
          </button>
          <button disabled={busy} onClick={() => save("tailor")}>
            Save as tailored fork
          </button>
        </div>
        <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>
          Saving creates a new version — the original is never overwritten.
        </p>
      </div>
    </div>
  );
}
