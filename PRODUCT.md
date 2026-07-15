# PRODUCT.md — resume-git

## Register

**Product** (design serves the product). resume-git is a tool: an authenticated app where the user is in a task — versioning, tailoring, and compiling a résumé. It is not a marketing surface. The bar is *earned familiarity*: someone fluent in Git, GitHub, and Claude should sit down and trust it immediately.

## What it is

Version control for a résumé. One canonical résumé is the source of truth; the app applies the Git mental model to it — **commits** (immutable versions), **branches** (job-tailored forks off the base line), **diffs**, **checkout/restore**, and a **network graph** of history. JSON is the source of truth; a Jake's-Résumé LaTeX template compiles it to a PDF on demand. A curated, streaming **Claude assistant** (git-aware: it can read history and propose changes / structural actions with confirmation) helps advise, tailor, ATS-audit, and update the baseline.

## Users & purpose

- **Who:** the owner plus a small, closed circle of friends — developer-literate, comfortable with Git. Not built to scale to strangers.
- **Context:** preparing and tailoring résumés for specific job applications, iterating over time without losing history.
- **Job to be done:** keep one strong baseline, branch/tailor per job, review the diff, compile to PDF, and get honest AI help — all non-destructively.
- **Primary task per screen:** the Edit workbench (edit → live PDF preview → commit) is the center of gravity; history/compare/network are for orientation and review.

## Brand personality

**A deliberate blend of GitHub and Claude:** GitHub's *structure* (repo/branches/commits, neutral developer palette, git vocabulary) carried with Claude's *calm* (restraint, generous space, content over chrome, prose over boxes). Precise, quiet, trustworthy — a serious developer tool that never shouts.

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
