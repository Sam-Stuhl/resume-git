# New-User Journey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the new-user journey: a public landing page, a direct-to-Google sign-in, and a two-question onboarding funnel that routes to the in-app assistant or a keyless copy-paste prompt.

**Architecture:** Frontend is React+Vite+TS (`frontend/src`); backend is FastAPI (`api/`) reusing pure `core/`. Copy-paste prompts live in `core/prompts.py`. Onboarding gates in `frontend/src/App.tsx`. The design and final copy are fixed by the spec (`docs/superpowers/specs/2026-07-17-new-user-journey-design.md`) and two approved demos, which are the source of truth for layout and copy.

**Tech Stack:** FastAPI, SQLAlchemy async, React 18, Vite, TypeScript, CSS custom properties in `frontend/src/styles.css`.

## Global Constraints

- **No em dashes anywhere** (UI copy, comments, docs, commits). Use colon, period, parentheses, or "to".
- **Keyless copy-paste copy stays AI-chat-agnostic** (do not name Claude in the copy-paste path). Naming Claude is allowed only on the in-app credential path.
- **Reuse the shipped design tokens** in `frontend/src/styles.css` (GitHub dark/light, `--accent`/`--commit`/`--branch`, system sans + mono). No webfonts, gradients, or glassmorphism.
- **Outward copy leans version-control, not Git** (versions/history/tailored copies, not commit/branch/diff). Keep the `resume-git` name and mark. Do not rename in-app Git UI.
- **Verify:** backend `pytest`; frontend `cd frontend && npx tsc --noEmit && npx vite build`; drive the app in a browser for UI.
- **Branch:** all work on `new-user-journey` off `main`. Commit change by change. Do not push or touch `main` without asking.

---

## Phase 1: Backend, build-from-scratch prompt

### Task 1: Add a build-from-scratch onboarding prompt and endpoint

**Files:**
- Modify: `core/prompts.py` (add `ONBOARDING_BUILD_PROMPT` next to `ONBOARDING_PROMPT`)
- Modify: `api/routes.py:531` area (add `GET /api/prompts/onboarding-build` next to `prompt_onboarding`)
- Test: `tests/test_prompts.py` (create if absent; otherwise add to the existing prompts test module)

**Interfaces:**
- Produces: `core.prompts.ONBOARDING_BUILD_PROMPT: str`; route `GET /api/prompts/onboarding-build -> {"prompt": str}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_prompts.py
from core.prompts import ONBOARDING_BUILD_PROMPT, ONBOARDING_PROMPT

def test_build_prompt_exists_and_is_from_scratch():
    p = ONBOARDING_BUILD_PROMPT
    assert isinstance(p, str) and len(p) > 200
    # Interviews the user rather than converting an attached resume.
    assert "interview" in p.lower() or "ask me" in p.lower()
    # Same strict JSON schema contract as the convert prompt.
    assert '"personal"' in p and '"sections"' not in p  # schema uses experience/projects/... like ONBOARDING_PROMPT
    assert "Return ONLY" in p or "return only" in p.lower()
    # No em dashes anywhere in product copy (u2014 = em dash).
    assert "\u2014" not in p

def test_build_prompt_is_chat_agnostic():
    assert "Claude" not in ONBOARDING_BUILD_PROMPT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_prompts.py -v`
Expected: FAIL with ImportError (ONBOARDING_BUILD_PROMPT not defined).

- [ ] **Step 3: Implement the prompt**

Add to `core/prompts.py`, mirroring `ONBOARDING_PROMPT`'s schema block verbatim but with an interview intro. Key requirements: does NOT reference an attached resume; asks about education, experience, projects, skills one topic at a time; ends by returning ONLY the JSON in the same schema; ASCII punctuation only (rule 5 of the convert prompt); no "Claude".

```python
ONBOARDING_BUILD_PROMPT = """\
You are helping me build a resume from scratch as structured JSON for resume-git, a resume version-control app. I do not have a resume yet.

Interview me one topic at a time: education, work or internship experience, projects, and skills. Ask short, specific questions (including for measurable numbers), and do not invent anything I did not tell you. When we have enough, return ONLY the JSON in the schema below. No commentary, no code fences. Start with `{` and end with `}`.

REQUIRED SCHEMA:
<copy the exact schema block and CONVERSION RULES 1-9 from ONBOARDING_PROMPT>
"""
```

(Implementer: copy the `REQUIRED SCHEMA` block and rules 1 to 9 verbatim from `ONBOARDING_PROMPT` so both prompts produce identical shapes.)

- [ ] **Step 4: Add the endpoint**

In `api/routes.py`, next to `prompt_onboarding` (around line 531):

```python
@router.get("/prompts/onboarding-build")
async def prompt_onboarding_build():
    from core.prompts import ONBOARDING_BUILD_PROMPT
    return {"prompt": ONBOARDING_BUILD_PROMPT}
```

(Match the existing import/return style of `prompt_onboarding`.)

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_prompts.py -v`
Expected: PASS.

- [ ] **Step 6: Add a route test**

```python
# tests/test_routes_prompts.py (or extend existing route tests)
def test_onboarding_build_route(client):
    r = client.get("/api/prompts/onboarding-build")
    assert r.status_code == 200
    assert "prompt" in r.json() and len(r.json()["prompt"]) > 200
```

Run: `.venv/bin/pytest -k onboarding_build -v`
Expected: PASS. (Use the existing test client fixture; check `tests/` for its name.)

- [ ] **Step 7: Commit**

```bash
git add core/prompts.py api/routes.py tests/
git commit -m "feat: add build-from-scratch onboarding prompt and endpoint"
```

### Task 2: Add the client method

**Files:**
- Modify: `frontend/src/api.ts:116` (next to `onboardingPrompt`)

- [ ] **Step 1: Add method**

```ts
onboardingBuildPrompt: () => req<{ prompt: string }>("/api/prompts/onboarding-build"),
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: add onboardingBuildPrompt client method"
```

---

## Phase 2: Landing page

### Task 3: Landing component and styles

**Files:**
- Create: `frontend/src/components/Landing.tsx`
- Modify: `frontend/src/styles.css` (append a `/* Landing */` section)

**Interfaces:**
- Produces: `export function Landing(): JSX.Element`. Self-contained; the only interactive elements are anchors to `GOOGLE_LOGIN_URL` (import from `../api`) and an in-page `#how` anchor.

- [ ] **Step 1: Build the component**

Port the approved landing demo (source of truth: `scratchpad/landing-demo.html`, published at the artifact URL in the spec). Structure: nav, hero (headline "AI edits your resume. You keep every version.", subhead, `Continue with Google` -> `GOOGLE_LOGIN_URL`, `How it works` -> `#how`, fine print "Works with any AI chat. No key required.", and the assistant "ask -> propose -> approve" card), `#how` 3-step section using real screenshots from `docs/img/` (import as Vite assets: `import appShot from "../../docs/img/app.webp"` etc, or copy the four images into `frontend/public/` and reference by path), the 5-item feature strip (Structured data (JSON) / Bring your own AI / You approve everything / Live PDF / Full history), the who-it's-for section, and the final CTA + footer. Use the exact copy from the demo. Reuse `styles.css` tokens; add landing-scoped classes.

- [ ] **Step 2: Wire screenshots**

Copy `docs/img/{app.webp,assistant.png,compare.png,network.png}` into `frontend/public/landing/` and reference as `/landing/app.webp` etc, so `vite build` bundles them.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx tsc --noEmit && npx vite build`
Expected: builds clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Landing.tsx frontend/src/styles.css frontend/public/landing
git commit -m "feat: add public landing page component"
```

### Task 4: Show the landing to logged-out visitors

**Files:**
- Modify: `frontend/src/App.tsx:125` (the `if (needAuth) return <AuthScreen .../>` line) and imports.

**Interfaces:**
- Consumes: `Landing` from Task 3.

- [ ] **Step 1: Swap the gate**

Replace the logged-out short-circuit so a 401 renders `<Landing />` instead of `<AuthScreen>`. Keep `AuthScreen` only for the `?auth=failed` case:

```tsx
if (needAuth) {
  const failed = new URLSearchParams(window.location.search).get("auth") === "failed";
  return failed ? <AuthScreen failed /> : <Landing />;
}
```

- [ ] **Step 2: Verify in the browser**

Run the app (see project run steps). Confirm: visiting logged-out shows the landing; `Continue with Google` navigates to Google; `?auth=failed` shows the fallback.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: serve landing page to logged-out visitors"
```

### Task 5: Reduce AuthScreen to the failed-sign-in fallback

**Files:**
- Modify: `frontend/src/components/AuthScreen.tsx`

- [ ] **Step 1: Trim copy**

Remove the Git-jargon product pitch. Keep: wordmark, a single line "Sign-in didn't complete. Please try again." (only meaningful in the `failed` case now), and `Continue with Google`. Keep the privacy line optional. No em dashes.

- [ ] **Step 2: Verify build + commit**

```bash
cd frontend && npx tsc --noEmit && npx vite build
git add frontend/src/components/AuthScreen.tsx
git commit -m "refactor: reduce AuthScreen to failed-sign-in fallback"
```

---

## Phase 3: Onboarding funnel

### Task 6: Onboarding funnel state machine and Q1/Q2 screens

**Files:**
- Create: `frontend/src/components/onboarding/OnboardingFlow.tsx` (new funnel; replaces `OnboardingWizard`)
- Modify: `frontend/src/App.tsx` (render `OnboardingFlow` where `OnboardingWizard` was, lines 186-190)
- Keep `frontend/src/components/OnboardingWizard.tsx` until Task 9 removes it.

**Interfaces:**
- Produces: `export function OnboardingFlow(props: { onFinish: (createdVersion?: number) => void; onStartBlank: () => void; onOpenAssistant: (initialInput: string) => void; })`.
- State: `has: boolean | null`, `ai: "pro" | "api" | "none" | null`. Screens: q1, q2, connect, chat-handoff, copypaste, manual. Port structure/copy from the approved onboarding demo (`scratchpad/onboarding-demo.html`).

- [ ] **Step 1: Build Q1 + Q2 + crumbs**

Q1 "Do you already have a resume?" with two option cards (Yes / No) and a quiet "I'll fill it in myself" link calling `onStartBlank`. Q2 "How do you want to use the AI?" with three cards (Claude Pro or Max / Anthropic API key / None of these) and a Back link. Use exact demo copy including the `claude setup-token` and `sk-ant-*` code chips. Add onboarding-scoped CSS to `styles.css`.

- [ ] **Step 2: Wire into App**

In `App.tsx`, replace `<OnboardingWizard .../>` with `<OnboardingFlow onFinish=... onStartBlank=... onOpenAssistant=... />`. `onOpenAssistant` is defined in Task 8.

- [ ] **Step 3: Verify build + drive Q1/Q2 in browser**

Run: `cd frontend && npx tsc --noEmit && npx vite build`; then in the app, create/log in as an empty account and confirm Q1 -> Q2 navigation and Back work.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/onboarding/OnboardingFlow.tsx frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: onboarding funnel Q1/Q2 screens"
```

### Task 7: Keyless copy-paste route (convert + build)

**Files:**
- Modify: `frontend/src/components/onboarding/OnboardingFlow.tsx`

**Interfaces:**
- Consumes: `api.onboardingPrompt` (convert), `api.onboardingBuildPrompt` (build, Task 2), `api.pastePreview(text, "base-update")`, `api.createBase(data, "Base")`.

- [ ] **Step 1: Build the copypaste screen**

When `ai === "none"`: fetch the convert prompt if `has`, else the build prompt. Show: title "Copy this into any AI chat"; lead per demo (convert lead includes "attach your resume (any file your AI accepts)"; build lead says answer its questions); a read-only prompt box with a Copy button; a paste-back textarea (placeholder "Paste whatever the AI sent back"); a softened-JSON hint ("Paste the whole reply, even if it looks like code. We'll turn it into a clean resume and show you a friendly summary before anything is saved."); a Review button calling `pastePreview(pasted, "base-update")`, then a summary (reuse `DiffView` `Summary`), then "Use as my resume" calling `createBase(preview.data, "Base")` then `onFinish(v)`. Keep it AI-chat-agnostic (no "Claude").

- [ ] **Step 2: Verify build + drive keyless convert end to end**

Run typecheck/build. In the browser, walk Yes -> None: copy prompt, run it in any chat, paste a valid resume JSON back, review, and confirm a first version is created and the app leaves onboarding.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/onboarding/OnboardingFlow.tsx
git commit -m "feat: keyless copy-paste onboarding route (convert + build)"
```

### Task 8: Connect step + preloaded assistant handoff

**Files:**
- Modify: `frontend/src/components/onboarding/OnboardingFlow.tsx` (connect screen)
- Modify: `frontend/src/components/ChatPanel.tsx` (accept an initial composer value)
- Modify: `frontend/src/components/Workbench.tsx` (accept a pending prompt: force chat open + pass to ChatPanel)
- Modify: `frontend/src/App.tsx` (hold `pendingChatPrompt`, pass to Workbench, define `onOpenAssistant`)

**Interfaces:**
- Produces: `ChatPanel` gains optional prop `initialInput?: string` (seed `input` state once on mount when non-empty). `Workbench` gains optional prop `initialChatInput?: string` (when set, force `chatOpen`/`pane="chat"` and pass to `ChatPanel`). `App` holds `const [pendingChatPrompt, setPendingChatPrompt] = useState<string | null>(null)`; `onOpenAssistant(text)` sets it and dismisses the wizard.

- [ ] **Step 1: ChatPanel initialInput**

Add `initialInput` to `ChatPanel` props and seed it once:

```tsx
// in the props destructure add: initialInput
useEffect(() => { if (initialInput) setInput(initialInput); /* eslint-disable-next-line */ }, []);
```

- [ ] **Step 2: Thread it through Workbench and App**

In `Workbench`, add `initialChatInput?: string`; when present, initialize `chatOpen` true and `pane` "chat", and pass `initialInput={initialChatInput}` to `ChatPanel`. In `App`, add `pendingChatPrompt` state, pass it as `initialChatInput` to `<Workbench>`, and define `onOpenAssistant(text)` to `setWizardDismissed(true); setPendingChatPrompt(text); setView("edit");`.

- [ ] **Step 3: Connect screen**

When `ai === "pro" | "api"`: show the connect screen (title/instructions per demo, `sk-ant-oat`/`sk-ant-api` chips), a password field, and "Connect and open the assistant" calling `api.saveApiKey(key)` then `onMeChanged`-equivalent refresh, then `onOpenAssistant(preloadText)`. `preloadText` is the convert message ("Here's my resume:\n\n[paste it here]") if `has`, else the build message ("Yes, let's start. Ask me your first question."). After connect, the empty account still has no version, so the wizard must not re-trigger: rely on `wizardDismissed` set by `onOpenAssistant`.

- [ ] **Step 4: Verify in the browser (connected path)**

With a real credential, walk Yes -> Claude Pro (or API key): paste a credential, confirm the assistant opens with the composer prefilled, send a resume, and confirm the assistant proposes a first version that applies as version 1. If the agent cannot create a first base on an empty account, fix `core/agent.py`/`core/tools.py` so `propose_resume` works with an empty baseline (add a focused test in `tests/`), then re-verify.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatPanel.tsx frontend/src/components/Workbench.tsx frontend/src/components/onboarding/OnboardingFlow.tsx frontend/src/App.tsx
git commit -m "feat: connect credential and hand off to a preloaded assistant chat"
```

### Task 9: Remove the old wizard and CLI-import onboarding route

**Files:**
- Delete: `frontend/src/components/OnboardingWizard.tsx`
- Verify no remaining imports of it.

- [ ] **Step 1: Delete and check references**

Run: `grep -rn "OnboardingWizard" frontend/src` -> expect no results after removing the import in `App.tsx` (done in Task 6).

- [ ] **Step 2: Verify build + commit**

```bash
cd frontend && npx tsc --noEmit && npx vite build
git rm frontend/src/components/OnboardingWizard.tsx
git commit -m "chore: remove superseded onboarding wizard"
```

---

## Phase 4: Entry copy and docs

### Task 10: Empty-state copy

**Files:**
- Modify: `frontend/src/App.tsx:156` (sidebar empty text)

- [ ] **Step 1: Revoice**

Change "No commits yet. Add your resume on the Edit tab, or import from the CLI." to "No versions yet. Add your resume on the Edit tab to get started."

- [ ] **Step 2: Verify build + commit**

```bash
cd frontend && npx tsc --noEmit && npx vite build
git add frontend/src/App.tsx
git commit -m "copy: revoice empty-state sidebar text"
```

### Task 11: Update PRODUCT.md positioning

**Files:**
- Modify: `PRODUCT.md`

- [ ] **Step 1: Rewrite Register/Users/Personality**

Update to: audience is anyone, targeting CS students (not a closed circle); it IS now a marketing surface (there is a public landing); AI-first framing (the assistant editing your resume is the primary job, version control is the trust layer). Keep the anti-references and design principles. No em dashes.

- [ ] **Step 2: Commit**

```bash
git add PRODUCT.md
git commit -m "docs: update PRODUCT.md for public, AI-first positioning"
```

---

## Final verification

- [ ] `.venv/bin/pytest` all green.
- [ ] `cd frontend && npx tsc --noEmit && npx vite build` clean.
- [ ] Browser walk of the full journey: logged-out landing -> Continue with Google -> Q1 -> Q2, exercising at least (a) Yes + None keyless convert to a created first version, and (b) Yes + Claude Pro/API connected chat to a created first version, plus the "I'll fill it in myself" manual escape.

## Self-review notes

- Spec coverage: landing (T3-4), sign-in direct + fallback (T4-5), onboarding funnel + routes + manual escape (T6-8), keyless attach + softened JSON (T7), build-from-scratch prompt (T1-2), preloaded chat + first-base verify (T8), entry copy (T10), PRODUCT.md (T11). Out-of-scope items (in-app Git rename, CLI import route removal is in T9, MAX_USERS raw-403) are respected.
- The two capabilities flagged in the spec are handled: build prompt (T1), first-resume-by-assistant (T8 step 4, with a fix path if needed).
- UI tasks intentionally reference the approved demos for verbatim markup/copy rather than reproducing hundreds of lines of JSX here; the demos are the fixed source of truth and the copy strings are quoted in-task.
