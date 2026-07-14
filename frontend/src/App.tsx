import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { Me, VersionDetail, VersionMeta } from "./types";
import { BranchRail } from "./components/BranchRail";
import { Editor } from "./components/Editor";
import { TailorPanel } from "./components/TailorPanel";
import { PdfPreview } from "./components/PdfPreview";
import { DiffPanel } from "./components/DiffPanel";
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

  const onSaved = async (v: number) => {
    await refresh(v);
    setMe(await api.me());
    setView("pdf");
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
        <button className="accent" onClick={() => setView("tailor")} disabled={empty}>
          ⑃ Tailor
        </button>
        <button className="icon-btn" title={`Theme: ${theme.theme}`} onClick={theme.cycle}>
          {theme.icon}
        </button>
        <span className="who">
          {me?.email} · {me?.ai_enabled ? "AI on" : "copy-paste"}
        </span>
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
              <button
                key={t.id}
                className={"tab" + (view === t.id ? " active" : "")}
                onClick={() => setView(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>
          <div className="content">
            {view === "edit" &&
              (detail ? (
                <Editor detail={detail} onSaved={onSaved} />
              ) : (
                <>
                  {empty && <ImportPanel onImported={() => refresh()} />}
                  <EmptyEditor onSaved={onSaved} />
                </>
              ))}
            {view === "tailor" && me && <TailorPanel me={me} onSaved={onSaved} />}
            {view === "pdf" && selected != null && <PdfPreview version={selected} />}
            {view === "compare" && !empty && selected != null && (
              <DiffPanel versions={versions} selected={selected} />
            )}
            {view === "network" && (
              <div className="card">
                <p className="section-title">Network</p>
                <p className="muted">The branch graph lands in a later pass. For now, the rail on the left shows your commits and branches.</p>
              </div>
            )}
            {view === "settings" && me && (
              <>
                <Settings me={me} onChange={async () => setMe(await api.me())} />
                <ImportPanel onImported={() => refresh()} />
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

// Blank base editor seeded with the schema shape, shown when there are no commits.
function EmptyEditor({ onSaved }: { onSaved: (v: number) => void }) {
  const skeleton: VersionDetail = {
    version: 0,
    created_at: "",
    label: null,
    is_base: true,
    forked_from: null,
    json_hash: "",
    jd_text: null,
    data: {
      personal: { name: "", email: "", phone: "", github: "", linkedin: "" },
      summary: "",
      experience: [],
      projects: [],
      leadership: [],
      skills: {},
      education: [],
    },
  };
  return <Editor detail={skeleton} onSaved={onSaved} />;
}
