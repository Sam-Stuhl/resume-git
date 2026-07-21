import { useEffect, useState } from "react";
import { api, ApiError } from "../../api";
import type { TailorPreview } from "../../types";
import { DiffLines, Summary } from "../DiffView";
import { ChatIcon, ChevronRightIcon, DocIcon, GitBranchIcon, KeyIcon, SparkIcon } from "../icons";

/**
 * New-user onboarding funnel for a brand-new empty account. A small state
 * machine (has / ai) drives which screen shows; a "crumbs" trail along the
 * top summarizes the answers so far. Replaces the old 3-route OnboardingWizard.
 *
 * Q1 asks whether the user already has a résumé (or lets them skip straight
 * to a blank editor). Q2 asks how they want to power the AI assistant, and
 * routes to either the connect screen (Claude Pro/Max or an API key) or the
 * copy-paste screen (no key, any AI chat). The connect screen saves the
 * credential, then hands off to the in-app assistant chat with the composer
 * preloaded via onOpenAssistant.
 */

type Ai = "pro" | "api" | "none";
type Screen = "q1" | "q2" | "connect" | "copypaste";

const AI_CRUMB: Record<Ai, string> = {
  pro: "Claude Pro",
  api: "API key",
  none: "No subscription",
};

export function OnboardingFlow({
  onFinish, onStartBlank, onOpenAssistant,
}: {
  onFinish: (createdVersion?: number) => void;   // a base résumé was created inside the funnel
  onStartBlank: () => void;                       // dismiss and hand off to the skeleton editor
  onOpenAssistant: (initialInput: string) => void; // connect finished; open the assistant preloaded
}) {
  const [has, setHas] = useState<boolean | null>(null);
  const [ai, setAi] = useState<Ai | null>(null);

  // Keyless copy-paste route state (convert if has, build if !has).
  const [cpPrompt, setCpPrompt] = useState("");
  const [cpPasted, setCpPasted] = useState("");
  const [cpPreview, setCpPreview] = useState<TailorPreview | null>(null);
  const [cpBusy, setCpBusy] = useState(false);
  const [cpCopied, setCpCopied] = useState(false);
  const [cpErr, setCpErr] = useState("");

  // Connect route state (Claude Pro/Max setup-token or an Anthropic API key).
  const [credKey, setCredKey] = useState("");
  const [credBusy, setCredBusy] = useState(false);
  const [credErr, setCredErr] = useState("");

  const screen: Screen =
    has === null ? "q1"
    : ai === null ? "q2"
    : ai === "none" ? "copypaste"
    : "connect";

  function resetCopyPaste() {
    setCpPrompt(""); setCpPasted(""); setCpPreview(null);
    setCpBusy(false); setCpCopied(false); setCpErr("");
  }

  // Fetch the ready-to-copy prompt as soon as the copy-paste route is shown;
  // convert (has a résumé) vs build (starting fresh) get different prompts.
  useEffect(() => {
    if (screen !== "copypaste") return;
    let cancelled = false;
    resetCopyPaste();
    const call = has ? api.onboardingPrompt() : api.onboardingBuildPrompt();
    call
      .then((r) => { if (!cancelled) setCpPrompt(r.prompt); })
      .catch((e) => { if (!cancelled) setCpErr(String((e as ApiError).message)); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screen, has]);

  async function copyCpPrompt() {
    await navigator.clipboard.writeText(cpPrompt);
    setCpCopied(true);
    setTimeout(() => setCpCopied(false), 1500);
  }

  async function reviewPaste() {
    setCpBusy(true); setCpErr("");
    try {
      setCpPreview(await api.pastePreview(cpPasted, "base-update"));
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setCpErr(
        d?.problems ? "That JSON isn't a valid résumé:\n- " + d.problems.join("\n- ")
        : "Couldn't read JSON from that paste. Copy the AI's reply again; it should be one JSON object."
      );
    } finally { setCpBusy(false); }
  }

  async function useAsResume() {
    if (!cpPreview) return;
    setCpBusy(true); setCpErr("");
    try {
      const created = await api.createBase(cpPreview.data, "Base");
      onFinish(created.version);
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setCpErr(d?.problems ? "Schema problems:\n- " + d.problems.join("\n- ") : String((e as Error).message));
      setCpBusy(false);
    }
  }

  function discardPaste() {
    setCpPreview(null);
    setCpPasted("");
  }

  function chooseHas(v: boolean) {
    setHas(v);
    setAi(null);
  }
  function backToQ1() {
    setHas(null);
    setAi(null);
  }
  function backToQ2() {
    setAi(null);
    setCredKey("");
    setCredErr("");
  }

  // The message the assistant chat opens with: a convert prompt (paste your
  // résumé) if the user already has one, otherwise a build prompt (kick off
  // the question-by-question build).
  const preloadText = has
    ? "Here's my résumé:\n\n[paste your résumé here]"
    : "Yes, let's start. Ask me your first question.";

  async function connect() {
    if (!credKey.trim()) return;
    setCredBusy(true);
    setCredErr("");
    try {
      await api.saveApiKey(credKey.trim());
      onOpenAssistant(preloadText);
    } catch (e) {
      setCredErr(String((e as ApiError).message || e));
      setCredBusy(false);
    }
  }

  const crumbs = has !== null && (
    <div className="crumbs">
      <span className="c on">{has ? "Has a résumé" : "Starting fresh"}</span>
      {ai && <span className="c on">{AI_CRUMB[ai]}</span>}
    </div>
  );

  return (
    <div className="onb-flow">
      <div className="card">
        {screen === "q1" && (
          <div className="onb-step">
            <span className="wm"><GitBranchIcon size={16} className="mk" /> resume-git</span>
            <h1 className="t">Welcome. Let's set up your résumé.</h1>
            <p className="lead">An AI does the editing for you. First: do you already have a résumé?</p>
            <div className="opts">
              <button className="opt" onClick={() => chooseHas(true)}>
                <span className="ic"><DocIcon size={16} /></span>
                <span className="oc">
                  <span className="ot">Yes, I have a résumé</span>
                  <span className="od">We'll turn it into your first version, ready to tailor.</span>
                </span>
                <ChevronRightIcon size={16} className="chev" />
              </button>
              <button className="opt" onClick={() => chooseHas(false)}>
                <span className="ic"><SparkIcon size={16} /></span>
                <span className="oc">
                  <span className="ot">No, start fresh</span>
                  <span className="od">The assistant will build one with you, from scratch.</span>
                </span>
                <ChevronRightIcon size={16} className="chev" />
              </button>
            </div>
            <button className="linklike manual" onClick={onStartBlank}>or I'll fill it in myself →</button>
          </div>
        )}

        {screen === "q2" && (
          <div className="onb-step">
            {crumbs}
            <h1 className="t">How do you want to use the AI?</h1>
            <p className="lead">This powers the assistant that writes and tailors your résumé. Pick what you have.</p>
            <div className="opts">
              <button className="opt" onClick={() => setAi("pro")}>
                <span className="ic"><SparkIcon size={16} /></span>
                <span className="oc">
                  <span className="ot">Claude Pro or Max</span>
                  <span className="od">Use your subscription. You'll paste a login token from <code>claude setup-token</code>.</span>
                </span>
                <ChevronRightIcon size={16} className="chev" />
              </button>
              <button className="opt" onClick={() => setAi("api")}>
                <span className="ic"><KeyIcon size={16} /></span>
                <span className="oc">
                  <span className="ot">Anthropic API key</span>
                  <span className="od">Paste an <code>sk-ant-api...</code> key. Bills API credits.</span>
                </span>
                <ChevronRightIcon size={16} className="chev" />
              </button>
              <button className="opt" onClick={() => setAi("none")}>
                <span className="ic"><ChatIcon size={16} /></span>
                <span className="oc">
                  <span className="ot">None of these</span>
                  <span className="od">No problem. Copy a prompt into any AI chat, free. No key needed.</span>
                </span>
                <ChevronRightIcon size={16} className="chev" />
              </button>
            </div>
            <div className="back">
              <button className="linklike" onClick={backToQ1}>← Back</button>
            </div>
          </div>
        )}

        {screen === "connect" && (
          <div className="onb-step">
            {crumbs}
            <h1 className="t">{ai === "pro" ? "Connect your Claude subscription" : "Connect your API key"}</h1>
            <p className="lead">
              {ai === "pro" ? (
                <>Run <code>claude setup-token</code> in your terminal and paste the token it prints. It starts with <code>sk-ant-oat</code> and bills your Claude subscription.</>
              ) : (
                <>Paste a key from console.anthropic.com. It starts with <code>sk-ant-api</code> and bills API credits.</>
              )}
            </p>
            <label className="onb-field-label">{ai === "pro" ? "Login token" : "API key"}</label>
            <input
              type="password"
              value={credKey}
              onChange={(e) => setCredKey(e.target.value)}
              placeholder={ai === "pro" ? "sk-ant-oat..." : "sk-ant-api..."}
              autoComplete="off"
              onKeyDown={(e) => { if (e.key === "Enter" && !credBusy) connect(); }}
            />
            <div className="row">
              <button className="green" disabled={credBusy || !credKey.trim()} onClick={connect}>
                {credBusy ? "Connecting…" : "Connect and open the assistant"}
              </button>
              <button className="linklike" onClick={backToQ2}>← Back</button>
            </div>
            {credErr && <p className="err" style={{ marginTop: 10 }}>{credErr}</p>}
            <p className="onb-hint">Saved to your account and never shown again.</p>
          </div>
        )}

        {screen === "copypaste" && (
          <div className="onb-step">
            {crumbs}
            <h1 className="t">Copy this into any AI chat</h1>
            <p className="lead">
              {has ? (
                <>Paste the prompt into any AI chat, <strong>attach your résumé</strong> (any file your AI accepts), and send. Then paste the AI's reply back here.</>
              ) : (
                "Paste the prompt into any AI chat, answer its questions, then paste its reply back here."
              )}
            </p>

            {cpPrompt ? (
              <div className="onb-pbox">
                <div className="onb-pbox-head">
                  Prompt
                  <button className="onb-pbox-copy" onClick={copyCpPrompt}>{cpCopied ? "Copied ✓" : "Copy"}</button>
                </div>
                <div className="onb-pbox-body">
                  <textarea rows={7} readOnly value={cpPrompt} />
                </div>
              </div>
            ) : (
              !cpErr && <p className="muted" style={{ fontSize: 13, marginTop: 16 }}>Preparing the prompt…</p>
            )}

            {cpPrompt && !cpPreview && (
              <>
                <label className="onb-field-label">Paste the AI's reply here</label>
                <textarea
                  rows={4}
                  value={cpPasted}
                  onChange={(e) => setCpPasted(e.target.value)}
                  placeholder="Paste whatever the AI sent back"
                />
                <p className="onb-hint">
                  Paste the whole reply, even if it looks like code. We'll turn it into a clean résumé and show you a friendly summary before anything is saved.
                </p>
                <div className="row">
                  <button className="accent" disabled={cpBusy || !cpPasted.trim()} onClick={reviewPaste}>
                    {cpBusy ? "Reading…" : "Review"}
                  </button>
                </div>
              </>
            )}

            {cpPreview && (
              <div className="card" style={{ marginTop: 16 }}>
                <p className="section-title">Your résumé</p>
                <Summary items={cpPreview.summary} />
                <details>
                  <summary className="muted" style={{ cursor: "pointer" }}>Line-by-line</summary>
                  <DiffLines lines={cpPreview.diff} />
                </details>
                <div className="row" style={{ marginTop: 12 }}>
                  <button className="green" disabled={cpBusy} onClick={useAsResume}>Use as my résumé</button>
                  <button disabled={cpBusy} onClick={discardPaste}>Discard</button>
                </div>
              </div>
            )}

            {cpErr && <p className="err" style={{ marginTop: 10 }}>{cpErr}</p>}

            <div className="back"><button className="linklike" onClick={backToQ2}>← Back</button></div>
          </div>
        )}
      </div>
    </div>
  );
}
