import { useState } from "react";
import { api, ApiError } from "../api";
import type { Me, TailorPreview } from "../types";
import { DiffLines, Summary } from "./DiffView";

export function TailorPanel({ me, onSaved }: { me: Me; onSaved: (v: number) => void }) {
  const [jd, setJd] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [preview, setPreview] = useState<TailorPreview | null>(null);
  const [prompt, setPrompt] = useState("");
  const [pasted, setPasted] = useState("");

  async function aiTailor() {
    setErr("");
    setPreview(null);
    setBusy(true);
    try {
      setPreview(await api.tailorPreview(jd));
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(d?.error ? d.error + (d.raw ? "\n\n--- model output ---\n" + d.raw : "") : String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function saveAi() {
    if (!preview) return;
    setBusy(true);
    try {
      const res = await api.createTailor(preview.data, label || "Tailored", jd || null);
      onSaved(res.version);
    } finally {
      setBusy(false);
    }
  }

  async function showPrompt() {
    setErr("");
    try {
      setPrompt((await api.sessionPrompt()).prompt);
    } catch (e) {
      setErr(String((e as ApiError).message));
    }
  }

  async function savePasted() {
    setErr("");
    let data: unknown;
    try {
      data = JSON.parse(pasted);
    } catch (e) {
      setErr("Invalid JSON: " + (e as Error).message);
      return;
    }
    setBusy(true);
    try {
      const res = await api.createTailor(data, label || "Tailored", jd || null);
      onSaved(res.version);
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(d?.problems ? "Schema problems:\n- " + d.problems.join("\n- ") : String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="card">
        <p className="section-title">Tailor to a job description</p>
        <textarea
          rows={8}
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          placeholder="Paste the job description (company, role, requirements, nice-to-haves)…"
        />
        <div className="field" style={{ marginTop: 10 }}>
          <label>Label</label>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Jane Street SWE" />
        </div>

        {me.ai_enabled ? (
          <div className="row">
            <button className="primary" disabled={busy || !jd.trim()} onClick={aiTailor}>
              {busy ? "Tailoring…" : "Tailor with Claude"}
            </button>
            <span className="muted" style={{ fontSize: 12 }}>Model: {me.default_model}</span>
          </div>
        ) : (
          <div className="row">
            <button onClick={showPrompt}>Show session prompt (copy into Claude)</button>
            <span className="muted" style={{ fontSize: 12 }}>
              No API key set — using copy-paste flow. Add a key in Settings to tailor in-app.
            </span>
          </div>
        )}
        {err && <p className="err">{err}</p>}
      </div>

      {preview && (
        <div className="card">
          <p className="section-title">Preview (not saved yet)</p>
          <Summary items={preview.summary} />
          <details>
            <summary className="muted">Line-by-line diff</summary>
            <DiffLines lines={preview.diff} />
          </details>
          <div className="row" style={{ marginTop: 10 }}>
            <button className="primary" disabled={busy} onClick={saveAi}>Save tailored version</button>
            <button disabled={busy} onClick={() => setPreview(null)}>Discard</button>
          </div>
        </div>
      )}

      {prompt && (
        <div className="card">
          <p className="section-title">Session prompt</p>
          <button onClick={() => navigator.clipboard.writeText(prompt)}>Copy prompt</button>
          <textarea rows={8} readOnly value={prompt} style={{ marginTop: 8 }} />
          <p className="muted" style={{ fontSize: 12 }}>
            Paste into a new Claude chat, send a <code>[TAILOR]</code> turn with the JD, then paste the
            returned JSON below.
          </p>
          <textarea
            rows={8}
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            placeholder="Paste the tailored JSON from Claude here…"
          />
          <div className="row" style={{ marginTop: 8 }}>
            <button className="primary" disabled={busy || !pasted.trim()} onClick={savePasted}>
              Save tailored version
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
