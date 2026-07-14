import type { DiffLine } from "../types";

export function Summary({ items }: { items: string[] }) {
  return (
    <ul className="summary">
      {items.map((s, i) => (
        <li key={i}>{s}</li>
      ))}
    </ul>
  );
}

export function DiffLines({ lines }: { lines: DiffLine[] }) {
  if (!lines.length) return <p className="muted">No differences.</p>;
  return (
    <pre className="diff">
      {lines.map((l, i) => (
        <div key={i} className={l.tag}>
          {l.text || " "}
        </div>
      ))}
    </pre>
  );
}
