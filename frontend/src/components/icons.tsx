// Small octicon-style icons. They inherit `currentColor`, so they theme
// automatically wherever they're used.

type P = { size?: number; className?: string };

export function GitBranchIcon({ size = 16, className }: P) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden="true">
      <path d="M9.5 3.25a2.25 2.25 0 1 1 3 2.122V6A2.5 2.5 0 0 1 10 8.5H6a1 1 0 0 0-1 1v1.128a2.251 2.251 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.5 0v1.836A2.492 2.492 0 0 1 6 7h4a1 1 0 0 0 1-1v-.628A2.25 2.25 0 0 1 9.5 3.25Zm-6 0a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Zm8.25-.75a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5ZM4.25 12a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Z" />
    </svg>
  );
}

export function GearIcon({ size = 16, className }: P) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden="true">
      <path d="M8 0c.18 0 .358.006.534.017.643.055 1.194.517 1.348 1.152l.19.74a5.79 5.79 0 0 1 1.006.582l.727-.22a1.5 1.5 0 0 1 1.635.552c.203.283.388.58.552.888a1.5 1.5 0 0 1-.283 1.71l-.537.548c.03.35.03.702 0 1.052l.537.548a1.5 1.5 0 0 1 .283 1.71c-.164.308-.35.605-.552.888a1.5 1.5 0 0 1-1.635.552l-.727-.22a5.79 5.79 0 0 1-1.006.582l-.19.74a1.5 1.5 0 0 1-1.348 1.152 6.68 6.68 0 0 1-1.068 0 1.5 1.5 0 0 1-1.348-1.152l-.19-.74a5.79 5.79 0 0 1-1.006-.582l-.727.22a1.5 1.5 0 0 1-1.635-.552 6.65 6.65 0 0 1-.552-.888 1.5 1.5 0 0 1 .283-1.71l.537-.548a5.87 5.87 0 0 1 0-1.052l-.537-.548a1.5 1.5 0 0 1-.283-1.71c.164-.308.35-.605.552-.888a1.5 1.5 0 0 1 1.635-.552l.727.22a5.79 5.79 0 0 1 1.006-.582l.19-.74A1.5 1.5 0 0 1 7.466.017 6.68 6.68 0 0 1 8 0Zm0 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm0 1.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Z" />
    </svg>
  );
}

export function ChevronIcon({ size = 16, className }: P) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12.78 5.22a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L3.22 6.28a.75.75 0 0 1 1.06-1.06L8 8.94l3.72-3.72a.75.75 0 0 1 1.06 0Z" />
    </svg>
  );
}

export function MenuIcon({ size = 16, className }: P) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden="true">
      <path d="M1 2.75A.75.75 0 0 1 1.75 2h12.5a.75.75 0 0 1 0 1.5H1.75A.75.75 0 0 1 1 2.75Zm0 5A.75.75 0 0 1 1.75 7h12.5a.75.75 0 0 1 0 1.5H1.75A.75.75 0 0 1 1 7.75ZM1.75 12h12.5a.75.75 0 0 1 0 1.5H1.75a.75.75 0 0 1 0-1.5Z" />
    </svg>
  );
}
