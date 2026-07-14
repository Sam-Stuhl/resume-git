import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { Me, VersionDetail, VersionMeta } from "./types";
import { VersionList } from "./components/VersionList";
import { Editor } from "./components/Editor";
import { TailorPanel } from "./components/TailorPanel";
import { PdfPreview } from "./components/PdfPreview";
import { DiffPanel } from "./components/DiffPanel";
import { Settings } from "./components/Settings";

type Tab = "edit" | "tailor" | "pdf" | "diff" | "settings";

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [versions, setVersions] = useState<VersionMeta[]>([]);
  const [current, setCurrent] = useState<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<VersionDetail | null>(null);
  const [tab, setTab] = useState<Tab>("edit");
  const [fatal, setFatal] = useState("");

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
    const pick = selectVersion ?? selected ?? cur ?? (vs[0]?.version ?? null);
    setSelected(pick);
  }, [selected]);

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch((e) => setFatal((e as ApiError).status === 401 ? "Not authenticated." : String(e)));
    refresh().catch((e) => setFatal(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    setTab("pdf");
  };

  const makeCurrent = async () => {
    if (selected == null) return;
    await api.setCurrent(selected);
    await refresh(selected);
  };
  const restore = async () => {
    if (selected == null) return;
    const res = await api.restore(selected);
    await refresh(res.version);
  };

  if (fatal) return <div style={{ padding: 24 }} className="err">{fatal}</div>;

  const empty = versions.length === 0;

  return (
    <div className="app">
      <div className="topbar">
        <h1>Resume Manager</h1>
        <span className="meta">
          {me?.email} · {me?.ai_enabled ? "AI on" : "copy-paste mode"}
          {current != null && ` · current v${String(current).padStart(4, "0")}`}
        </span>
      </div>

      <div className="layout">
        <aside className="sidebar">
          {empty ? (
            <p className="muted">No versions yet. Paste a base resume JSON in the Edit tab and “Save as new base”.</p>
          ) : (
            <>
              <VersionList
                versions={versions}
                selected={selected}
                current={current}
                onSelect={setSelected}
              />
              {selected != null && (
                <div className="row" style={{ marginTop: 10 }}>
                  <button onClick={makeCurrent} disabled={selected === current}>Make current</button>
                  <button onClick={restore}>Restore</button>
                </div>
              )}
            </>
          )}
        </aside>

        <main className="main">
          <nav className="tabs">
            {(["edit", "tailor", "pdf", "diff", "settings"] as Tab[]).map((t) => (
              <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
                {t === "pdf" ? "PDF" : t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </nav>
          <div className="content">
            {tab === "edit" &&
              (detail ? (
                <Editor detail={detail} onSaved={onSaved} />
              ) : (
                <EmptyEditor onSaved={onSaved} />
              ))}
            {tab === "tailor" && me && <TailorPanel me={me} onSaved={onSaved} />}
            {tab === "pdf" && selected != null && <PdfPreview version={selected} />}
            {tab === "diff" && !empty && selected != null && (
              <DiffPanel versions={versions} selected={selected} />
            )}
            {tab === "settings" && me && <Settings me={me} onChange={async () => setMe(await api.me())} />}
          </div>
        </main>
      </div>
    </div>
  );
}

// When there are no versions yet, offer a blank base editor seeded with the schema shape.
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
