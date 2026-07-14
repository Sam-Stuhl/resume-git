import { useRef, type ReactNode } from "react";

export function Field({
  label, value, onChange, placeholder,
}: {
  label: string;
  value: string | undefined;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="ef">
      <span className="ef-k">{label}</span>
      <input value={value ?? ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </label>
  );
}

export function Area({
  label, value, onChange, rows = 3,
}: {
  label: string;
  value: string | undefined;
  onChange: (v: string) => void;
  rows?: number;
}) {
  return (
    <label className="ef">
      <span className="ef-k">{label}</span>
      <textarea rows={rows} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

/** Editable, reorderable list of bullet strings. */
export function Bullets({ items, onChange }: { items: string[]; onChange: (b: string[]) => void }) {
  const from = useRef<number | null>(null);
  const move = (a: number, b: number) => {
    if (b < 0 || b >= items.length) return;
    const next = [...items];
    const [x] = next.splice(a, 1);
    next.splice(b, 0, x);
    onChange(next);
  };
  return (
    <div className="bullets">
      {items.map((b, i) => (
        <div
          className="bullet-row"
          key={i}
          draggable
          onDragStart={() => (from.current = i)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={() => {
            if (from.current != null) move(from.current, i);
            from.current = null;
          }}
        >
          <span className="grip" title="drag to reorder">⠿</span>
          <input
            value={b}
            onChange={(e) => {
              const next = [...items];
              next[i] = e.target.value;
              onChange(next);
            }}
          />
          <button className="mini" title="remove" onClick={() => onChange(items.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <button className="mini add" onClick={() => onChange([...items, ""])}>+ bullet</button>
    </div>
  );
}

/** Generic reorderable list of entry cards (experience, projects, etc.). */
export function EntryList<T>({
  items, onChange, empty, addLabel, render,
}: {
  items: T[];
  onChange: (x: T[]) => void;
  empty: () => T;
  addLabel: string;
  render: (item: T, update: (patch: Partial<T>) => void) => ReactNode;
}) {
  const from = useRef<number | null>(null);
  const move = (a: number, b: number) => {
    if (b < 0 || b >= items.length) return;
    const next = [...items];
    const [x] = next.splice(a, 1);
    next.splice(b, 0, x);
    onChange(next);
  };
  return (
    <div>
      {items.map((item, i) => (
        <div
          className="entry-card"
          key={i}
          onDragOver={(e) => e.preventDefault()}
          onDrop={() => {
            if (from.current != null) move(from.current, i);
            from.current = null;
          }}
        >
          <div className="entry-head">
            <span className="grip" draggable onDragStart={() => (from.current = i)} title="drag to reorder">⠿</span>
            <span className="spacer" />
            <button className="mini" title="move up" onClick={() => move(i, i - 1)}>▲</button>
            <button className="mini" title="move down" onClick={() => move(i, i + 1)}>▼</button>
            <button className="mini" title="remove" onClick={() => onChange(items.filter((_, j) => j !== i))}>✕</button>
          </div>
          {render(item, (patch) => {
            const next = [...items];
            next[i] = { ...items[i], ...patch };
            onChange(next);
          })}
        </div>
      ))}
      <button className="add-entry" onClick={() => onChange([...items, empty()])}>+ {addLabel}</button>
    </div>
  );
}
