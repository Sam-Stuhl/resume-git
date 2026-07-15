import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { TailorPreview } from "../types";
import { ImportPanel } from "./ImportPanel";
import { DiffLines, Summary } from "./DiffView";
import { GitBranchIcon } from "./icons";

/**
 * First-run wizard for a brand-new empty account. Three calm steps: what this is,
 * build a base résumé (convert-with-AI / start blank / import a CLI bundle), then
 * an optional AI-credential explainer. The convert route is the keyless bootstrap:
 * copy the prompt into any AI chat with your resume attached, paste the JSON back.
 */
type Step = "welcome" | "base" | "ai";
type BaseRoute = "paste" | "blank" | "import";

export function OnboardingWizard({
  onFinish, onStartBlank,
}: {
  onFinish: (createdVersion?: number) => void;  // a base was created inside the wizard
  onStartBlank: () => void;                     // dismiss and hand off to the skeleton editor
}) {
  const [step, setStep] = useState<Step>("welcome");
  const [route, setRoute] = useState<BaseRoute>("paste");

  // Convert-with-AI state.
  const [prompt, setPrompt] = useState("");
  const [pasted, setPasted] = useState("");
  const [preview, setPreview] = useState<TailorPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState("");

  // AI step: optional inline key.
  const [key, setKey] = useState("");
  const [keySaved, setKeySaved] = useState(false);

  // Fetch the ready-to-copy prompt as soon as the convert route is shown.
  useEffect(() => {
    if (step !== "base" || route !== "paste" || prompt) return;
    let cancelled = false;
    api.onboardingPrompt()
      .then((r) => { if (!cancelled) setPrompt(r.prompt); })
      .catch((e) => { if (!cancelled) setErr(String((e as ApiError).message)); });
    return () => { cancelled = true; };
  }, [step, route, prompt]);

  async function copy() {
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function review() {
    setBusy(true); setErr("");
    try {
      setPreview(await api.pastePreview(pasted, "base-update"));
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(
        d?.problems ? "That JSON isn't a valid résumé:\n- " + d.problems.join("\n- ")
        : "Couldn't read JSON from that paste. Copy the AI's reply again; it should be one JSON object."
      );
    } finally { setBusy(false); }
  }

  async function commitBase() {
    if (!preview) return;
    setBusy(true); setErr("");
    try {
      await api.createBase(preview.data, "Base");
      setStep("ai");
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(d?.problems ? "Schema problems:\n- " + d.problems.join("\n- ") : String((e as Error).message));
    } finally { setBusy(false); }
  }

  async function saveKey() {
    if (!key.trim()) return;
    await api.saveApiKey(key.trim());
    setKey("");
    setKeySaved(true);
  }

  return (
    <div className="onb-wrap">
      <div className="onb-card">
        <div className="onb-steps">
          {(["welcome", "base", "ai"] as Step[]).map((s, i) => (
            <span key={s} className={"onb-dot" + (step === s ? " on" : "") + (["welcome","base","ai"].indexOf(step) > i ? " done" : "")} />
          ))}
        </div>

        {step === "welcome" && (
          <div className="onb-step">
            <h1 className="onb-title"><GitBranchIcon size={20} /> Welcome to resume-git</h1>
            <p className="onb-lead">
              Version control for your résumé. One canonical résumé is your <strong>base</strong>;
              branch off it to tailor for a specific job, review the diff, and compile to a PDF —
              all without ever losing history.
            </p>
            <p className="muted onb-sub">Let's set up your base résumé. It takes a minute.</p>
            <div className="row">
              <button className="accent" onClick={() => setStep("base")}>Get started</button>
            </div>
          </div>
        )}

        {step === "base" && (
          <div className="onb-step">
            <h2 className="onb-title">Add your base résumé</h2>
            <div className="ed-modebar onb-routes">
              <button className={"seg" + (route === "paste" ? " on" : "")} onClick={() => setRoute("paste")}>Paste & convert</button>
              <button className={"seg" + (route === "blank" ? " on" : "")} onClick={() => setRoute("blank")}>Start blank</button>
              <button className={"seg" + (route === "import" ? " on" : "")} onClick={() => setRoute("import")}>Import from CLI</button>
            </div>

            {route === "paste" && (
              <div>
                <p className="muted onb-sub">
                  Copy the prompt below into any AI chat, attach your résumé (a PDF or text), and send it.
                  Paste the JSON it returns back here. No key needed.
                </p>

                {prompt ? (
                  <div className="card cp-prompt">
                    <p className="section-title">1. Copy the prompt</p>
                    <button onClick={copy}>{copied ? "Copied ✓" : "Copy prompt"}</button>
                    <textarea rows={5} readOnly value={prompt} style={{ marginTop: 8 }} />
                    <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>
                      2. Paste it into an AI chat with your résumé attached, then paste the reply below.
                      Code fences and extra prose are fine.
                    </p>
                    <textarea rows={5} value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="Paste the AI's reply here" />
                    <div className="row" style={{ marginTop: 8 }}>
                      <button className="accent" disabled={busy || !pasted.trim()} onClick={review}>
                        {busy && !preview ? "Reading…" : "Review"}
                      </button>
                    </div>
                  </div>
                ) : (
                  !err && <p className="muted" style={{ fontSize: 13 }}>Preparing the prompt…</p>
                )}

                {preview && (
                  <div className="card">
                    <p className="section-title">Your base résumé</p>
                    <Summary items={preview.summary} />
                    <details>
                      <summary className="muted" style={{ cursor: "pointer" }}>Line-by-line</summary>
                      <DiffLines lines={preview.diff} />
                    </details>
                    <div className="row" style={{ marginTop: 12 }}>
                      <button className="green" disabled={busy} onClick={commitBase}>Use as my base</button>
                      <button disabled={busy} onClick={() => { setPreview(null); setPasted(""); }}>Discard</button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {route === "blank" && (
              <div>
                <p className="muted onb-sub">
                  Start from an empty résumé and fill it in the editor. You can always connect the
                  assistant later.
                </p>
                <div className="row">
                  <button className="accent" onClick={onStartBlank}>Open the editor</button>
                </div>
              </div>
            )}

            {route === "import" && (
              <div>
                <p className="muted onb-sub">Already used the CLI? Bring your full history across.</p>
                <ImportPanel onImported={() => onFinish()} />
              </div>
            )}

            {err && <p className="err" style={{ whiteSpace: "pre-wrap", marginTop: 10 }}>{err}</p>}
            <button className="onb-back linklike" onClick={() => setStep("welcome")}>← Back</button>
          </div>
        )}

        {step === "ai" && (
          <div className="onb-step">
            <h2 className="onb-title">Connect Claude (optional)</h2>
            <p className="onb-lead">Your base is saved. The assistant can tailor, audit, and update it. Two ways to use it:</p>
            <ul className="onb-list">
              <li><strong>Claude Code token</strong> — run <code>claude setup-token</code> and paste the <code>sk-ant-oat…</code> it prints (bills your Claude subscription).</li>
              <li><strong>Claude API key</strong> — an <code>sk-ant-api…</code> key from the Anthropic console (bills API credits).</li>
              <li><strong>No key</strong> — use the built-in <strong>copy-paste assistant</strong> with any Claude.ai chat.</li>
            </ul>
            <div className="field">
              <label>Paste a credential now (optional)</label>
              <div className="row">
                <input type="password" value={key} onChange={(e) => setKey(e.target.value)}
                  placeholder="sk-ant-api… or sk-ant-oat…" style={{ flex: 1 }} />
                <button className="primary" disabled={!key.trim()} onClick={saveKey}>Save</button>
              </div>
              {keySaved && <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Credential saved ✓</div>}
            </div>
            <div className="row" style={{ marginTop: 8 }}>
              <button className="accent" onClick={() => onFinish()}>
                {keySaved ? "Finish" : "Skip — I'll use copy-paste"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
