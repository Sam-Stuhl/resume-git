import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type {
  AgentAction, ChatMessage, ChatProposal, Me, Resume, Skill,
} from "../types";
import { mergeProposal } from "../lib/proposal";
import { slugify } from "../lib/git";
import { prefs, type AssistantMode } from "../lib/prefs";
import { GitBranchIcon } from "./icons";
import { DiffLines, Summary } from "./DiffView";
import { CopyPasteAssistant } from "./CopyPasteAssistant";
import { ConnectInApp } from "./ConnectInApp";

/** A turn is an ordered list of blocks in the order they streamed — text, read
 * steps, structural actions, and proposals interleave sequentially (like Claude),
 * rather than being bucketed by type. */
type Block =
  | { kind: "text"; text: string }
  | { kind: "tool"; summary: string }
  | { kind: "action"; action: AgentAction; live: boolean }
  | { kind: "proposal"; proposal: ChatProposal };

type Msg = { id: number; role: "user" | "assistant"; blocks: Block[] };

/** Rebuild a persisted message into blocks. Reloaded history has no interleaved
 * read steps (those aren't persisted); structural actions come back static. */
function toBlocks(m: ChatMessage): Block[] {
  const blocks: Block[] = [];
  if (m.content) blocks.push({ kind: "text", text: m.content });
  const p = m.proposal;
  if (p && "data" in p) blocks.push({ kind: "proposal", proposal: p as ChatProposal });
  else if (p && "actions" in p) {
    for (const a of p.actions) blocks.push({ kind: "action", action: a, live: false });
  }
  return blocks;
}

function suggestedName(p: ChatProposal): string {
  return p.branch_name || (p.intent === "tailor" ? "Tailored" : "");
}

/**
 * Resume Assistant — a streaming chat docked in the Workbench. Claude advises,
 * inspects git history via read tools, proposes résumé changes to review, and can
 * request structural actions (checkout/restore) with confirmation. Everything in a
 * turn renders in the order it happened.
 */
export function ChatPanel({
  threadKey, me, currentData, onApply, onCreateBranch, onRepoChanged, onMeChanged,
}: {
  threadKey: string;
  me: Me;
  currentData: Resume;
  onApply: (resume: Resume) => void;
  onCreateBranch: (data: Resume, label: string, jd: string | null) => Promise<void>;
  onRepoChanged: (v?: number) => void;
  onMeChanged: () => void | Promise<void>;
}) {
  // Which assistant to show: the streaming in-app agent or the copy-paste flow.
  // Default by credential the first time, then remember the user's choice.
  const [mode, setMode] = useState<AssistantMode>(
    () => prefs.assistantMode() ?? (me.ai_enabled ? "agent" : "copypaste")
  );
  const switchMode = (m: AssistantMode) => { setMode(m); prefs.setAssistantMode(m); };

  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [liveBlocks, setLiveBlocks] = useState<Block[]>([]);
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
      .then((rows) => {
        if (alive) setMessages(rows.map((m) => ({ id: m.id, role: m.role, blocks: toBlocks(m) })));
      })
      .catch(() => { /* empty thread / not-yet-created is fine */ });
    return () => { alive = false; };
  }, [threadKey]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, liveBlocks, streaming]);

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

  // Run one streamed assistant turn, accumulating blocks in arrival order.
  async function runTurn(
    start: (h: import("../api").ChatStreamHandlers) => Promise<void>,
    afterDone?: () => void,
  ) {
    setStreaming(true);
    setErr("");
    const acc: Block[] = [];
    setLiveBlocks([]);
    const sync = () => setLiveBlocks([...acc]);
    try {
      await start({
        onDelta: (d) => {
          const last = acc[acc.length - 1];
          if (last && last.kind === "text") last.text += d;
          else acc.push({ kind: "text", text: d });
          sync();
        },
        onProposal: (p) => { acc.push({ kind: "proposal", proposal: p }); sync(); },
        onToolStep: (s) => { acc.push({ kind: "tool", summary: s.summary }); sync(); },
        onAction: (a) => { acc.push({ kind: "action", action: a, live: true }); sync(); },
        onError: (msg) => setErr(msg),
        onDone: () => { /* finalized below */ },
      });
    } catch (e) {
      setErr(String((e as ApiError).message || e));
    } finally {
      setMessages((m) => [...m, { id: -Date.now() - 1, role: "assistant", blocks: acc }]);
      setLiveBlocks([]);
      setStreaming(false);
      afterDone?.();
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;
    const skill = detectSkill(text);
    setInput("");
    setMessages((m) => [...m, { id: -Date.now(), role: "user", blocks: [{ kind: "text", text }] }]);
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

  // The JD/context for a proposal is the most recent user turn before message `idx`.
  function jdFor(idx: number): string | null {
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        const t = messages[i].blocks.find((b): b is Extract<Block, { kind: "text" }> => b.kind === "text");
        return t ? stripTag(t.text) : null;
      }
    }
    return null;
  }

  const renderBlock = (b: Block, key: number, jd: string | null) => {
    if (b.kind === "text") return b.text ? <div key={key} className="chat-bubble">{b.text}</div> : null;
    if (b.kind === "tool") return <div key={key} className="tool-step">{b.summary}</div>;
    if (b.kind === "action") {
      return b.live
        ? <ActionCard key={key} action={b.action} disabled={streaming} onResolve={resolveAction} />
        : <div key={key} className="tool-step">{b.action.summary}</div>;
    }
    return (
      <ProposalCard
        key={key}
        proposal={b.proposal}
        currentData={currentData}
        suggestedName={suggestedName(b.proposal)}
        jd={jd}
        onApply={onApply}
        onCreateBranch={onCreateBranch}
      />
    );
  };

  const liveJd = (() => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    const t = lastUser?.blocks.find((b): b is Extract<Block, { kind: "text" }> => b.kind === "text");
    return t ? stripTag(t.text) : null;
  })();

  return (
    <div className="chatpanel">
      <div className="chat-head">
        <div className="ed-modebar asst-modes">
          <button className={"seg" + (mode === "agent" ? " on" : "")} onClick={() => switchMode("agent")}>In-app</button>
          <button className={"seg" + (mode === "copypaste" ? " on" : "")} onClick={() => switchMode("copypaste")}>Copy-paste</button>
        </div>
        <span className="spacer" />
        {mode === "agent" && me.ai_enabled && messages.length > 0 && (
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

      {mode === "copypaste" ? (
        <CopyPasteAssistant onApply={onApply} onCreateBranch={onCreateBranch} />
      ) : !me.ai_enabled ? (
        <ConnectInApp onSaved={onMeChanged} onUseCopyPaste={() => switchMode("copypaste")} />
      ) : (
        <>
          <div className="chat-msgs" ref={scrollRef}>
            {messages.length === 0 && !streaming && (
              <p className="chat-hint">
                Ask anything about your resume, or type <kbd>/</kbd> for a skill.
              </p>
            )}
            {messages.map((m, i) => (
              <div key={m.id} className={"chat-msg " + m.role}>
                {m.blocks.map((b, bi) => renderBlock(b, bi, jdFor(i)))}
              </div>
            ))}
            {streaming && (
              <div className="chat-msg assistant">
                {liveBlocks.map((b, bi) => renderBlock(b, bi, liveJd))}
                {/* Persist a working indicator until the bot actually answers (text) or
                    produces a result (action/proposal); it stays through read steps. */}
                {(liveBlocks.length === 0 || liveBlocks[liveBlocks.length - 1].kind === "tool") && (
                  <div className="chat-working">Working…</div>
                )}
              </div>
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
        </>
      )}
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
              style={{ maxWidth: 180 }}
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
