# Resume Assistant v2 — an agentic, git-aware assistant with skills

**Date:** 2026-07-14
**Branch base:** `resume-copilot-chat` (current), targeting `main` after review.
**Status:** design approved in brainstorming; ready for an implementation plan.

## Context

The Resume Assistant (shipped on `resume-copilot-chat`) is a streaming advisor with a single
`propose_resume` tool: one model call, extract one proposed resume, review-diff-and-apply. The four
intents (`ask`, `ats`, `tailor`, `base-update`) live as sections of one monolithic system prompt
(`core/prompts.py:SESSION_PROMPT_TEMPLATE`), selected by a `[TAG]` the user types.

This design evolves it into **an agent that operates the resume repo like git**, with the four intents
restructured as **discoverable, self-describing skills** invoked via `/` commands. Concretely:

1. **Git-aware, agentic.** The assistant gets tools to *read* history (list versions, view one, diff two,
   current HEAD) and to *act* (create branch, commit, checkout, restore). It runs a real tool loop.
2. **`/commands` replace `[TAGS]`.** Typing `/` opens a menu of the four skills (each with a short
   description); plain typing still works and defaults to advisor mode.
3. **Skills, not prompt-sections.** Each intent becomes a small `{name, description, allowed_tools,
   instructions}` unit (SKILL.md-shaped) in a registry, so it is self-describing and extensible.

### Decisions locked in brainstorming
- **Git access = read + act (agentic tool loop).**
- **Writes confirm, reads auto.** Read/diff tools execute freely; every mutation is user-confirmed.
- **Own skill registry** over the streaming Messages API (not the Agent SDK) — identical model capability,
  keeps the working OAuth-token path, precise/safe tool surface, stateless-container friendly. Shaped like
  SKILL.md so it could port to real Skills later.
- **Free chat + `/` to focus.** Plain typing = advisor default; `/` selects a skill (loads its
  instructions + scopes its tools).
- **Writes end the turn** (confirm → REST executes → user sends another message to continue) — no
  mid-stream pause/resume machinery.
- **Per-skill tool scoping** (e.g. `/ats` is read-only; `/tailor` may branch).

## Architecture

### The agent loop (`core/agent.py`)
`stream_chat` becomes a bounded loop (safety cap ~8 iterations) over the streaming Messages API:

```
messages = replay_text(history) + [user_message]
tools    = skill.allowed_tools if skill else ALL_TOOLS   # advisor default = all; reads auto, writes confirm
system   = base_identity + git_tools_context + (skill.instructions or advisor_default) [+ CC identity if OAuth]

for _ in range(MAX_STEPS):
    stream one model call (system, messages, tools)      # emit ("delta", text) for text
    blocks = final message content
    reads  = [b for b in blocks if b.type=="tool_use" and b.name in READ_TOOLS]
    writes = [b for b in blocks if b.type=="tool_use" and (b.name in WRITE_TOOLS or b.name=="propose_resume")]

    if reads and not writes:
        for b in reads: result = dispatch_read(b); emit ("tool_step", {name, summary}); collect tool_result
        messages += [assistant(reads), user(tool_results)]     # continue loop
        continue
    if writes:
        for b in writes:
            if b.name == "propose_resume": emit ("proposal", package(b.input))   # content → diff/apply card
            else:                          emit ("action",   summarize(b))        # structural → confirm card
        break                                                  # writes end the turn
    break                                                       # end_turn, no tools

emit ("done", None)
persist(user, assistant_final_text, proposal_or_actions)
```

Notes:
- **Reads execute server-side and loop**; **writes never execute in the loop** — they surface as UI cards
  and the turn ends. This enforces "writes confirm" structurally.
- If a single response mixes reads and writes (rare), reads run and the loop continues; writes are only
  surfaced when a response has no reads. Keeps execution unambiguous.
- **Persistence:** we persist the final assistant text + a `proposal`/`actions` blob (thread history), and
  replay only **text** turns to the model on later turns (intermediate tool round-trips are ephemeral to the
  turn — each turn re-reads what it needs). Same replay rule as v1.
- Works on both credential kinds; the OAuth path keeps its Bearer + `oauth-2025-04-20` header + Claude Code
  identity first system block.

### Tools
| Tool | Kind | Executed by | Backed by |
|---|---|---|---|
| `list_versions` | read (auto) | server, in-loop | `db.repo.list_versions` + branch naming |
| `get_version(version)` | read (auto) | server, in-loop | `db.repo.get_version` + `core.sections.normalize` |
| `diff_versions(a, b)` | read (auto) | server, in-loop | `core.diff.summarize_changes` + `diff_lines` |
| `get_current()` | read (auto) | server, in-loop | `db.repo.current_version` |
| `propose_resume(resume, intent)` | content write | proposal card | existing diff→apply → **Apply to editor / Create branch** buttons |
| `checkout(version)` | structural write | confirm card | `PUT /api/versions/current` (`services.set_current`) |
| `restore(version)` | structural write | confirm card | `POST /api/versions/{v}/restore` (`services.restore`) |

**One content-write tool, not three.** `propose_resume` is the single content path — its existing card
already offers *Apply to editor* (→ commit on the current line) and *Create branch*, and the user's click
on those buttons **is** the confirmed write. So there is no separate `create_branch`/`commit` tool; that
would be a second way to do the same thing. The genuinely new writes are the **structural** ones —
`checkout` and `restore` — which carry no resume content and so get their own one-line confirm cards.

Read tools return compact JSON (never PDFs). `list_versions` includes `branch` (base commits → `main`,
else the label slug), `is_base`, `forked_from`, `is_head`. `get_version` truncates long bodies to the
fields that matter. All tools are scoped to the request user.

### Skill registry (`core/skills/`)
Each skill is a SKILL.md-shaped file `core/skills/<name>.md`:

```markdown
---
name: tailor
description: Adapt your resume to a specific job description and open it as a branch.
allowed_tools: [list_versions, get_version, diff_versions, propose_resume]
---
<tailoring instructions, lifted from today's SESSION_PROMPT_TEMPLATE [TAILOR] section>
```

`core/skills/__init__.py` loads all `*.md` at import into a registry `{name: Skill(name, description,
allowed_tools, instructions)}`. The four skills:

| Skill | Description (menu) | Allowed tools |
|---|---|---|
| `ask` | Get honest advice on your resume — no changes made. | reads only |
| `ats` | Audit a version against a job description before you submit. | reads only |
| `tailor` | Adapt your resume to a job and open it as a branch. | reads + `propose_resume` |
| `base-update` | Apply a real life change to your baseline resume. | reads + `propose_resume` |

Advisor default (no skill) = **all tools** — reads + `propose_resume` + the structural `checkout`/`restore`
(writes still confirm) — plus a base advisor instruction that lists the skills so the model can
suggest/infer intent. The structural git ops live in the advisor default (general repo navigation like
"check out my pre-NJIT resume"), not scoped into the four content-oriented skills.

The four instruction blocks are **moved out of** `core/prompts.py` into these files; `prompts.py` keeps the
identity/ATS-knowledge preamble that all skills share (`build_chat_system` composes: shared preamble +
skill instructions + git-tools context). The copy-paste CLI prompt path is left untouched.

## API changes (`api/`)
- `GET /api/skills` → `[{name, description}]` for the `/` menu (from the registry).
- `ChatSendIn` gains `skill: str | None` (the invoked skill name; validated against the registry).
- `POST /api/chat/{thread}` (SSE) gains new event types: `tool_step` and `action` (alongside existing
  `delta`, `proposal`, `error`, `done`). Read-tool dispatch lives in a new `core/tools.py` (pure functions
  taking `(session, user_id, args)`), called by the route's SSE generator (it already has the session).
- No new write endpoints — structural/content writes reuse `POST /api/tailor`, `/api/base`,
  `PUT /api/versions/current`, `POST /api/versions/{v}/restore`.

## Frontend (`frontend/src/`)
- **`/` skill menu** in `ChatPanel.tsx`: when the input starts with `/`, show a popup of skills
  (`api.skills()`) filtered by typed text; selecting sets the active skill (a chip on the input) and, for
  `tailor`/`ats`, hints for a JD. `chatStream` body gains `skill`.
- **Tool-step lines**: `tool_step` events render as muted `▸ read v0003`, `▸ diff main…notion` rows inside
  the streaming assistant bubble (transparency into what it read).
- **Confirm cards** (`action` events, structural only): a compact card — `Claude wants to checkout v0005
  (main)` — `[Confirm] [Cancel]`. Confirm calls the mapped `api.*` method (`setCurrent` / `restore`); on
  success show a result line. These are live only in-session; on reload they render as a static summary line
  (no re-exec) to avoid double-applying.
- **Proposal card** (`proposal`): unchanged from v1 (section accept → Apply to editor / Create branch).
- `types.ts`: `Skill`, `ToolStep`, `AgentAction` types; `ChatMessage.proposal` widened to also carry
  persisted actions summary.

## What's reused
Streaming SSE pipe, per-branch threads (`Message` table), OAuth/API-key detection, the whole
propose→apply→commit content flow, `db/repo`, `core/diff`, `core/schema`, `services.py`, and every REST
endpoint the writes call. The loop and skills are additive; no destructive migration.

## Testing
**Automated (extend the 29 passing tests):**
- `core/tools.py`: each read tool returns correct compact JSON for a seeded user (list/get/diff/current),
  scoped per user. `core/skills`: registry loads 4 skills with descriptions + valid `allowed_tools`.
- `core/agent.py` loop (fake `AsyncAnthropic`): (a) a read-tool response is executed and the loop continues
  then ends with text; (b) a `propose_resume` response ends the turn with a `proposal`; (c) a structural
  write (`checkout`) ends the turn with an `action`; (d) per-skill tool scoping — an `ats` turn is offered
  only read tools; (e) `MAX_STEPS` cap terminates a pathological read-only loop.
- API: `GET /api/skills`; a chat turn with `skill:"ats"` streams `tool_step`+`done` and never an `action`;
  a `checkout` action event round-trips and the frontend-equivalent `PUT current` persists.

**Manual (live, on the dev server + your OAuth token):**
1. `/` shows the four skills with descriptions; picking `/tailor` focuses the turn.
2. Free chat: "what changed between my notion branch and main?" → see `▸` read/diff steps → a grounded answer.
3. `/tailor <JD>` → drafts → proposal card → **Create branch** → branch created.
4. "checkout my main resume from before NJIT" → the agent reads history, then a `checkout` confirm card →
   Confirm → HEAD moves.
5. `/ats <JD>` → read-only audit, never offers a write.
6. `npm run build` clean; 29+ backend tests green.

## Risks / notes
- **Loop cost/latency:** each read step is a model round-trip. Cap at `MAX_STEPS` and keep read results
  compact (truncate large resume bodies in `get_version` to the fields that matter).
- **OAuth + multi-step tool loop:** verified single-step works; multi-step is the same request shape
  repeated. Surface any auth error as an `error` event, never crash the SSE.
- **Stale confirm cards on reload:** structural action cards are in-session only (render as summary after
  reload) to prevent double-apply; content proposals stay actionable as today.
- **Scope guard:** v1 keeps "writes end the turn." Auto-continue-after-write and mid-stream resume are
  explicitly out of scope (possible later phase).
```
