import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { Me, Resume, VersionDetail } from "../types";
import { branchName } from "../lib/git";
import { ResumeEditor } from "./editor/ResumeEditor";
import { LivePdfPreview } from "./LivePdfPreview";
import { CommitBar } from "./CommitBar";
import { ChatPanel } from "./ChatPanel";

const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n));
const WIDE_Q = "(min-width: 901px)";

/** A draggable vertical divider between two grid panes. */
function Resizer({ onDrag }: { onDrag: (dx: number) => void }) {
  const start = (e: React.PointerEvent) => {
    e.preventDefault();
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    let last = e.clientX;
    const move = (ev: PointerEvent) => { onDrag(ev.clientX - last); last = ev.clientX; };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  return <div className="wb-resizer" onPointerDown={start} role="separator" aria-orientation="vertical" />;
}

/**
 * The build-first Workbench: continuous editor + live PDF preview + a
 * context-aware commit bar, plus the Resume Assistant chat. Committing on a base
 * commit writes a new base (main); on a tailored branch it refines that branch.
 */
export function Workbench({ detail, me, onCommitted, onOpenSettings }: {
  detail: VersionDetail;
  me: Me | null;
  onCommitted: (v: number) => void;
  onOpenSettings: () => void;
}) {
  const [working, setWorking] = useState<Resume>(detail.data as Resume);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [pane, setPane] = useState<"editor" | "preview" | "chat">("editor"); // narrow-screen toggle
  const [chatOpen, setChatOpen] = useState(false); // wide-screen third column

  // Draggable pane widths (wide screens only; persisted).
  const wbRef = useRef<HTMLDivElement>(null);
  const [isWide, setIsWide] = useState(() => window.matchMedia(WIDE_Q).matches);
  const [splitPct, setSplitPct] = useState(() => Number(localStorage.getItem("wbSplit")) || 50);
  const [chatW, setChatW] = useState(() => Number(localStorage.getItem("wbChatW")) || 380);

  useEffect(() => {
    const m = window.matchMedia(WIDE_Q);
    const h = () => setIsWide(m.matches);
    m.addEventListener("change", h);
    return () => m.removeEventListener("change", h);
  }, []);
  useEffect(() => { localStorage.setItem("wbSplit", String(splitPct)); }, [splitPct]);
  useEffect(() => { localStorage.setItem("wbChatW", String(chatW)); }, [chatW]);

  const dragSplit = (dx: number) => {
    const w = wbRef.current?.clientWidth ?? 1000;
    const region = chatOpen ? w - chatW - 12 : w; // width shared by the editor+preview fr tracks
    setSplitPct((p) => clamp(p + (dx / Math.max(region, 1)) * 100, 20, 80));
  };
  const dragChat = (dx: number) => {
    const w = wbRef.current?.clientWidth ?? 1000;
    setChatW((cw) => clamp(cw - dx, 300, Math.min(720, w - 360)));
  };

  const cols = chatOpen
    ? `${splitPct}fr 6px ${100 - splitPct}fr 6px ${chatW}px`
    : `${splitPct}fr 6px ${100 - splitPct}fr`;

  useEffect(() => {
    setWorking(detail.data as Resume);
    setLabel("");
    setErr("");
  }, [detail.version]);

  const onMain = detail.is_base;
  const dirty = useMemo(
    () => JSON.stringify(working) !== JSON.stringify(detail.data),
    [working, detail.data]
  );

  const commit = async () => {
    setBusy(true);
    setErr("");
    try {
      const res = onMain
        ? await api.createBase(working, label || "Update")
        : await api.createTailor(working, label || detail.label || "Tailored", detail.jd_text);
      onCommitted(res.version);
    } catch (e) {
      const d: any = (e as ApiError).detail;
      setErr(d?.problems ? "Schema problems:\n- " + d.problems.join("\n- ") : String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const createBranchFromChat = async (data: Resume, name: string, jd: string | null) => {
    const res = await api.createTailor(data, name || "Branch", jd);
    onCommitted(res.version);
  };

  const threadKey = detail.is_base ? "main" : branchName(detail);

  return (
    <div className="wb-wrap">
      <div className="wb-toolbar">
        <div className="pane-toggle">
          <div className="ed-modebar">
            <button className={"seg" + (pane === "editor" ? " on" : "")} onClick={() => setPane("editor")}>Editor</button>
            <button className={"seg" + (pane === "preview" ? " on" : "")} onClick={() => setPane("preview")}>Preview</button>
            <button className={"seg" + (pane === "chat" ? " on" : "")} onClick={() => setPane("chat")}>Assistant</button>
          </div>
        </div>
        <span className="spacer" />
        <button
          className={"wb-chat-toggle" + (chatOpen ? " on" : "")}
          onClick={() => setChatOpen((o) => !o)}
          title="Toggle Resume Assistant"
        >
          Assistant
        </button>
      </div>
      <div
        className={"workbench pane-" + pane + (chatOpen ? " chat-open" : "")}
        ref={wbRef}
        style={isWide ? { gridTemplateColumns: cols } : undefined}
      >
        <div className="wb-editor">
          <ResumeEditor value={working} onChange={setWorking} />
          {err && <p className="err">{err}</p>}
        </div>
        <Resizer onDrag={dragSplit} />
        <div className="wb-preview">
          <LivePdfPreview data={working} />
        </div>
        {chatOpen && <Resizer onDrag={dragChat} />}
        <div className="wb-chat">
          {me && (
            <ChatPanel
              threadKey={threadKey}
              me={me}
              currentData={working}
              onApply={setWorking}
              onCreateBranch={createBranchFromChat}
              onOpenSettings={onOpenSettings}
              onRepoChanged={(v) => { if (v !== undefined) onCommitted(v); }}
            />
          )}
        </div>
      </div>
      <CommitBar
        dirty={dirty}
        onMain={onMain}
        branchName={branchName(detail)}
        label={label}
        onLabel={setLabel}
        onCommit={commit}
        onDiscard={() => setWorking(detail.data as Resume)}
        busy={busy}
      />
    </div>
  );
}
