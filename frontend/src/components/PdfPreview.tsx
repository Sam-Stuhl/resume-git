import { useEffect, useState } from "react";

export function PdfPreview({ version }: { version: number }) {
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let objectUrl = "";
    let cancelled = false;
    setLoading(true);
    setErr("");
    setUrl("");
    fetch(`/api/versions/${version}/pdf`, { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) {
          const d = await res.json().catch(() => ({}));
          throw new Error(d?.detail?.log || d?.detail?.error || d?.detail || res.statusText);
        }
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setUrl(objectUrl);
      })
      .catch((e) => !cancelled && setErr(String(e.message)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [version, nonce]);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div className="row" style={{ marginBottom: 10 }}>
        <button onClick={() => setNonce((n) => n + 1)}>Recompile</button>
        {url && (
          <a href={url} download={`resume_v${String(version).padStart(4, "0")}.pdf`}>
            <button>Download</button>
          </a>
        )}
        {loading && <span className="muted">Compiling…</span>}
      </div>
      {err && (
        <div className="card">
          <p className="section-title">Compilation failed</p>
          <pre className="err">{err}</pre>
        </div>
      )}
      {url && <iframe className="pdf" src={url} title="resume pdf" />}
    </div>
  );
}
