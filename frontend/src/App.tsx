import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { Me, VersionDetail, VersionMeta } from "./types";
import { BranchRail } from "./components/BranchRail";
import { Workbench } from "./components/Workbench";
import { BranchFlow } from "./components/BranchFlow";
import { PdfPreview } from "./components/PdfPreview";
import { Compare } from "./components/Compare";
import { NetworkGraph } from "./components/NetworkGraph";
import { CommitModal } from "./components/CommitModal";
import { Settings } from "./components/Settings";
import { OnboardingWizard } from "./components/OnboardingWizard";
import { UserMenu } from "./components/UserMenu";
import { Tour } from "./components/Tour";
import { GitBranchIcon, MenuIcon } from "./components/icons";
import { branchName, ref } from "./lib/git";
import { prefs } from "./lib/prefs";

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
  return { theme, setTheme };
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [versions, setVersions] = useState<VersionMeta[]>([]);
  const [current, setCurrent] = useState<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<VersionDetail | null>(null);
  const [view, setView] = useState<View>(() => prefs.landingTab());
  const [modalVersion, setModalVersion] = useState<number | null>(null);
  const [railOpen, setRailOpen] = useState<boolean>(() => {
    const s = localStorage.getItem("railOpen");
    return s == null ? window.innerWidth > 820 : s === "1";
  });
  const [fatal, setFatal] = useState("");
  const [wizardDismissed, setWizardDismissed] = useState(false);
  const [tourActive, setTourActive] = useState(false);
  const { theme, setTheme } = useTheme();

  const startTour = useCallback(() => { setView("edit"); setTourActive(true); }, []);

  useEffect(() => { localStorage.setItem("railOpen", railOpen ? "1" : "0"); }, [railOpen]);

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

  // A brand-new empty account must land on the onboarding wizard (Edit view),
  // regardless of the saved default-landing-tab preference.
  useEffect(() => {
    if (versions.length === 0 && !wizardDismissed) setView("edit");
  }, [versions.length, wizardDismissed]);

  // First-run product tour: auto-start once the account has a résumé (i.e. past
  // onboarding) and the tour hasn't been shown. Delay lets the editor mount so
  // the spotlight targets exist.
  useEffect(() => {
    if (versions.length === 0 || prefs.tourSeen()) return;
    const t = setTimeout(() => { setView("edit"); setTourActive(true); }, 500);
    return () => clearTimeout(t);
  }, [versions.length]);

  const onCommitted = async (v?: number) => {
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
  const showWizard = empty && !wizardDismissed;
  const headMeta = versions.find((v) => v.version === current);
  const onMain = headMeta ? headMeta.is_base : true;
  const editDetail = detail ?? (empty ? SKELETON : null);

  return (
    <div className="app">
      <div className="appbar">
        <button className="icon-btn" title="Toggle history" onClick={() => setRailOpen((o) => !o)}>
          <MenuIcon size={16} />
        </button>
        <span className="wordmark"><GitBranchIcon size={16} className="wm-ico" /> resume-git</span>
        <span className={"branch-pill " + (onMain ? "on-main" : "on-branch")}>
          <GitBranchIcon size={12} /> {headMeta ? branchName(headMeta) : "main"}
        </span>
        {current != null && <span className="head-badge">HEAD {ref(current)}</span>}
        <span className="spacer" />
        <button className="accent branch-btn" onClick={() => setView("tailor")} disabled={empty}>
          <GitBranchIcon size={14} /> <span className="nb-text">New branch</span>
        </button>
        {me && <UserMenu me={me} onOpenSettings={() => setView("settings")} onStartTour={startTour} />}
      </div>

      <div className="layout">
        {railOpen && (
          <aside className="sidebar">
            {empty ? (
              <p className="muted" style={{ padding: "6px 10px" }}>No commits yet. Add your resume on the Edit tab, or import from the CLI.</p>
            ) : (
              <>
                <BranchRail
                  versions={versions}
                  selected={selected}
                  current={current}
                  onSelect={setSelected}
                  onOpen={setModalVersion}
                />
                {selected != null && selected !== current && (
                  <div className="row" style={{ margin: "10px 12px" }}>
                    <button className="green" onClick={checkout}>Checkout {ref(selected)}</button>
                  </div>
                )}
              </>
            )}
          </aside>
        )}

        <main className="main">
          <nav className="tabs">
            {TABS.map((t) => (
              <button key={t.id} className={"tab" + (view === t.id ? " active" : "")} onClick={() => setView(t.id)}>
                {t.label}
              </button>
            ))}
          </nav>

          {view === "edit" ? (
            showWizard ? (
              <OnboardingWizard
                onFinish={async (v) => { setWizardDismissed(true); await onCommitted(v); }}
                onStartBlank={() => setWizardDismissed(true)}
              />
            ) : editDetail ? (
              <div className="edit-fill">
                <Workbench detail={editDetail} me={me} onCommitted={onCommitted} onOpenSettings={() => setView("settings")} />
              </div>
            ) : (
              <div className="content"><p className="muted">Loading…</p></div>
            )
          ) : view === "network" ? (
            !empty ? (
              <div className="net-fill">
                <NetworkGraph versions={versions} current={current} selected={selected} onSelect={setSelected} onOpen={setModalVersion} />
              </div>
            ) : (
              <div className="content"><p className="muted">No commits yet.</p></div>
            )
          ) : (
            <div className="content">
              {view === "tailor" && me && <BranchFlow me={me} onCreated={onCommitted} />}
              {view === "pdf" && selected != null && <PdfPreview version={selected} />}
              {view === "compare" && !empty && selected != null && (
                <Compare versions={versions} selected={selected} />
              )}
              {view === "settings" && me && (
                <Settings
                  me={me}
                  theme={theme}
                  setTheme={setTheme}
                  onChange={async () => setMe(await api.me())}
                  onImported={() => refresh()}
                />
              )}
            </div>
          )}
        </main>
      </div>
      {tourActive && <Tour onClose={() => setTourActive(false)} />}
      {modalVersion != null && (
        <CommitModal versions={versions} version={modalVersion} onClose={() => setModalVersion(null)} />
      )}
    </div>
  );
}
