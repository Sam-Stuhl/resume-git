import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { Me, VersionDetail, VersionMeta } from "./types";
import { BranchRail } from "./components/BranchRail";
import { Workbench } from "./components/Workbench";
import { TailorFlow } from "./components/TailorFlow";
import { PdfPreview } from "./components/PdfPreview";
import { Compare } from "./components/Compare";
import { NetworkGraph } from "./components/NetworkGraph";
import { Settings } from "./components/Settings";
import { ImportPanel } from "./components/ImportPanel";
import { branchName, ref } from "./lib/git";

type View = "edit" | "compare" | "network" | "pdf" | "settings" | "tailor";
const TABS: { id: View; label: string }[] = [
  { id: "edit", label: "Edit" },
  { id: "compare", label: "Compare" },
  { id: "network", label: "Network" },
  { id: "pdf", label: "PDF" },
  { id: "settings", label: "Settings" },
];

const SKELETON: VersionDetail = {
  version: 0, created_at: "", label: null, is_base: true, forked_from: null,
  json_hash: "", jd_text: null,
  data: {
    personal: { name: "", email: "", phone: "", github: "", linkedin: "" },
    sections: [],
  },
};

function useTheme() {
  const [theme, setTheme] = useState<string>(() => localStorage.getItem("theme") || "system");
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);
  const cycle = () => setTheme((t) => (t === "dark" ? "light" : t === "light" ? "system" : "dark"));
  const icon = theme === "dark" ? "☾" : theme === "light" ? "☀" : "◐";
  return { icon, cycle, theme };
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [versions, setVersions] = useState<VersionMeta[]>([]);
  const [current, setCurrent] = useState<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<VersionDetail | null>(null);
  const [view, setView] = useState<View>("edit");
  const [fatal, setFatal] = useState("");
  const theme = useTheme();

  const refresh = useCallback(async (selectVersion?: number) => {
    const vs = await api.versions();
    setVersions(vs);
    let cur: number | null = null;
    try {
      cur = (await api.current()).version;
    } catch {
      cur = null;
    }
    setCurrent(cur);
    setSelected((prev) => selectVersion ?? prev ?? cur ?? vs[0]?.version ?? null);
  }, []);

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch((e) => setFatal((e as ApiError).status === 401 ? "Not authenticated." : String(e)));
    refresh().catch((e) => setFatal(String(e)));
  }, [refresh]);

  useEffect(() => {
    if (selected == null) {
      setDetail(null);
      return;
    }
    api.version(selected).then(setDetail).catch(() => setDetail(null));
  }, [selected]);

  const onCommitted = async (v: number) => {
    await refresh(v);
    setMe(await api.me());
  };

  const checkout = async () => {
    if (selected == null) return;
    await api.setCurrent(selected);
    await refresh(selected);
  };

  if (fatal) return <div style={{ padding: 24 }} className="err">{fatal}</div>;

  const empty = versions.length === 0;
  const owner = me?.email ? me.email.split("@")[0] : "you";
  const headMeta = versions.find((v) => v.version === current);
  const onMain = headMeta ? headMeta.is_base : true;
  const editDetail = detail ?? (empty ? SKELETON : null);

  return (
    <div className="app">
      <div className="appbar">
        <span className="repo">
          <span className="ico">▤</span>
          <span className="owner">{owner} /</span>
          <span className="name">resume</span>
        </span>
        <span className={"branch-pill " + (onMain ? "main" : "branch")}>
          ⎇ {headMeta ? branchName(headMeta) : "main"}
        </span>
        {current != null && <span className="head-badge">HEAD {ref(current)}</span>}
        <span className="spacer" />
        <button className="accent" onClick={() => setView("tailor")} disabled={empty}>⑃ Tailor</button>
        <button className="icon-btn" title={`Theme: ${theme.theme}`} onClick={theme.cycle}>{theme.icon}</button>
        <span className="who">{me?.email} · {me?.ai_enabled ? "AI on" : "copy-paste"}</span>
      </div>

      <div className="layout">
        <aside className="sidebar">
          {empty ? (
            <p className="muted">No commits yet. Add your resume on the Edit tab, or import from the CLI.</p>
          ) : (
            <>
              <BranchRail versions={versions} selected={selected} current={current} onSelect={setSelected} />
              {selected != null && selected !== current && (
                <div className="row" style={{ marginTop: 12 }}>
                  <button className="green" onClick={checkout}>Checkout {ref(selected)}</button>
                </div>
              )}
            </>
          )}
        </aside>

        <main className="main">
          <nav className="tabs">
            {TABS.map((t) => (
              <button key={t.id} className={"tab" + (view === t.id ? " active" : "")} onClick={() => setView(t.id)}>
                {t.label}
              </button>
            ))}
          </nav>

          {view === "edit" ? (
            editDetail ? (
              <div className="edit-fill">
                {empty && (
                  <div style={{ padding: 16, borderBottom: "1px solid var(--border)" }}>
                    <ImportPanel onImported={() => refresh()} />
                  </div>
                )}
                <Workbench detail={editDetail} onCommitted={onCommitted} />
              </div>
            ) : (
              <div className="content"><p className="muted">Loading…</p></div>
            )
          ) : (
            <div className="content">
              {view === "tailor" && me && <TailorFlow me={me} onCreated={onCommitted} />}
              {view === "pdf" && selected != null && <PdfPreview version={selected} />}
              {view === "compare" && !empty && selected != null && (
                <Compare versions={versions} selected={selected} />
              )}
              {view === "network" && !empty && (
                <NetworkGraph versions={versions} current={current} selected={selected} onSelect={setSelected} />
              )}
              {view === "settings" && me && (
                <>
                  <Settings me={me} onChange={async () => setMe(await api.me())} />
                  <ImportPanel onImported={() => refresh()} />
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
