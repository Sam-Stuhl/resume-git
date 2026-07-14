import { useState } from "react";
import type { Resume } from "../../types";
import { SectionEditor } from "./SectionEditor";

/**
 * The center editor: continuous section forms with a raw-JSON escape hatch.
 * Controlled — the working copy lives in the parent (the Workbench).
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
    <div>
      <div className="ed-modebar">
        <button className={"seg" + (mode === "form" ? " on" : "")} onClick={() => setMode("form")}>Form</button>
        <button className={"seg" + (mode === "raw" ? " on" : "")} onClick={enterRaw}>Raw JSON</button>
      </div>
      {mode === "form" ? (
        <SectionEditor value={value} onChange={onChange} />
      ) : (
        <>
          <textarea className="raw" rows={26} value={raw} onChange={(e) => onRaw(e.target.value)} spellCheck={false} />
          {err && <p className="err">{err}</p>}
        </>
      )}
    </div>
  );
}
