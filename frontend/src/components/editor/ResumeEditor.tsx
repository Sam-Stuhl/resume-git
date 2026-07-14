import { lazy, Suspense, useState } from "react";
import type { Resume } from "../../types";
import { SectionEditor } from "./SectionEditor";

const RawJsonEditor = lazy(() => import("./RawJsonEditor"));

/**
 * The center editor: continuous section forms with a raw-JSON escape hatch.
 * The raw view is a real code editor (CodeMirror) lazy-loaded on demand.
 */
export function ResumeEditor({ value, onChange }: { value: Resume; onChange: (r: Resume) => void }) {
  const [mode, setMode] = useState<"form" | "raw">("form");
  const [raw, setRaw] = useState("");
  const [err, setErr] = useState("");

  const enterRaw = () => {
    setRaw(JSON.stringify(value, null, 2));
    setErr("");
    setMode("raw");
  };

  const onRaw = (t: string) => {
    setRaw(t);
    try {
      const parsed = JSON.parse(t);
      setErr("");
      onChange(parsed);
    } catch (e) {
      setErr("Invalid JSON: " + (e as Error).message);
    }
  };

  return (
    <div className="resume-editor">
      <div className="ed-modebar">
        <button className={"seg" + (mode === "form" ? " on" : "")} onClick={() => setMode("form")}>Form</button>
        <button className={"seg" + (mode === "raw" ? " on" : "")} onClick={enterRaw}>Raw JSON</button>
      </div>
      {mode === "form" ? (
        <div className="ed-scroll">
          <SectionEditor value={value} onChange={onChange} />
        </div>
      ) : (
        <div className="cm-wrap">
          <Suspense fallback={<p className="muted">Loading editor…</p>}>
            <RawJsonEditor value={raw} onChange={onRaw} />
          </Suspense>
          {err && <p className="err" style={{ marginTop: 8 }}>{err}</p>}
        </div>
      )}
    </div>
  );
}
