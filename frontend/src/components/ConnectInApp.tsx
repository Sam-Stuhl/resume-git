import { useState } from "react";
import { api } from "../api";

/** Shown on the In-app tab when no credential is connected. Explains what the
 * streaming assistant does and lets the user paste a key right here. */
export function ConnectInApp({
  onSaved, onUseCopyPaste,
}: {
  onSaved: () => void | Promise<void>;   // refetch identity so the agent chat appears
  onUseCopyPaste: () => void;
}) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function save() {
    if (!key.trim()) return;
    setBusy(true);
    setErr("");
    try {
      await api.saveApiKey(key.trim());
      setKey("");
      await onSaved();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="connect-inapp">
      <p className="ci-lead">
        The in-app assistant streams answers, reads your version history, and applies changes
        with your confirmation. It needs a Claude key.
      </p>
      <div className="field">
        <label>Paste a Claude key</label>
        <div className="row">
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="sk-ant-api… or sk-ant-oat…"
            onKeyDown={(e) => { if (e.key === "Enter") save(); }}
            style={{ flex: 1 }}
          />
          <button className="primary" disabled={busy || !key.trim()} onClick={save}>
            {busy ? "Saving…" : "Connect"}
          </button>
        </div>
        <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
          An <code>sk-ant-api…</code> key bills API credits; an <code>sk-ant-oat…</code> token
          (from <code>claude setup-token</code>) bills your Claude subscription. Stored write-only.
        </div>
      </div>
      {err && <p className="err">{err}</p>}
      <p className="muted" style={{ fontSize: 12, marginTop: 14 }}>
        No key? <button className="linklike" onClick={onUseCopyPaste}>Use copy-paste instead</button>,
        which works with any AI chat.
      </p>
    </div>
  );
}
