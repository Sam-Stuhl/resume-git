import { useState } from "react";
import { api, ApiError } from "../api";
import type { Me, TailorPreview } from "../types";
import { slugify } from "../lib/git";
import { DiffLines, Summary } from "./DiffView";

/**
 * Tailor = branch off `main` for a specific job. Name the branch, paste the JD,
 * let Claude tailor (or copy-paste), review the diff, then create the branch.
 */
export function TailorFlow({ me, onCreated }: { me: Me; onCreated: (v: number) => void }) {
  const [name, setName] = useState("");
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [preview, setPreview] = useState<TailorPreview | null>(null);
  const [prompt, setPrompt] = useState("");
  const [pasted, setPasted] = useState("");

  const slug = slugify(name);

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

  async function createBranch(data: unknown) {
    setBusy(true);
    setErr("");
    try {
      const res = await api.createTailor(data, name || "Tailored", jd || null);
      onCreated(res.version);
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(d?.problems ? "Schema problems:\n- " + d.problems.join("\n- ") : String((e as Error).message));
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

  function commitPasted() {
    let data: unknown;
    try {
      data = JSON.parse(pasted);
    } catch (e) {
      setErr("Invalid JSON: " + (e as Error).message);
      return;
    }
    createBranch(data);
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <div className="card">
        <p className="section-title">⑃ New branch — tailor for a job</p>
        <p className="muted" style={{ fontSize: 12, marginTop: -4, marginBottom: 12 }}>
          Branches off <code>main</code>; your baseline stays untouched.
        </p>
        <div className="field">
          <label>Branch name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Jane Street SWE" />
          <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>branch <code>{slug}</code></div>
        </div>
        <div className="field">
          <label>Job description</label>
          <textarea rows={8} value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the JD (company, role, requirements, nice-to-haves)…" />
        </div>
        {me.ai_enabled ? (
          <div className="row">
            <button className="accent" disabled={busy || !jd.trim()} onClick={aiTailor}>
              {busy ? "Tailoring…" : "⑃ Tailor with Claude"}
            </button>
            <span className="muted" style={{ fontSize: 12 }}>Model: {me.default_model}</span>
          </div>
        ) : (
          <div className="row">
            <button onClick={showPrompt}>Get session prompt (copy into Claude)</button>
            <span className="muted" style={{ fontSize: 12 }}>No API key — copy-paste mode. Add a key in Settings to tailor in-app.</span>
          </div>
        )}
        {err && <p className="err">{err}</p>}
      </div>

      {preview && (
        <div className="card">
          <p className="section-title">Preview vs main (not committed)</p>
          <Summary items={preview.summary} />
          <details>
            <summary className="muted" style={{ cursor: "pointer" }}>Line-by-line diff</summary>
            <DiffLines lines={preview.diff} />
          </details>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="green" disabled={busy} onClick={() => createBranch(preview.data)}>
              ⑃ Create branch {slug}
            </button>
            <button disabled={busy} onClick={() => setPreview(null)}>Discard</button>
          </div>
        </div>
      )}

      {prompt && (
        <div className="card">
          <p className="section-title">Session prompt</p>
          <button onClick={() => navigator.clipboard.writeText(prompt)}>Copy prompt</button>
          <textarea rows={7} readOnly value={prompt} style={{ marginTop: 8 }} />
          <p className="muted" style={{ fontSize: 12 }}>
            Paste into a new Claude chat, send a <code>[TAILOR]</code> turn with the JD, then paste the returned JSON below.
          </p>
          <textarea rows={7} value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="Paste the tailored JSON from Claude…" />
          <div className="row" style={{ marginTop: 8 }}>
            <button className="green" disabled={busy || !pasted.trim()} onClick={commitPasted}>⑃ Create branch {slug}</button>
          </div>
        </div>
      )}
    </div>
  );
}
