import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { Resume } from "../types";

/** Debounced live PDF of the working copy (unsaved edits). */
export function LivePdfPreview({ data }: { data: Resume }) {
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const objRef = useRef<string>("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(() => {
      api
        .previewPdf(data)
        .then((blob) => {
          if (cancelled) return;
          const next = URL.createObjectURL(blob);
          if (objRef.current) URL.revokeObjectURL(objRef.current);
          objRef.current = next;
          setUrl(next);
          setErr("");
        })
        .catch((e) => {
          if (cancelled) return;
          const d: any = (e as ApiError).detail;
          setErr(d?.log || d?.error || String((e as Error).message));
        })
        .finally(() => !cancelled && setLoading(false));
    }, 600);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [data]);

  useEffect(() => () => { if (objRef.current) URL.revokeObjectURL(objRef.current); }, []);

  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="section-title" style={{ margin: 0 }}>Live preview</span>
        {loading && <span className="muted" style={{ fontSize: 12 }}>compiling…</span>}
        {url && (
          <a href={url} download="resume.pdf" style={{ marginLeft: "auto", fontSize: 12 }}>Download</a>
        )}
      </div>
      {err ? (
        <div className="card"><p className="section-title">Won't compile</p><pre className="err">{err}</pre></div>
      ) : (
        url && <iframe className="pdf" src={url} title="live preview" style={{ flex: 1 }} />
      )}
    </>
  );
}
