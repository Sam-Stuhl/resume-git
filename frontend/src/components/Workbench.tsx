import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import type { Me, Resume, VersionDetail } from "../types";
import { branchName } from "../lib/git";
import { ResumeEditor } from "./editor/ResumeEditor";
import { LivePdfPreview } from "./LivePdfPreview";
import { CommitBar } from "./CommitBar";
import { ChatPanel } from "./ChatPanel";

/**
 * The build-first Workbench: continuous editor + live PDF preview + a
 * context-aware commit bar, plus the Resume Copilot chat. Committing on a base
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
            <button className={"seg" + (pane === "chat" ? " on" : "")} onClick={() => setPane("chat")}>Copilot</button>
          </div>
        </div>
        <span className="spacer" />
        <button
          className={"wb-chat-toggle" + (chatOpen ? " on" : "")}
          onClick={() => setChatOpen((o) => !o)}
          title="Toggle Resume Copilot"
        >
          Copilot
        </button>
      </div>
      <div className={"workbench pane-" + pane + (chatOpen ? " chat-open" : "")}>
        <div className="wb-editor">
          <ResumeEditor value={working} onChange={setWorking} />
          {err && <p className="err">{err}</p>}
        </div>
        <div className="wb-preview">
          <LivePdfPreview data={working} />
        </div>
        <div className="wb-chat">
          {me && (
            <ChatPanel
              threadKey={threadKey}
              me={me}
              currentData={working}
              onApply={setWorking}
              onCreateBranch={createBranchFromChat}
              onOpenSettings={onOpenSettings}
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
