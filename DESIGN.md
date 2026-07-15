# DESIGN.md — resume-git

Visual system for resume-git. Documents the current, shipped design (the source of truth is `frontend/src/styles.css`). Register: **product**. Feel: GitHub structure + Claude calm. Follows the [design.md](https://raw.githubusercontent.com/google-labs-code/design.md/main/docs/spec.md) spirit.

## Theme

Dual light/dark, GitHub-flavored. Dark is the default; the viewer's `prefers-color-scheme` and an explicit `data-theme="light|dark"` on `:root` both switch it. Neutral developer surfaces carry the UI; meaning-bearing hues (green/purple/blue) are used sparingly for state.

## Color

Tokens are CSS custom properties in `:root` (dark) with light overrides. Format below: `token — dark / light`.

**Surfaces**
- `--bg` #0d1117 / #ffffff — app background
- `--panel` #161b22 / #f6f8fa — panels, cards, composer
- `--panel-2` #21262d / #f3f4f6 — second layer: sidebars, user chat bubble, hover

**Lines**
- `--border` #30363d / #d0d7de — default hairline
- `--border-strong` #444c56 / #afb8c1 — emphasized dividers

**Text** (contrast-checked ≥ 4.5:1 for body on its surface)
- `--text` #e6edf3 / #1f2328 — primary / prose
- `--muted` #8b949e / #59636e — secondary, labels, tool-step metadata
- `--faint` #6e7681 / #818b98 — chrome-only micro-labels (never body copy; fails AA on white)

**Meaning (semantic, not decorative)**
- `--accent` #58a6ff / #0969da — primary actions, selection, focus, `modified`
- `--commit` #3fb950 / #1a7f37 — base / `main` line, HEAD, `added`
- `--branch` #d2a8ff / #8250df — tailored branches
- `--active` #f78166 / #fd8c73 — active-tab underline
- `--add` = commit-green · `--del` / `--danger` #f85149 / #cf222e — diff + destructive
- `--green-btn` #238636 / #1f883d (hover #2ea043 / #1a7f37) — primary/commit buttons

**Color strategy:** Restrained. Neutral surfaces + one accent. Green/purple/blue each map to a fixed concept (base, branch, selection); never introduce a hue as decoration.

## Typography

One system sans for all UI; one mono for code, refs, data, and command tokens. No display/body pairing (product register).

- **Sans:** `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Mono (`--mono`):** `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`
- **Scale (fixed rem/px, not fluid):** body 13px; chat prose 14px / line-height 1.65; labels 11–12px; version refs, branch names, thread keys, `/skill` tokens, diffs → mono.
- Prose line length is naturally bounded by the narrow assistant column; wide data (diffs, tables) may run denser.

## Radius, elevation, motion

- `--radius: 6px` base. Inputs/cards 6–12px; composer & proposal/action cards 12–16px; pills/tags fully round. **No 24px+ rounding on cards.**
- Elevation is restrained: hairline borders do most of the work. Soft shadow only on floating menus (the `/` skill menu). Never pair a 1px border with a wide drop shadow as decoration.
- Motion 150–250ms, ease-out; conveys state only (message entrance fade/slide, focus ring, streaming). Every animation has a `prefers-reduced-motion: reduce` fallback. No page-load choreography.

## Components

Standardized vocabulary across surfaces:

- **Buttons:** default (panel-2 + border), `.primary`/`.green` (commit-green, primary actions), `.accent` (blue). One shape everywhere; `:hover`/`:disabled` defined.
- **App shell:** top appbar (wordmark + branch-pill + HEAD badge), tabbed nav with `--active` underline, collapsible history rail.
- **Branch pill / HEAD badge:** mono, `.on-main` green / `.on-branch` purple. (Modifier classes are namespaced — never bare `main`/`branch`.)
- **History rail & network graph:** dot = commit (green) / branch (purple) / HEAD (ringed); GitLens-style per-row graph.
- **Workbench:** draggable panes (editor · live PDF preview · assistant), persisted widths, commit bar.
- **Assistant (reference surface):** assistant turns render as **prose in the column, no box**; user turns get a **quiet neutral bubble** (`--panel-2`, not a saturated fill); one **rounded composer** with the send tucked inside + focus ring; tool-steps are muted mono metadata (no glyph marker — color carries it); **proposals are a flat reviewable list** (section rows with a hairline divider, quiet colored `ADDED/REMOVED/MODIFIED` labels — not filled pills); **action cards** are inline permission prompts.
- **Diff view:** monospace, `add`/`del`/`hunk`/`ctx` tinted by semantic tokens.

## Layout

- Structural responsiveness, not fluid type: the history rail overlays under ~820px; the workbench collapses to a single pane with an Editor/Preview/Assistant segmented toggle under ~900px; draggable pane widths on wide screens only.
- Generous padding in the assistant stream (breathing room is a stated value); denser where data warrants (diffs, forms).

## Bans (project-specific, on top of the shared product bans)

- No saturated accent-fill chat bubbles, gradient text, glassmorphism, or emoji decoration (the "AI-slop" anti-reference).
- No bare generic class names that collide with layout (`.main`, `.branch`) — namespace modifiers (`.on-main`).
- No side-stripe accent borders, nested cards, or 24px+ card rounding.
