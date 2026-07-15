import { useState } from "react";
import { api, ApiError } from "../api";
import type { Me, TailorPreview } from "../types";
import { slugify } from "../lib/git";
import { GitBranchIcon } from "./icons";
import { DiffLines, Summary } from "./DiffView";

/**
 * Create a branch: fork off `main` for a specific job. Name the branch, paste
 * the JD, let Claude draft it (or copy-paste), review the diff, then commit.
 */
export function BranchFlow({ me, onCreated }: { me: Me; onCreated: (v: number) => void }) {
  const [name, setName] = useState("");
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [preview, setPreview] = useState<TailorPreview | null>(null);
  const [prompt, setPrompt] = useState("");
  const [pasted, setPasted] = useState("");

  const slug = slugify(name);

  async function draft() {
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
      const res = await api.createTailor(data, name || "Branch", jd || null);
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
      // Full tailor prompt with the JD injected — one copy, no manual re-assembly.
      setPrompt((await api.copyPrompt({ intent: "tailor", jd_text: jd })).prompt);
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(typeof d === "string" ? d : (d?.message || String((e as Error).message)));
    }
  }

  async function reviewPasted() {
    setErr("");
    setBusy(true);
    try {
      // Fence-strip + validate + diff before committing (no more blind commits).
      setPreview(await api.pastePreview(pasted, "tailor"));
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(
        d?.problems ? "That JSON isn't a valid résumé:\n- " + d.problems.join("\n- ")
        : "Couldn't read JSON from that paste. Copy Claude's reply again."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <div className="card">
        <p className="section-title" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <GitBranchIcon size={14} /> New branch for a job
        </p>
        <p className="muted" style={{ fontSize: 12, marginTop: -4, marginBottom: 12 }}>
          Forks off <code>main</code> and adapts it to the role; your baseline stays untouched.
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
            <button className="accent" disabled={busy || !jd.trim()} onClick={draft}>
              {busy ? "Drafting…" : "Draft with Claude"}
            </button>
            <span className="muted" style={{ fontSize: 12 }}>Model: {me.default_model}</span>
          </div>
        ) : (
          <div className="row">
            <button disabled={!jd.trim()} onClick={showPrompt}>Get the prompt (copy into Claude)</button>
            <span className="muted" style={{ fontSize: 12 }}>No Claude key connected — copy-paste mode. Connect one in Settings to draft in-app.</span>
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
              <GitBranchIcon size={13} /> Create branch {slug}
            </button>
            <button disabled={busy} onClick={() => setPreview(null)}>Discard</button>
          </div>
        </div>
      )}

      {prompt && (
        <div className="card">
          <p className="section-title">Session prompt</p>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <button onClick={() => navigator.clipboard.writeText(prompt)}>Copy prompt</button>
            <a className="cp-link" href="https://claude.ai/new" target="_blank" rel="noopener noreferrer">Open Claude.ai ↗</a>
          </div>
          <textarea rows={7} readOnly value={prompt} style={{ marginTop: 8 }} />
          <p className="muted" style={{ fontSize: 12 }}>
            Paste it into a new Claude chat — the JD is already included. Then paste Claude's reply below
            (code fences and surrounding prose are fine).
          </p>
          <textarea rows={7} value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="Paste Claude's reply here…" />
          <div className="row" style={{ marginTop: 8 }}>
            <button className="accent" disabled={busy || !pasted.trim()} onClick={reviewPasted}>
              {busy ? "Reading…" : "Review changes"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
