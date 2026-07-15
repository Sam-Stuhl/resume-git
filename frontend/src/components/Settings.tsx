import { useEffect, useState } from "react";
import { api, ApiError, LOGOUT_URL } from "../api";
import type { Me } from "../types";
import { prefs, type EditorMode, type LandingTab } from "../lib/prefs";
import { ImportPanel } from "./ImportPanel";
import { SignOutIcon } from "./icons";

const MODELS = ["claude-sonnet-5", "claude-opus-4-8", "claude-haiku-4-5-20251001"];
const THEMES = [
  { id: "system", label: "System" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
];
const LANDING_TABS: { id: LandingTab; label: string }[] = [
  { id: "edit", label: "Edit" },
  { id: "compare", label: "Compare" },
  { id: "network", label: "Network" },
  { id: "pdf", label: "PDF" },
];

type Section = "profile" | "ai" | "appearance" | "data" | "account" | "danger";
const NAV: { id: Section; label: string }[] = [
  { id: "profile", label: "Profile" },
  { id: "ai", label: "AI & credentials" },
  { id: "appearance", label: "Appearance" },
  { id: "data", label: "Data" },
  { id: "account", label: "Account" },
  { id: "danger", label: "Danger zone" },
];

function initials(me: Me): string {
  const name = me.display_name?.trim();
  if (name) {
    const p = name.split(/\s+/);
    return (p[0][0] + (p[1]?.[0] ?? "")).toUpperCase();
  }
  return (me.email[0] || "?").toUpperCase();
}

function memberSince(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

export function Settings({
  me, theme, setTheme, onChange, onImported,
}: {
  me: Me;
  theme: string;
  setTheme: (t: string) => void;
  onChange: () => void;       // refetch `me` after a server-side save
  onImported: () => void;     // refresh versions after a CLI import
}) {
  const [section, setSection] = useState<Section>("profile");

  // Server-backed fields.
  const [name, setName] = useState(me.display_name ?? "");
  const [key, setKey] = useState("");
  const [model, setModel] = useState(me.default_model);
  const [enabled, setEnabled] = useState(me.ai_enabled);
  const [msg, setMsg] = useState("");

  // Client prefs (instant-apply).
  const [landingTab, setLandingTab] = useState<LandingTab>(() => prefs.landingTab());
  const [editorMode, setEditorMode] = useState<EditorMode>(() => prefs.editorMode());
  const [autoCompile, setAutoCompile] = useState<boolean>(() => prefs.autoCompile());

  useEffect(() => setName(me.display_name ?? ""), [me.display_name]);

  const flash = (m: string) => { setMsg(m); };

  async function saveProfile() {
    await api.saveSettings({ display_name: name.trim() });
    flash("Profile saved.");
    onChange();
  }
  async function saveKey() {
    await api.saveApiKey(key);
    setKey("");
    flash("Credential saved.");
    onChange();
  }
  async function saveAiPrefs() {
    await api.saveSettings({ default_model: model, ai_enabled: enabled });
    flash("Preferences saved.");
    onChange();
  }

  return (
    <div className="settings-page">
      <nav className="settings-nav" aria-label="Settings sections">
        {NAV.map((n) => (
          <button
            key={n.id}
            className={"snode" + (section === n.id ? " sel" : "") + (n.id === "danger" ? " danger" : "")}
            onClick={() => { setSection(n.id); setMsg(""); }}
          >
            {n.label}
          </button>
        ))}
      </nav>

      <div className="settings-panel">
        {section === "profile" && (
          <div className="card">
            <p className="section-title">Profile</p>
            <div className="profile-head">
              <div className="avatar-lg">{initials(me)}</div>
              <div>
                <div className="profile-email">{me.email}</div>
                {memberSince(me.created_at) && (
                  <div className="muted" style={{ fontSize: 12 }}>Member since {memberSince(me.created_at)}</div>
                )}
              </div>
            </div>
            <div className="field">
              <label>Display name</label>
              <div className="row">
                <input value={name} onChange={(e) => setName(e.target.value)} maxLength={200}
                  placeholder="How you want to be shown (optional)" style={{ flex: 1 }} />
                <button className="primary" onClick={saveProfile}>Save</button>
              </div>
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                Shown in the account menu. Separate from your résumé's name.
              </div>
            </div>
            <div className="field">
              <label>Email</label>
              <input value={me.email} readOnly />
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Set by your sign-in; can't be changed here.</div>
            </div>
          </div>
        )}

        {section === "ai" && (
          <div className="card">
            <p className="section-title">AI &amp; credentials</p>
            <div className="field">
              <label>Claude credential: API key or Claude Code token (write-only)</label>
              <div className="row">
                <input type="password" value={key} onChange={(e) => setKey(e.target.value)}
                  placeholder={me.credential_kind ? "•••• (a credential is set)" : "sk-ant-api… or sk-ant-oat…"}
                  style={{ flex: 1 }} />
                <button className="primary" disabled={!key.trim()} onClick={saveKey}>Save</button>
              </div>
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                {me.credential_kind === "oauth"
                  ? "Using a Claude Code OAuth token (bills your Claude subscription)."
                  : me.credential_kind === "api"
                  ? "Using an API key (bills API credits)."
                  : "An sk-ant-api… key bills API credits; an sk-ant-oat… token (from `claude setup-token`) bills your Claude subscription."}
              </div>
            </div>
            <div className="field">
              <label>Default model</label>
              <select value={model} onChange={(e) => setModel(e.target.value)}>
                {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div className="field">
              <label>
                <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} style={{ marginRight: 8 }} />
                Enable in-app AI tailoring (requires a key)
              </label>
            </div>
            <button onClick={saveAiPrefs}>Save preferences</button>
          </div>
        )}

        {section === "appearance" && (
          <div className="card">
            <p className="section-title">Appearance</p>
            <div className="field">
              <label>Theme</label>
              <div className="ed-modebar">
                {THEMES.map((t) => (
                  <button key={t.id} className={"seg" + (theme === t.id ? " on" : "")} onClick={() => setTheme(t.id)}>{t.label}</button>
                ))}
              </div>
            </div>
            <div className="field">
              <label>Default landing tab</label>
              <select value={landingTab} onChange={(e) => { const v = e.target.value as LandingTab; setLandingTab(v); prefs.setLandingTab(v); }}>
                {LANDING_TABS.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Which tab opens when the app loads.</div>
            </div>
            <div className="field">
              <label>Default editor mode</label>
              <div className="ed-modebar">
                {(["form", "raw"] as EditorMode[]).map((m) => (
                  <button key={m} className={"seg" + (editorMode === m ? " on" : "")}
                    onClick={() => { setEditorMode(m); prefs.setEditorMode(m); }}>
                    {m === "form" ? "Form" : "Raw JSON"}
                  </button>
                ))}
              </div>
            </div>
            <div className="field">
              <label>
                <input type="checkbox" checked={autoCompile}
                  onChange={(e) => { setAutoCompile(e.target.checked); prefs.setAutoCompile(e.target.checked); }}
                  style={{ marginRight: 8 }} />
                Auto-compile the live PDF preview while editing
              </label>
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Turn off to compile only on demand (lighter on quota).</div>
            </div>
          </div>
        )}

        {section === "data" && <ImportPanel onImported={onImported} />}

        {section === "account" && (
          <div className="card">
            <p className="section-title">Account</p>
            <div className="profile-head">
              <div className="avatar-lg">{initials(me)}</div>
              <div>
                {me.display_name && <div className="profile-email" style={{ fontWeight: 600 }}>{me.display_name}</div>}
                <div className="profile-email">{me.email}</div>
                {memberSince(me.created_at) && (
                  <div className="muted" style={{ fontSize: 12 }}>Member since {memberSince(me.created_at)}</div>
                )}
              </div>
            </div>
            {me.behind_access ? (
              <a className="btn-logout" href={LOGOUT_URL}>
                <SignOutIcon size={14} /> Log out
              </a>
            ) : (
              <p className="muted" style={{ fontSize: 12 }}>
                Sign-in is managed by Cloudflare Access; there's no session to log out of in local dev.
              </p>
            )}
          </div>
        )}

        {section === "danger" && <DangerZone me={me} />}

        {msg && <p className="muted" style={{ marginTop: 4 }}>{msg}</p>}
      </div>
    </div>
  );
}

function DangerZone({ me }: { me: Me }) {
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!confirming) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && setConfirming(false);
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [confirming]);

  async function doDelete() {
    setBusy(true);
    setErr("");
    try {
      await api.deleteAccount();
      // Fully sign out behind Access; in dev just reload into a fresh account.
      if (me.behind_access) window.location.href = LOGOUT_URL;
      else window.location.reload();
    } catch (e) {
      setErr(String((e as ApiError).message));
      setBusy(false);
    }
  }

  return (
    <div className="card danger-card">
      <p className="section-title">Danger zone</p>
      <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
        Permanently delete your account and <strong>all</strong> of your versions, settings, and chat
        history. This cannot be undone.
      </p>
      <button className="btn-danger" onClick={() => { setConfirming(true); setTyped(""); setErr(""); }}>
        Delete account
      </button>

      {confirming && (
        <div className="modal-backdrop" onClick={() => !busy && setConfirming(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: "min(460px, 100%)" }}>
            <div className="modal-head">
              <div className="modal-title">Delete account?</div>
              <button className="mini ghost" onClick={() => !busy && setConfirming(false)} title="close (Esc)">✕</button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: 13, lineHeight: 1.6 }}>
                This erases everything for <strong>{me.email}</strong>. Type <code>DELETE</code> to confirm.
              </p>
              <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="DELETE" autoFocus
                style={{ width: "100%" }} />
              {err && <p className="err">{err}</p>}
              <div className="row" style={{ marginTop: 12 }}>
                <button className="btn-danger" disabled={busy || typed !== "DELETE"} onClick={doDelete}>
                  {busy ? "Deleting…" : "Permanently delete"}
                </button>
                <button disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
