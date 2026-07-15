import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { prefs } from "../lib/prefs";
import type { Resume } from "../types";

/** Debounced live PDF of the working copy (unsaved edits). When the auto-compile
 * preference is off, compiling happens only when the user clicks "Compile". */
export function LivePdfPreview({ data }: { data: Resume }) {
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [stale, setStale] = useState(false);
  const objRef = useRef<string>("");
  // Read once on mount. Settings unmounts the editor, so this re-reads on return.
  const [autoCompile] = useState(() => prefs.autoCompile());

  const compile = useCallback((d: Resume) => {
    setLoading(true);
    return api
      .previewPdf(d)
      .then((blob) => {
        const next = URL.createObjectURL(blob);
        if (objRef.current) URL.revokeObjectURL(objRef.current);
        objRef.current = next;
        setUrl(next);
        setErr("");
        setStale(false);
      })
      .catch((e) => {
        const dt: any = (e as ApiError).detail;
        setErr(dt?.log || dt?.error || String((e as Error).message));
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!autoCompile) {
      setStale(true); // mark that the preview no longer matches the edits
      return;
    }
    let cancelled = false;
    const t = setTimeout(() => {
      if (!cancelled) compile(data);
    }, 600);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [data, autoCompile, compile]);

  useEffect(() => () => { if (objRef.current) URL.revokeObjectURL(objRef.current); }, []);

  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="section-title" style={{ margin: 0 }}>Live preview</span>
        {loading && <span className="muted" style={{ fontSize: 12 }}>compiling…</span>}
        {!autoCompile && !loading && (
          <button style={{ fontSize: 12, padding: "2px 10px" }} onClick={() => compile(data)}>
            {url ? "Recompile" : "Compile preview"}
          </button>
        )}
        {url && (
          <a href={url} download="resume.pdf" style={{ marginLeft: "auto", fontSize: 12 }}>Download</a>
        )}
      </div>
      {err ? (
        <div className="card"><p className="section-title">Won't compile</p><pre className="err">{err}</pre></div>
      ) : url ? (
        <>
          {!autoCompile && stale && (
            <p className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Edited. Recompile to update.</p>
          )}
          <iframe className="pdf" src={url} title="live preview" style={{ flex: 1 }} />
        </>
      ) : (
        !autoCompile && <p className="muted" style={{ fontSize: 13 }}>Auto-compile is off. Click "Compile preview" to render.</p>
      )}
    </>
  );
}
