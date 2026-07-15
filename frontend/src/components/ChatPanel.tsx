import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type {
  AgentAction, ChatMessage, ChatProposal, Me, Resume, Skill, ToolStep,
} from "../types";
import { mergeProposal } from "../lib/proposal";
import { slugify } from "../lib/git";
import { GitBranchIcon } from "./icons";
import { DiffLines, Summary } from "./DiffView";

/** Local message shape: a persisted/finalized ChatMessage plus, for messages
 * produced during this session's live stream, the tool steps and structural
 * actions that accompanied it (rendered as inline lines / confirm cards). */
type Msg = ChatMessage & { steps?: ToolStep[]; actions?: AgentAction[] };

/**
 * Resume Assistant — a streaming chat docked in the Workbench. Claude advises and,
 * when asked for a concrete change, returns a proposal the user reviews as a diff
 * and applies (staged into the editor) or turns into a new branch. It can also
 * inspect git history via read tools (shown as inline `▸` step lines) and propose
 * structural actions like checkout/restore (shown as confirm cards).
 */
export function ChatPanel({
  threadKey, me, currentData, onApply, onCreateBranch, onOpenSettings, onRepoChanged,
}: {
  threadKey: string;
  me: Me;
  currentData: Resume;
  onApply: (resume: Resume) => void;
  onCreateBranch: (data: Resume, label: string, jd: string | null) => Promise<void>;
  onOpenSettings: () => void;
  onRepoChanged: (v?: number) => void;
}) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [liveText, setLiveText] = useState("");
  const [liveProposal, setLiveProposal] = useState<ChatProposal | null>(null);
  const [liveSteps, setLiveSteps] = useState<ToolStep[]>([]);
  const [liveActions, setLiveActions] = useState<AgentAction[]>([]);
  const [err, setErr] = useState("");
  const [skills, setSkills] = useState<Skill[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.skills().then(setSkills).catch(() => {});
  }, []);

  useEffect(() => {
    let alive = true;
    setMessages([]);
    setErr("");
    api.chatHistory(threadKey)
      .then((m) => { if (alive) setMessages(m); })
      .catch(() => { /* empty thread / not-yet-created is fine */ });
    return () => { alive = false; };
  }, [threadKey]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, liveText, liveProposal, liveSteps, liveActions, streaming]);

  // `/` skill menu: show it only while typing the bare /token (no space yet), so it
  // closes as soon as you pick a skill or start typing your actual message.
  const skillQuery = /^\/\S*$/.test(input) ? input.slice(1).toLowerCase() : null;
  const filteredSkills = useMemo(() => {
    if (skillQuery === null) return [];
    return skills.filter((s) => s.name.toLowerCase().includes(skillQuery));
  }, [skillQuery, skills]);

  // Picking from the menu just completes the text inline (e.g. "/tailor ").
  function pickSkill(name: string) {
    setInput((v) => v.replace(/^\/\S*\s?/, `/${name} `));
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  // The active skill is read from the leading /token of the message itself.
  function detectSkill(raw: string): string | undefined {
    const m = raw.match(/^\/([\w-]+)/);
    return m && skills.some((s) => s.name === m[1]) ? m[1] : undefined;
  }

  // Run one streamed assistant turn: manage live state, then finalize the message.
  async function runTurn(
    start: (h: import("../api").ChatStreamHandlers) => Promise<void>,
    afterDone?: () => void,
  ) {
    setStreaming(true);
    setErr("");
    setLiveText(""); setLiveProposal(null); setLiveSteps([]); setLiveActions([]);
    let text_ = "";
    let proposal: ChatProposal | null = null;
    const steps: ToolStep[] = [];
    const actions: AgentAction[] = [];
    try {
      await start({
        onDelta: (d) => { text_ += d; setLiveText(text_); },
        onProposal: (p) => { proposal = p; setLiveProposal(p); },
        onToolStep: (s) => { steps.push(s); setLiveSteps((v) => [...v, s]); },
        onAction: (a) => { actions.push(a); setLiveActions((v) => [...v, a]); },
        onError: (msg) => setErr(msg),
        onDone: () => { /* finalized below */ },
      });
    } catch (e) {
      setErr(String((e as ApiError).message || e));
    } finally {
      setMessages((m) => [
        ...m,
        {
          id: -Date.now() - 1, role: "assistant", content: text_, proposal, created_at: "",
          steps: steps.length ? steps : undefined,
          actions: actions.length ? actions : undefined,
        },
      ]);
      setLiveText(""); setLiveProposal(null); setLiveSteps([]); setLiveActions([]);
      setStreaming(false);
      afterDone?.();
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;
    const skill = detectSkill(text);
    setInput("");
    setMessages((m) => [...m, { id: -Date.now(), role: "user", content: text, proposal: null, created_at: "" }]);
    await runTurn((h) =>
      api.chatStream(threadKey, { message: text, model: me.default_model, current_data: currentData, skill }, h)
    );
  }

  // Approve/decline a structural action; the agent executes it and keeps going.
  async function resolveAction(action: AgentAction, approved: boolean) {
    if (streaming) return;
    await runTurn(
      (h) => api.chatContinue(
        threadKey,
        { tool: action.tool, args: action.args, approved, model: me.default_model, current_data: currentData },
        h,
      ),
      () => { if (approved) onRepoChanged(action.tool === "checkout" ? action.args.version : undefined); },
    );
  }

  function jdFor(index: number): string | null {
    // The JD/context for a proposal is the user turn just before it.
    for (let i = index - 1; i >= 0; i--) {
      if (messages[i].role === "user") return stripTag(messages[i].content);
    }
    return null;
  }

  if (!me.ai_enabled) {
    return (
      <div className="chatpanel">
        <div className="chat-head"><span className="chat-title">Assistant</span></div>
        <div className="chat-empty">
          <p>Connect a Claude API key or Claude Code token to start.</p>
          <button className="accent" onClick={onOpenSettings}>Open Settings</button>
        </div>
      </div>
    );
  }

  return (
    <div className="chatpanel">
      <div className="chat-head">
        <span className="chat-title">Assistant</span>
        <span className="chat-thread">{threadKey}</span>
        <span className="spacer" />
        {messages.length > 0 && (
          <button
            className="chat-clear"
            title="Clear this conversation"
            disabled={streaming}
            onClick={async () => { await api.clearChat(threadKey); setMessages([]); }}
          >
            New chat
          </button>
        )}
      </div>

      <div className="chat-msgs" ref={scrollRef}>
        {messages.length === 0 && !streaming && (
          <p className="chat-hint">
            Ask anything about your resume — or type <kbd>/</kbd> for a skill.
          </p>
        )}
        {messages.map((m, i) => (
          <Bubble key={m.id} role={m.role} text={m.content}>
            {m.steps && m.steps.map((s, si) => (
              <div key={si} className="tool-step">
{s.summary}</div>
            ))}
            {isContentProposal(m.proposal) ? (
              <ProposalCard
                proposal={m.proposal}
                currentData={currentData}
                suggestedName={m.proposal.intent === "tailor" ? "Tailored" : ""}
                jd={jdFor(i)}
                onApply={onApply}
                onCreateBranch={onCreateBranch}
              />
            ) : (
              persistedActions(m.proposal).map((a, ai) => (
                <div key={ai} className="tool-step">
{a.summary}</div>
              ))
            )}
            {m.actions && m.actions.map((a, ai) => (
              <ActionCard key={ai} action={a} disabled={streaming} onResolve={resolveAction} />
            ))}
          </Bubble>
        ))}
        {streaming && (
          <Bubble role="assistant" text={liveText || "…"}>
            {liveSteps.map((s, si) => (
              <div key={si} className="tool-step">
{s.summary}</div>
            ))}
            {liveProposal && (
              <ProposalCard
                proposal={liveProposal}
                currentData={currentData}
                suggestedName={liveProposal.intent === "tailor" ? "Tailored" : ""}
                jd={stripTag(messages[messages.length - 1]?.content ?? "")}
                onApply={onApply}
                onCreateBranch={onCreateBranch}
              />
            )}
            {liveActions.map((a, ai) => (
              <ActionCard key={ai} action={a} disabled={streaming} onResolve={resolveAction} />
            ))}
          </Bubble>
        )}
      </div>

      {err && <p className="err chat-err">{err}</p>}

      {skillQuery !== null && filteredSkills.length > 0 && (
        <div className="chat-skill-menu">
          {filteredSkills.map((s) => (
            <button key={s.name} type="button" onClick={() => pickSkill(s.name)}>
              <span className="sk-name">/{s.name}</span>
              <span className="sk-desc">{s.description}</span>
            </button>
          ))}
        </div>
      )}

      <div className="chat-input">
        <textarea
          ref={inputRef}
          rows={2}
          value={input}
          placeholder="Message the assistant…  (/ for skills · Enter to send, Shift+Enter for newline)"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
          }}
        />
        <button className="primary" disabled={streaming || !input.trim()} onClick={send}>
          {streaming ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}

/** A stored `ChatMessage.proposal` is either a content proposal (has `.data`)
 * or, for turns that only performed structural actions, a `{ actions: [...] }`
 * blob (see `api/routes.py::chat_send`). Narrow on `.data` so the latter never
 * reaches `ProposalCard`. */
function isContentProposal(p: ChatMessage["proposal"]): p is ChatProposal {
  return !!p && "data" in p;
}

function persistedActions(p: ChatMessage["proposal"]): AgentAction[] {
  return p && "actions" in p ? p.actions : [];
}

function Bubble({ role, text, children }: { role: string; text: string; children?: React.ReactNode }) {
  return (
    <div className={"chat-msg " + role}>
      {text && <div className="chat-bubble">{text}</div>}
      {children}
    </div>
  );
}

/** Permission prompt for a structural action (checkout/restore). Resolving hands
 * the decision to the server, which executes it and streams the agent's
 * continuation — so approving doesn't dead-end the chat. */
function ActionCard({ action, disabled, onResolve }: {
  action: AgentAction;
  disabled: boolean;
  onResolve: (action: AgentAction, approved: boolean) => void;
}) {
  const [done, setDone] = useState<"" | "done" | "cancelled">("");

  if (done === "done") return <div className="action-card done">✓ {action.summary}</div>;
  if (done === "cancelled") return <div className="action-card">✕ Cancelled — {action.summary}</div>;
  return (
    <div className="action-card">
      <span>{action.summary}?</span>
      <div className="row">
        <button className="green" disabled={disabled} onClick={() => { setDone("done"); onResolve(action, true); }}>Confirm</button>
        <button disabled={disabled} onClick={() => { setDone("cancelled"); onResolve(action, false); }}>Cancel</button>
      </div>
    </div>
  );
}

function ProposalCard({
  proposal, currentData, suggestedName, jd, onApply, onCreateBranch,
}: {
  proposal: ChatProposal;
  currentData: Resume;
  suggestedName: string;
  jd: string | null;
  onApply: (resume: Resume) => void;
  onCreateBranch: (data: Resume, label: string, jd: string | null) => Promise<void>;
}) {
  const changes = proposal.section_changes;
  const [accepted, setAccepted] = useState<Set<string>>(
    () => new Set(changes.map((c) => c.key))
  );
  const [applied, setApplied] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState(suggestedName);
  const [busy, setBusy] = useState(false);

  const merged = useMemo(
    () => mergeProposal(currentData, proposal, accepted),
    [currentData, proposal, accepted]
  );
  const isTailor = proposal.intent === "tailor";

  function toggle(key: string) {
    setAccepted((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  return (
    <div className="chat-proposal">
      <p className="section-title">Proposed changes</p>
      <Summary items={proposal.summary} />

      {changes.length > 0 && (
        <div className="sec-accept-list">
          {changes.map((c) => (
            <div key={c.key} className="sec-accept">
              <label>
                <input type="checkbox" checked={accepted.has(c.key)} onChange={() => toggle(c.key)} />
                <span className={"sec-tag " + c.status}>{c.status}</span>
                <span className="sec-name">{c.title}</span>
              </label>
              <details>
                <summary className="muted">diff</summary>
                <DiffLines lines={c.diff} />
              </details>
            </div>
          ))}
        </div>
      )}

      <details className="full-diff">
        <summary className="muted">Full line-by-line diff</summary>
        <DiffLines lines={proposal.diff} />
      </details>

      <div className="row proposal-actions">
        <button
          className={isTailor ? "" : "green"}
          disabled={busy || applied}
          onClick={() => { onApply(merged); setApplied(true); }}
        >
          {applied ? "Applied to editor ✓" : "Apply to editor"}
        </button>
        {!creating ? (
          <button className={isTailor ? "green" : ""} disabled={busy} onClick={() => setCreating(true)}>
            <GitBranchIcon size={13} /> Create branch…
          </button>
        ) : (
          <>
            <input
              value={name}
              placeholder="Branch name"
              onChange={(e) => setName(e.target.value)}
              style={{ maxWidth: 160 }}
            />
            <button
              className="green"
              disabled={busy || !name.trim()}
              onClick={async () => {
                setBusy(true);
                try { await onCreateBranch(merged, name.trim(), jd); }
                finally { setBusy(false); }
              }}
            >
              {busy ? "Creating…" : `Create ${slugify(name) || "branch"}`}
            </button>
            <button disabled={busy} onClick={() => setCreating(false)}>Cancel</button>
          </>
        )}
      </div>
    </div>
  );
}

function stripTag(s: string): string {
  // Drop a leading [TAG] or /skill token so a proposal's JD is just the request.
  return s.replace(/^\s*(\[[A-Z][A-Z ]*\]|\/[\w-]+)\s*/, "").trim();
}
