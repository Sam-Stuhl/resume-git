import { useState } from "react";
import { ChatIcon, ChevronRightIcon, DocIcon, GitBranchIcon, KeyIcon, SparkIcon } from "../icons";

/**
 * New-user onboarding funnel for a brand-new empty account. A small state
 * machine (has / ai) drives which screen shows; a "crumbs" trail along the
 * top summarizes the answers so far. Replaces the old 3-route OnboardingWizard.
 *
 * Q1 asks whether the user already has a résumé (or lets them skip straight
 * to a blank editor). Q2 asks how they want to power the AI assistant, and
 * routes to either the connect screen (Claude Pro/Max or an API key) or the
 * copy-paste screen (no key, any AI chat). This task implements Q1 and Q2
 * fully; connect and copy-paste are placeholders for Tasks 8 and 7.
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

  // onFinish and onOpenAssistant aren't called by this task's placeholder
  // connect/copy-paste screens; Tasks 7 and 8 wire them in when those screens
  // get real bodies. Referencing them here keeps the interface stable and
  // satisfies noUnusedParameters in the meantime.
  void onFinish;
  void onOpenAssistant;

  const screen: Screen =
    has === null ? "q1"
    : ai === null ? "q2"
    : ai === "none" ? "copypaste"
    : "connect";

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
          // TODO(Task 8): connect + preloaded chat. Real screen collects a
          // claude setup-token (pro) or sk-ant-api key (api), saves it, then
          // calls onOpenAssistant(initialInput) to hand off to a preloaded chat.
          <div className="onb-step">
            {crumbs}
            <h1 className="t">{ai === "pro" ? "Connect your Claude subscription" : "Connect your API key"}</h1>
            <p className="lead">Placeholder: implemented in a later task.</p>
            <div className="back"><button className="linklike" onClick={backToQ2}>← Back</button></div>
          </div>
        )}

        {screen === "copypaste" && (
          // TODO(Task 7): copy-paste route. Real screen shows the ready-to-copy
          // prompt (via api.onboardingPrompt) and a paste-back box that calls
          // onFinish(createdVersion) once the AI's reply is reviewed and saved.
          <div className="onb-step">
            {crumbs}
            <h1 className="t">Copy this into any AI chat</h1>
            <p className="lead">Placeholder: implemented in a later task.</p>
            <div className="back"><button className="linklike" onClick={backToQ2}>← Back</button></div>
          </div>
        )}
      </div>
    </div>
  );
}
