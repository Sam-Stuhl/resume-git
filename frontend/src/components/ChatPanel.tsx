import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { ChatMessage, ChatProposal, Me, Resume } from "../types";
import { mergeProposal } from "../lib/proposal";
import { slugify } from "../lib/git";
import { GitBranchIcon } from "./icons";
import { DiffLines, Summary } from "./DiffView";

/**
 * Resume Assistant — a streaming chat docked in the Workbench. Claude advises and,
 * when asked for a concrete change, returns a proposal the user reviews as a diff
 * and applies (staged into the editor) or turns into a new branch.
 */
export function ChatPanel({
  threadKey, me, currentData, onApply, onCreateBranch, onOpenSettings,
}: {
  threadKey: string;
  me: Me;
  currentData: Resume;
  onApply: (resume: Resume) => void;
  onCreateBranch: (data: Resume, label: string, jd: string | null) => Promise<void>;
  onOpenSettings: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [liveText, setLiveText] = useState("");
  const [liveProposal, setLiveProposal] = useState<ChatProposal | null>(null);
  const [err, setErr] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

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
  }, [messages, liveText, liveProposal, streaming]);

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    setErr("");
    const userMsg: ChatMessage = {
      id: -Date.now(), role: "user", content: text, proposal: null, created_at: "",
    };
    setMessages((m) => [...m, userMsg]);
    setStreaming(true);
    setLiveText("");
    setLiveProposal(null);

    let text_ = "";
    let proposal: ChatProposal | null = null;
    try {
      await api.chatStream(
        threadKey,
        { message: text, model: me.default_model, current_data: currentData },
        {
          onDelta: (d) => { text_ += d; setLiveText(text_); },
          onProposal: (p) => { proposal = p; setLiveProposal(p); },
          onToolStep: () => {},
          onAction: () => {},
          onError: (msg) => setErr(msg),
          onDone: () => { /* finalized below */ },
        }
      );
    } catch (e) {
      setErr(String((e as ApiError).message || e));
    } finally {
      setMessages((m) => [
        ...m,
        { id: -Date.now() - 1, role: "assistant", content: text_, proposal, created_at: "" },
      ]);
      setLiveText("");
      setLiveProposal(null);
      setStreaming(false);
    }
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
          <p className="muted">
            Add a Claude API key or a Claude Code token in Settings to chat with your
            resume advisor.
          </p>
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
          <p className="muted chat-hint">
            Ask for advice, an ATS audit, a base update, or to tailor for a job.
            Try: <em>[ATS] how does this read for a backend role?</em>
          </p>
        )}
        {messages.map((m, i) => (
          <Bubble key={m.id} role={m.role} text={m.content}>
            {m.proposal && (
              <ProposalCard
                proposal={m.proposal}
                currentData={currentData}
                suggestedName={m.proposal.intent === "tailor" ? "Tailored" : ""}
                jd={jdFor(i)}
                onApply={onApply}
                onCreateBranch={onCreateBranch}
              />
            )}
          </Bubble>
        ))}
        {streaming && (
          <Bubble role="assistant" text={liveText || "…"}>
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
          </Bubble>
        )}
      </div>

      {err && <p className="err chat-err">{err}</p>}

      <div className="chat-input">
        <textarea
          rows={2}
          value={input}
          placeholder="Message the assistant…  (Enter to send, Shift+Enter for newline)"
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

function Bubble({ role, text, children }: { role: string; text: string; children?: React.ReactNode }) {
  return (
    <div className={"chat-msg " + role}>
      {text && <div className="chat-bubble">{text}</div>}
      {children}
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
  return s.replace(/^\s*\[[A-Z][A-Z ]*\]\s*/, "").trim();
}
