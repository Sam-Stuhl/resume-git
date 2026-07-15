# Working agreements for this repo

## Commit discipline

**Commit change by change — not one big commit at the end.** As you implement,
commit each logical, self-contained change on its own (a bug fix, one endpoint, a
component, a settings module) with a clear message, rather than batching an entire
feature into a single commit. Each commit should leave the tree in a coherent,
buildable state. Keep unrelated fixes in their own commits (e.g. a race-condition
fix separate from the feature that surfaced it).

Still commit/push only when asked, and branch off `main` for new work (never commit
straight to `main`).

## Writing style

**Never use em dashes anywhere.** Not in UI copy, code comments, prompts, docs, or
commit messages. Use a colon, a period, parentheses, or "to" (for ranges) instead.

Copy-paste prompt flows (onboarding "Paste & convert", the keyless assistant) must
stay AI-chat-agnostic. Don't name Claude in that UI, since the user pastes the prompt
into whatever chat they use. Only the in-app credential/API path is Claude-specific
(Settings, "connect a key"), because the API only supports Claude.

## Verify before handing off

Run `pytest` and the frontend `tsc --noEmit` + `vite build` before calling work
done. Drive the real app in a browser for UI changes. Don't claim success without
the evidence.
