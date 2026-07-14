import { useState } from "react";
import { api, ApiError } from "../api";

interface Bundle {
  schema?: string;
  current_version?: number | null;
  versions: { version: number; label: string | null; is_base: boolean }[];
}

export function ImportPanel({ onImported }: { onImported: () => void }) {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [needsReplace, setNeedsReplace] = useState<number | null>(null);
  const [done, setDone] = useState("");

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    setErr("");
    setDone("");
    setNeedsReplace(null);
    setBundle(null);
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result));
        if (!Array.isArray(parsed.versions)) throw new Error("not a resume export bundle");
        setBundle(parsed);
      } catch (ex) {
        setErr("Could not read bundle: " + (ex as Error).message);
      }
    };
    reader.readAsText(file);
  }

  async function doImport(replace: boolean) {
    if (!bundle) return;
    setBusy(true);
    setErr("");
    try {
      const res = await api.importBundle(bundle, replace);
      setDone(`Imported ${res.imported} version(s).`);
      setBundle(null);
      setNeedsReplace(null);
      onImported();
    } catch (e) {
      const ae = e as ApiError;
      const d: any = ae.detail;
      if (ae.status === 409 && d?.error === "account_not_empty") {
        setNeedsReplace(d.count);
      } else if (d?.problems) {
        setErr("Bundle failed validation:\n- " + d.problems.join("\n- "));
      } else {
        setErr(String(ae.message));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <p className="section-title">Import from CLI</p>
      <p className="muted" style={{ fontSize: 12, marginTop: 0 }}>
        Run <code>python export_cli.py</code> against your local resume_data, then
        upload the resulting <code>resume_export.json</code> here.
      </p>
      <input type="file" accept="application/json,.json" onChange={onFile} />

      {bundle && (
        <div style={{ marginTop: 12 }}>
          <p>
            Found <strong>{bundle.versions.length}</strong> version(s)
            {bundle.current_version ? `, current v${String(bundle.current_version).padStart(4, "0")}` : ""}.
          </p>
          {needsReplace == null ? (
            <button className="primary" disabled={busy} onClick={() => doImport(false)}>
              {busy ? "Importing…" : "Import"}
            </button>
          ) : (
            <div>
              <p className="err">
                This account already has {needsReplace} version(s). Replace them with the import?
                This deletes the existing ones.
              </p>
              <div className="row">
                <button disabled={busy} onClick={() => doImport(true)}>Replace all</button>
                <button disabled={busy} onClick={() => setNeedsReplace(null)}>Cancel</button>
              </div>
            </div>
          )}
        </div>
      )}

      {err && <p className="err">{err}</p>}
      {done && <p className="muted" style={{ marginTop: 8 }}>{done}</p>}
    </div>
  );
}
