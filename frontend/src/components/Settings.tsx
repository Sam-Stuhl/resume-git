import { useState } from "react";
import { api } from "../api";
import type { Me } from "../types";

const MODELS = ["claude-sonnet-5", "claude-opus-4-8", "claude-haiku-4-5-20251001"];

const THEMES: { id: string; label: string }[] = [
  { id: "system", label: "System" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
];

export function Settings({
  me, theme, setTheme, onChange,
}: {
  me: Me;
  theme: string;
  setTheme: (t: string) => void;
  onChange: () => void;
}) {
  const [key, setKey] = useState("");
  const [model, setModel] = useState(me.default_model);
  const [enabled, setEnabled] = useState(me.ai_enabled);
  const [msg, setMsg] = useState("");

  async function saveKey() {
    await api.saveApiKey(key);
    setKey("");
    setMsg("API key saved.");
    onChange();
  }
  async function savePrefs() {
    await api.saveSettings({ default_model: model, ai_enabled: enabled });
    setMsg("Preferences saved.");
    onChange();
  }

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <p className="section-title">Settings</p>
      <div className="field">
        <label>Theme</label>
        <div className="ed-modebar">
          {THEMES.map((t) => (
            <button key={t.id} className={"seg" + (theme === t.id ? " on" : "")} onClick={() => setTheme(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="field">
        <label>Claude API key (write-only — never displayed)</label>
        <div className="row">
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder={me.ai_enabled ? "•••• (a key is set)" : "sk-ant-…"}
            style={{ flex: 1 }}
          />
          <button className="primary" disabled={!key.trim()} onClick={saveKey}>Save key</button>
        </div>
      </div>
      <div className="field">
        <label>Default model</label>
        <select value={model} onChange={(e) => setModel(e.target.value)}>
          {MODELS.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label>
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            style={{ marginRight: 8 }}
          />
          Enable in-app AI tailoring (requires a key)
        </label>
      </div>
      <button onClick={savePrefs}>Save preferences</button>
      {msg && <p className="muted" style={{ marginTop: 8 }}>{msg}</p>}
    </div>
  );
}
