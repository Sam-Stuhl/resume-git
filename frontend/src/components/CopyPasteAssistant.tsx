import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Resume, TailorPreview } from "../types";
import { slugify } from "../lib/git";
import { prefs } from "../lib/prefs";
import { ChevronIcon, GitBranchIcon } from "./icons";
import { DiffLines, Summary } from "./DiffView";

/** The keyless assistant: same four skills as the in-app agent, run through a
 * copy-to-an-AI-chat and paste-back round-trip. Advice intents (ask/ats) end at
 * the copied prompt; content intents (tailor/base-update) bring the JSON back
 * through a validated diff before anything is committed. */
type Intent = "ask" | "ats" | "tailor" | "base-update";

const INTENTS: { id: Intent; label: string; blurb: string; returnsJson: boolean }[] = [
  { id: "ask", label: "Ask", blurb: "Honest advice on your résumé. The AI replies in prose; nothing to paste back.", returnsJson: false },
  { id: "ats", label: "ATS audit", blurb: "Audit a version against a job description. The AI replies in prose; nothing to paste back.", returnsJson: false },
  { id: "tailor", label: "Tailor", blurb: "Adapt your résumé to a job. Paste the result back to review a diff and open a branch.", returnsJson: true },
  { id: "base-update", label: "Base update", blurb: "Fold a real life change into your baseline. Paste the result back to review and apply it.", returnsJson: true },
];

const NEEDS_JD: Intent[] = ["tailor", "ats"];

export function CopyPasteAssistant({
  onApply, onCreateBranch,
}: {
  onApply: (resume: Resume) => void;
  onCreateBranch: (data: Resume, label: string, jd: string | null) => Promise<void>;
}) {
  const [intent, setIntent] = useState<Intent>("tailor");
  const [text, setText] = useState("");        // the JD (tailor/ats) or note (ask/base-update)
  const [branch, setBranch] = useState("");
  const [prompt, setPrompt] = useState("");
  const [pasted, setPasted] = useState("");
  const [preview, setPreview] = useState<TailorPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState("");

  // The "set up a chat" session prompt: résumé + commands, pasted once to start a
  // conversation that already has your résumé as context.
  const [session, setSession] = useState("");
  const [sessionCopied, setSessionCopied] = useState(false);
  const [sessionHidden, setSessionHidden] = useState(() => prefs.cpSessionHidden());
  const toggleSession = () => {
    setSessionHidden((h) => { prefs.setCpSessionHidden(!h); return !h; });
  };
  useEffect(() => {
    let alive = true;
    api.sessionPrompt().then((r) => { if (alive) setSession(r.prompt); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  async function copySession() {
    await navigator.clipboard.writeText(session);
    setSessionCopied(true);
    setTimeout(() => setSessionCopied(false), 1500);
  }

  const spec = INTENTS.find((i) => i.id === intent)!;
  const needsJd = NEEDS_JD.includes(intent);

  const reset = () => { setPrompt(""); setPasted(""); setPreview(null); setErr(""); setCopied(false); };
  const pick = (id: Intent) => { setIntent(id); reset(); setText(""); setBranch(""); };

  async function generate() {
    setBusy(true); setErr(""); setPreview(null); setPasted("");
    try {
      const body = needsJd ? { intent, jd_text: text } : { intent, note: text };
      setPrompt((await api.copyPrompt(body)).prompt);
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(typeof d === "string" ? d : (d?.message || String((e as Error).message)));
    } finally { setBusy(false); }
  }

  async function copy() {
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function review() {
    setBusy(true); setErr(""); setPreview(null);
    try {
      setPreview(await api.pastePreview(pasted, intent));
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(
        d?.problems ? "That JSON doesn't look like a valid résumé:\n- " + d.problems.join("\n- ")
        : d?.error ? d.error
        : "Couldn't read JSON from that paste. Copy the AI's reply again; it should be a single JSON object."
      );
    } finally { setBusy(false); }
  }

  async function commit() {
    if (!preview) return;
    setBusy(true); setErr("");
    try {
      if (intent === "tailor") {
        await onCreateBranch(preview.data as Resume, branch || "Tailored", text || null);
      } else {
        onApply(preview.data as Resume);  // load into the editor; the commit bar saves the base
      }
      reset(); setText(""); setBranch("");
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(d?.problems ? "Schema problems:\n- " + d.problems.join("\n- ") : String((e as Error).message));
    } finally { setBusy(false); }
  }

  return (
    <div className="cp-body">
      {session && (
        <div className="card cp-session">
          <button className="cp-session-head" onClick={toggleSession} aria-expanded={!sessionHidden}>
            <span className="section-title" style={{ margin: 0 }}>
              Set up a chat{sessionHidden ? "" : " (recommended)"}
            </span>
            <ChevronIcon size={14} className={sessionHidden ? "chev-collapsed" : ""} />
          </button>
          {!sessionHidden && (
            <>
              <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                Paste this into a new AI chat once. It loads your résumé and the commands, so the chat
                has your résumé as context and you can ask follow-ups and iterate without re-pasting.
                When it hands back updated résumé JSON, apply it below.
              </p>
              <button onClick={copySession}>{sessionCopied ? "Copied ✓" : "Copy setup prompt"}</button>
              <details style={{ marginTop: 8 }}>
                <summary className="muted" style={{ cursor: "pointer", fontSize: 12 }}>Preview the prompt</summary>
                <textarea rows={6} readOnly value={session} style={{ marginTop: 8 }} />
              </details>
            </>
          )}
        </div>
      )}

      <p className="muted cp-intro">
        Or copy a one-off request for a single task: pick what you want, copy the prompt, and
        (for changes) paste the reply back to review it.
      </p>

        <div className="ed-modebar cp-intents">
          {INTENTS.map((i) => (
            <button key={i.id} className={"seg" + (intent === i.id ? " on" : "")} onClick={() => pick(i.id)}>
              {i.label}
            </button>
          ))}
        </div>
        <p className="muted cp-blurb">{spec.blurb}</p>

        <div className="field">
          <label>{needsJd ? "Job description" : intent === "ask" ? "Your question" : "What changed"}</label>
          <textarea
            rows={5}
            value={text}
            onChange={(e) => { setText(e.target.value); }}
            placeholder={
              needsJd ? "Paste the JD (company, role, requirements, nice-to-haves)…"
              : intent === "ask" ? "e.g. What's the weakest part of my résumé right now?"
              : "e.g. I finished my internship on Aug 31; update the end date and write final bullets."
            }
          />
        </div>
        {intent === "tailor" && (
          <div className="field">
            <label>Branch name</label>
            <input value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="e.g. Jane Street SWE" />
            {branch && <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>branch <code>{slugify(branch)}</code></div>}
          </div>
        )}
        <div className="row">
          <button className="accent" disabled={busy || !text.trim()} onClick={generate}>
            {busy && !prompt ? "Preparing…" : "Get the prompt"}
          </button>
        </div>

        {prompt && (
          <div className="card cp-prompt">
            <p className="section-title">Copy the prompt</p>
            <button onClick={copy}>{copied ? "Copied ✓" : "Copy prompt"}</button>
            <textarea rows={6} readOnly value={prompt} style={{ marginTop: 8 }} />
            {spec.returnsJson ? (
              <>
                <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                  Paste it into an AI chat, then paste the reply below. Code fences and surrounding prose are fine; we'll pull out the JSON.
                </p>
                <textarea
                  rows={6}
                  value={pasted}
                  onChange={(e) => setPasted(e.target.value)}
                  placeholder="Paste the AI's reply here"
                />
                <div className="row" style={{ marginTop: 8 }}>
                  <button className="accent" disabled={busy || !pasted.trim()} onClick={review}>
                    {busy && !preview ? "Reading…" : "Review changes"}
                  </button>
                </div>
              </>
            ) : (
              <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                Paste it into an AI chat and read the reply there. This is advice, so there's nothing to paste back.
              </p>
            )}
          </div>
        )}

        {preview && (
          <div className="card">
            <p className="section-title">
              {intent === "tailor" ? "Preview vs main (not committed)" : "Proposed base update"}
            </p>
            <Summary items={preview.summary} />
            <details>
              <summary className="muted" style={{ cursor: "pointer" }}>Line-by-line diff</summary>
              <DiffLines lines={preview.diff} />
            </details>
            <div className="row" style={{ marginTop: 12 }}>
              {intent === "tailor" ? (
                <button className="green" disabled={busy} onClick={commit}>
                  <GitBranchIcon size={13} /> Create branch {branch ? slugify(branch) : ""}
                </button>
              ) : (
                <button className="green" disabled={busy} onClick={commit}>
                  Apply to editor
                </button>
              )}
              <button disabled={busy} onClick={() => { setPreview(null); setPasted(""); }}>Discard</button>
            </div>
            {intent !== "tailor" && (
              <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                This loads the update into the editor. Review the live preview, then commit it from the bar below.
              </p>
            )}
          </div>
        )}

      {err && <p className="err" style={{ whiteSpace: "pre-wrap" }}>{err}</p>}
    </div>
  );
}
