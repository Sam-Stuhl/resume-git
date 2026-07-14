interface Props {
  dirty: boolean;
  onMain: boolean;
  branchName: string;
  label: string;
  onLabel: (v: string) => void;
  onCommit: () => void;
  onDiscard: () => void;
  busy: boolean;
}

export function CommitBar({ dirty, onMain, branchName, label, onLabel, onCommit, onDiscard, busy }: Props) {
  return (
    <div className="commit-bar">
      {dirty ? <span className="dirty-dot" /> : null}
      <span className="hint">
        {dirty
          ? onMain
            ? "uncommitted · commit saves a base update to main"
            : `uncommitted · commit refines branch ${branchName}`
          : "no changes"}
      </span>
      <input
        placeholder={onMain ? "commit message (what changed)" : "commit message"}
        value={label}
        onChange={(e) => onLabel(e.target.value)}
      />
      <span className="spacer" />
      {dirty && <button disabled={busy} onClick={onDiscard}>Discard</button>}
      <button className="green" disabled={!dirty || busy} onClick={onCommit}>
        {busy ? "Committing…" : onMain ? "✓ Commit to main" : "✓ Commit"}
      </button>
    </div>
  );
}
