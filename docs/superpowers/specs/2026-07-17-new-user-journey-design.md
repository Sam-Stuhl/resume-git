# New-user journey: landing, sign-in, and onboarding

Design spec. Date: 2026-07-17. Status: approved in brainstorm, pending spec review.

Covers the full first-time-user path for resume-git: a public landing page, the
sign-in handoff, and a redesigned onboarding funnel, plus the small entry-copy
cleanups those touch. Two interactive demos are the visual source of truth:

- Landing: https://claude.ai/code/artifact/0b231ea3-4a9d-4bba-a914-1279597ab390
- Onboarding: https://claude.ai/code/artifact/5507e98c-68f7-41f7-8b8d-feecca0624fb

## Why

Today a logged-out visitor is pushed straight to a one-sentence, Git-jargon
sign-in card (`AuthScreen`), and a signed-in first-timer lands in a 3-route
wizard led by version-control language. There is no page that explains the
product from zero, and the copy assumes Git fluency. We want anyone with no
context to: get a quick overview, make an account, and set up their first
resume (from scratch or from an existing one).

## Audience and positioning (the through-line)

The product is for **anyone**, with a genuine target of **CS students** (the
output is the canonical single-page CS/SWE LaTeX resume). Git literacy helps but
is not required.

The core thesis, which had drifted during development and is now restored: **the
AI does the resume edits for you.** The resume is stored as structured JSON so
the AI can operate on it precisely; the version-control model is the trust layer
that makes AI edits safe (precise, reviewable, reversible, never destructive).

Voice principles for every new-user surface:

1. **AI-first, but balanced.** The AI editing your resume and keeping every
   version are co-equal pillars. AI is the protagonist; version history is why
   you can trust it.
2. **Structured data (JSON) is the "why it works," stated plainly.** It is the
   reason the AI edits precisely instead of handing you text to paste.
3. **Lean into version control, less Git.** Outward copy uses versions /
   history / tailored copies, not commit / branch / diff. The `resume-git` name
   and mark stay. (This does not rename the in-app Git UI: see Out of scope.)
4. **De-jargoned and terse.** No `base`, `diff`, `experience[0]`, `CLI`. Plain,
   confident, developer-toned copy. It must not read as AI-generated marketing.
5. **Keyless-or-connect, both first-class.** Use any AI chat with no key, or
   connect a Claude API key / OAuth token for the in-app assistant.
6. **Honesty rails, kept visible.** The AI never invents experience and never
   writes without confirmation.

**PRODUCT.md must be updated** to reflect the audience shift (away from "a small,
closed circle of friends... not a marketing surface") and the AI-first framing
(today it leads with "version control for a resume" and treats the assistant as
a helper).

## Visual system

All new surfaces reuse the shipped design tokens in `frontend/src/styles.css`
(GitHub dark default + light, blue accent, commit-green, branch-purple, system
sans + mono). No marketing webfont, no gradients, no glassmorphism: the "AI-slop
/ corporate-SaaS" anti-references in PRODUCT.md still hold. The landing's one
distinctive device is a live assistant "ask -> propose -> approve" card; the
onboarding is a calm centered card matching the existing wizard.

## Surface 1: Landing page

**Route/behavior.** Served at `/` for logged-out visitors (the SPA already
serves at every path; the app currently short-circuits a 401 straight to
`AuthScreen`). Instead, a logged-out visitor sees the landing. A signed-in
visitor boots into the app as today. `Continue with Google` triggers OAuth
directly (see Surface 2).

**Sections (top to bottom):**

1. **Nav.** `resume-git` wordmark + mark, `How it works` anchor, `Continue with
   Google`.
2. **Hero.** Headline: "AI edits your resume. You keep every version." Subhead:
   "Ask for changes in plain English, see exactly what changed, and compile a
   clean PDF. Your original is never overwritten." Primary CTA + `How it works`.
   Fine print: "Works with any AI chat. No key required." Right side: the live
   assistant card (user asks, assistant proposes a modified/added change list
   plus a before/after line, Approve / Discard, "Nothing is saved until you
   approve").
3. **How it works.** One line naming the substrate ("Under the hood your resume
   is **structured data (JSON)**, so the assistant edits it precisely, field by
   field, instead of handing you text to copy-paste back. Every change is easy
   to review."). Three steps down a spine, each with a real screenshot from
   `docs/img/`: 01 Ask (`assistant.png`) -> 02 Review the changes
   (`compare.png`) -> 03 Save it, get the PDF (`app.webp`).
4. **Feature strip (5).** Structured data (JSON); Bring your own AI (any chat
   with no key, or connect a Claude API key / OAuth token); You approve
   everything; Live PDF; Full history.
5. **Who it's for.** "CS students first. Anyone, really." Describes the
   single-page LaTeX resume format by its properties (no "Jake" name-drop), and
   frames version control in plain terms.
6. **Final CTA + footer.**

The final landing copy lives in the demo and in the Copy appendix below.

## Surface 2: Sign-in

`Continue with Google` on the landing navigates directly to
`/api/auth/google/login` (existing OAuth). There is no separate happy-path
sign-in screen. `AuthScreen` shrinks to the failed-sign-in fallback only
(`?auth=failed`): wordmark, "Sign-in didn't complete. Please try again.",
`Continue with Google`. Its current Git-jargon product pitch is removed (the
landing does that job now).

`MAX_USERS` stays as-is (default 0 = uncapped). Note a known rough edge for the
plan to optionally address: when the cap is hit, the 403 surfaces raw inside the
OAuth callback rather than redirecting to a friendly message
(`api/auth.py` `resolve_or_create_user` raises; `google_callback` does not
catch it). Out of scope unless we choose to include it.

## Surface 3: Onboarding funnel (redesigned)

Replaces the current 3-route wizard (`OnboardingWizard`: welcome -> base ->
"Connect Claude (optional)"). A brand-new signed-in account with no versions
enters a two-question funnel that always ends with the AI doing the work.

**Q1: "Do you already have a resume?"**
- *Yes, I have a resume* -> convert path (the prompt/chat turns it into the
  first version).
- *No, start fresh* -> build path (the assistant builds one via interview).
- Quiet secondary link: **"I'll fill it in myself"** -> blank editor (the manual
  escape). This is the only non-AI route in onboarding.

**Q2: "How do you want to use the AI?"** (asked regardless of Q1)
- *Claude Pro or Max* -> connect an `sk-ant-oat` login token from
  `claude setup-token` (bills the subscription).
- *Anthropic API key* -> connect an `sk-ant-api` key (bills API credits).
- *None of these* -> keyless copy-paste path.

**Routing (the 2x3 outcome):**

| | Have a resume (convert) | Start fresh (build) |
|---|---|---|
| Claude Pro | connect token -> in-app chat, preloaded convert prompt | connect token -> in-app chat, preloaded build prompt |
| API key | connect key -> in-app chat, preloaded convert prompt | connect key -> in-app chat, preloaded build prompt |
| None | copy-paste convert prompt, paste reply back | copy-paste build prompt, paste reply back |

Q2 chooses the mechanism (connected in-app chat vs keyless copy-paste); Q1
chooses the prompt content (convert vs build).

**Connect step (Pro / API key).** One password field; the paste is saved via the
existing `PUT /api/settings/api-key` (`saveApiKey`), which stores whatever is
pasted; `_credential_kind` detects `sk-ant-oat` vs `sk-ant-api` by prefix. On
save, open the in-app assistant preloaded with the first message.

**Preloaded chat.** The assistant opens with a short greeting and the composer
prefilled:
- Convert: greeting asks the user to paste their resume; on send the assistant
  proposes the first version for review.
- Build: greeting says it will interview them; composer prefilled with a "yes,
  start" message; the assistant asks questions and proposes the first version.

**Keyless copy-paste.** Mirrors today's "Paste and convert":
- Convert: "Paste the prompt into any AI chat, **attach your resume** (any file
  your AI accepts), and send. Then paste the AI's reply back here." Uses the
  existing convert prompt (`/api/prompts/onboarding`), then
  `/api/paste/preview` -> `/api/base`.
- Build: a new build-from-scratch prompt the user runs in any chat; it interviews
  them and returns the resume, pasted back through the same preview -> base flow.
- **JSON is softened** everywhere the user reads it: "paste the AI's reply,"
  "paste whatever the AI sent back," and a reassurance that we turn it into a
  clean resume and show a friendly summary before anything is saved. The user
  never has to think about the word JSON.

## Surface 4: Entry copy cleanups

- **Empty sidebar:** "No commits yet. Add your resume on the Edit tab, or import
  from the CLI." -> "No versions yet. Add your resume on the Edit tab to get
  started."
- Onboarding and empty-state copy default to **"your resume"** (and "your main
  resume" where the one-canonical-source sense is needed) rather than "base".
  "base" remains in deeper app UI and is out of scope here.
- `import from the CLI` is removed from onboarding. CLI import can remain
  available elsewhere (e.g. Settings) but is not a first-run route.

## Capabilities to build or verify (do not assume)

1. **Build-from-scratch prompt.** Only a convert prompt exists today
   (`core/prompts.py` `ONBOARDING_PROMPT`). Add a build variant for both the
   keyless copy-paste path and the preloaded in-app chat. It interviews the user
   and returns the same JSON schema.
2. **First-resume creation by the assistant.** Confirm the in-app agent can
   create the *first* version on an empty account via `propose_resume` (convert
   from a pasted resume, or from an interview), and that the resulting proposal
   applies as version 1. `core/agent.py` / `core/tools.py` support propose today;
   the empty-account first-base case must be verified.
3. **Preloaded chat launch.** A way to open the assistant (today the third
   `Workbench` column, `ChatPanel`) directly from onboarding with the composer
   prefilled and, for the connected path, the credential already saved.
4. **Landing at `/` for logged-out.** Change the 401 short-circuit in
   `frontend/src/App.tsx` so logged-out visitors get the landing, not
   `AuthScreen`. `AuthScreen` becomes the `?auth=failed` fallback.
5. **Onboarding routing state.** The wizard needs to carry the Q1/Q2 answers and
   branch accordingly (new component or a rework of `OnboardingWizard`).

## Out of scope (explicitly)

- Renaming the in-app Git UI (branch pills, "New branch", Compare/diff, Network
  graph). The "less Git" rule applies to marketing/entry surfaces only.
- Reworking onboarding beyond this funnel, or a broader app-wide AI-first
  redesign past the entry surfaces.
- The `MAX_USERS`-hit raw-403 rough edge, unless we opt in.
- CLI import as an onboarding route.

## Verification

- `pytest` for any backend changes (new build prompt endpoint, any onboarding
  routing endpoints).
- Frontend `tsc --noEmit` + `vite build`.
- Drive the real app in a browser for each new-user surface: logged-out landing,
  Google sign-in, both onboarding questions, and at least the keyless-convert and
  one connected-chat route end to end. Confirm a first resume is actually created
  and a PDF compiles.

## Copy appendix

The authoritative copy is in the two demos. The strings there (hero, how-it-works,
feature strip, who-it's-for, the two onboarding questions, connect steps, chat
greetings, and the keyless copy-paste guidance) are the copy to implement.
