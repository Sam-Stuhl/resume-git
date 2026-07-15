import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { prefs } from "../lib/prefs";

/** One coach-mark: a CSS selector to spotlight plus the copy to show. */
type Step = { selector: string; title: string; body: string };

const STEPS: Step[] = [
  {
    selector: ".wb-editor",
    title: "Edit your résumé",
    body: "Fill in sections here. JSON is the source of truth; switch to Raw JSON any time for direct edits.",
  },
  {
    selector: ".wb-preview",
    title: "Live PDF preview",
    body: "Your résumé compiles to a one-page PDF as you type. Download it any time.",
  },
  {
    selector: ".commit-bar",
    title: "Commit a version",
    body: "Save with a short message. Nothing is ever overwritten: every save is a new commit you can return to.",
  },
  {
    selector: ".branch-btn",
    title: "Branch for a job",
    body: "Fork a branch to tailor your résumé to a specific role. Your base stays untouched.",
  },
  {
    selector: ".tabs",
    title: "Review your history",
    body: "Compare any two versions, or see the whole history as a network graph. PDF opens the current commit.",
  },
  {
    selector: ".wb-chat-toggle",
    title: "The Resume Assistant",
    body: "Ask the AI to tailor, audit (ATS), or update your résumé. No key connected? A copy-paste assistant works with any AI chat.",
  },
];

const POP_W = 340;
const clamp = (n: number, lo: number, hi: number) => Math.min(Math.max(n, lo), hi);

/** First-run spotlight tour. Dims the app and highlights each area in turn.
 * Skippable at any point; marks itself seen on finish or skip. */
export function Tour({ onClose }: { onClose: () => void }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [pos, setPos] = useState<{ left: number; top: number }>({ left: 0, top: 0 });
  const popRef = useRef<HTMLDivElement>(null);
  const step = STEPS[i];

  const finish = () => { prefs.setTourSeen(true); onClose(); };
  const next = () => (i < STEPS.length - 1 ? setI(i + 1) : finish());
  const back = () => setI((n) => Math.max(0, n - 1));

  // Track the target's position (and follow resize / scroll).
  useEffect(() => {
    let raf = 0;
    const measure = () => {
      const el = document.querySelector(step.selector);
      setRect(el ? el.getBoundingClientRect() : null);
    };
    measure();
    const onMove = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(measure); };
    window.addEventListener("resize", onMove);
    window.addEventListener("scroll", onMove, true);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onMove);
      window.removeEventListener("scroll", onMove, true);
    };
  }, [step.selector]);

  // Place the popover once we know its measured height. Beside tall targets,
  // above/below short ones, always clamped into the viewport.
  useLayoutEffect(() => {
    const pop = popRef.current;
    if (!pop) return;
    const pw = pop.offsetWidth, ph = pop.offsetHeight;
    const vw = window.innerWidth, vh = window.innerHeight, m = 12;
    if (!rect) { setPos({ left: (vw - pw) / 2, top: (vh - ph) / 2 }); return; }
    let left: number, top: number;
    if (rect.height > vh * 0.55) {
      left = rect.right + m + pw < vw ? rect.right + m
        : rect.left - m - pw > 0 ? rect.left - m - pw
        : (vw - pw) / 2;
      top = rect.top;
    } else {
      top = rect.bottom + m + ph < vh ? rect.bottom + m : rect.top - m - ph;
      left = rect.left;
    }
    setPos({ left: clamp(left, m, vw - pw - m), top: clamp(top, m, vh - ph - m) });
  }, [rect, i]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
      else if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  const pad = 6;
  const spot = rect
    ? { top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }
    : null;

  return createPortal(
    <div className="tour-root">
      {spot && <div className="tour-spot" style={spot} />}
      <div className="tour-pop" ref={popRef} style={{ left: pos.left, top: pos.top, width: POP_W }} role="dialog" aria-label="Product tour">
        <div className="tour-progress">{i + 1} of {STEPS.length}</div>
        <h4 className="tour-title">{step.title}</h4>
        <p className="tour-body">{step.body}</p>
        <div className="tour-actions">
          <button className="tour-skip" onClick={finish}>Skip tour</button>
          <span className="spacer" />
          {i > 0 && <button onClick={back}>Back</button>}
          <button className="accent" onClick={next}>{i === STEPS.length - 1 ? "Done" : "Next"}</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
