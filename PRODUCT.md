# PRODUCT.md — resume-git

## Register

**Product** (design serves the product). resume-git is a tool: an authenticated app where the user is in a task, editing and compiling a résumé with an AI. It now has a public **landing page**, which is a genuine marketing surface that introduces the product to newcomers; the app behind it stays a focused workspace, not a marketing dashboard. It assumes no prior context: someone new should get it in about a minute, and someone fluent in Git and AI chat should trust it immediately.

## What it is

**An AI edits your résumé; version control keeps every version.** You ask in plain English and the AI tailors, tightens, or updates your résumé for you. The résumé is stored as structured **JSON**, which is what lets the AI make precise, reviewable, reversible edits: every change is a diff you approve, on a version you can restore, with your original never overwritten. A single-page LaTeX template compiles the JSON to a PDF on demand. Under the hood the app uses a Git-style model (immutable versions, branches for job-tailored copies, diffs, checkout/restore, a network graph of history); outward-facing copy leans on plain version-control language rather than Git jargon. Two ways to run the AI: the in-app **Claude assistant** (git-aware, reads history and proposes changes with confirmation, powered by a connected API key or OAuth token), or a keyless **copy-paste** path that works with any AI chat.

## Users & purpose

- **Who:** anyone, with a genuine target of CS and early-career software applicants (the output is the canonical single-page CS/SWE LaTeX résumé). Git literacy is a tailwind, not a requirement: the app teaches the model as you go, and non-technical users can rely entirely on the AI.
- **Context:** preparing and tailoring résumés for specific job applications, iterating over time without losing history.
- **Job to be done:** keep one strong résumé, let the AI tailor a copy per job, review the change, compile to PDF, all non-destructively.
- **Primary task per screen:** the Edit workbench (edit, live PDF preview, commit) with the AI assistant alongside is the center of gravity; history/compare/network are for orientation and review.

## Brand personality

**A deliberate blend of GitHub and Claude:** GitHub's *structure* (repo/branches/commits, neutral developer palette, git vocabulary) carried with Claude's *calm* (restraint, generous space, content over chrome, prose over boxes). Precise, quiet, trustworthy: a serious developer tool that never shouts.

The living reference for the feel is the app itself as it stands, especially the redesigned assistant panel (assistant replies as prose, quiet neutral user bubbles, one composer, flat reviewable proposals).

## Anti-references (explicitly NOT)

All four were rejected outright:

- **AI-slop / over-decorated** — no saturated accent-fill chat bubbles, gradient text, glassmorphism, emoji spray, or the generic "an AI made this" look. This is the primary thing to avoid; it has come up repeatedly.
- **Corporate SaaS** — no navy-and-gradient marketing-dashboard energy, hero-metric templates, or stocky impersonal chrome.
- **Playful / cutesy** — no rounded-everything, mascots, hand-drawn/doodle SVGs, or informal tone. Wrong register for a résumé tool.
- **Dense / cluttered** — no cramped enterprise-dashboard density. Breathing room wins.

## Strategic design principles

1. **The tool disappears into the task.** Familiar, standard affordances; no invented controls for standard jobs.
2. **Content over chrome.** Résumé content and the user's own writing lead; UI recedes. Prose beats boxes.
3. **Restraint by default.** One neutral surface system + a single accent for actions/selection/state. Color is meaning (green = base/main, purple = branch, blue = accent/selection), never decoration.
4. **Git fluency is the metaphor, not a costume.** Branches/commits/diffs mean what a developer expects; don't stretch the metaphor past where it informs.
5. **Honesty is a product value.** The assistant never fabricates résumé content, and writes never happen without explicit user confirmation — this shows up directly in UX copy and flows.
6. **Consistency over surprise.** Same button shape, form vocabulary, and icon style across every surface; delight is reserved for moments, not pages.

## Accessibility

- Theme-aware **light and dark**, driven by `data-theme` / `prefers-color-scheme`.
- **WCAG AA** contrast: body text ≥ 4.5:1, large/secondary text ≥ 3:1; verified when tuning muted/faint tokens.
- **Reduced motion** honored — every animation has a `prefers-reduced-motion: reduce` fallback; motion conveys state (streaming, entrance, focus), never decoration.
- Keyboard-reachable controls; visible focus rings on inputs and the composer.
