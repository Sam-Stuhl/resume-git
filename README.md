# Resume Manager

A small web app for managing a resume with full version history, diffing, AI
tailoring, and one-click PDF compilation. JSON is the single source of truth; a
LaTeX (Jake's-Resume) template renders it to an ATS-friendly one-page PDF.

Built for a handful of users (not a public SaaS). It runs behind
[Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/policies/access/)
for auth and deploys on a self-hosted [console](https://github.com/Sam-Stuhl/console) PaaS.

## Two kinds of changes

- **Base updates** — facts about your life change (new role, new school,
  finished a project). These update *who you are* and become the new canonical
  baseline. Future tailoring starts from the latest base.
- **Tailoring** — a job-specific *presentation* of your background. Tailored
  versions fork from the current base and never become the new base.

Nothing is ever overwritten: every save is a new version, and you can restore
any past one (non-destructively).

## Architecture

| Layer | Tech |
|-------|------|
| Core | `core/` — pure Python: LaTeX render, PDF compile, diff, schema, prompts, AI |
| Backend | FastAPI (`api/`) + SQLAlchemy async (`db/`), reusing `core/` |
| Frontend | React + Vite + TypeScript SPA (`frontend/`), served by the backend in prod |
| Data | Postgres (Neon) in prod, SQLite locally — resume JSON stored in-row; **PDFs compiled on demand**, never stored |
| Auth | Cloudflare Access (Google IdP, email allowlist) — the app reads the verified identity header; no in-app login |
| AI | Claude API (`anthropic`) when a key is set; copy-paste prompt fallback otherwise |

## Local development

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" aiosqlite httpx "pyjwt[crypto]" anthropic
cp .env.example .env                     # DEV_USER_EMAIL impersonates a user outside Access
DEV_USER_EMAIL=dev@example.com uvicorn api.main:app --reload --port 8080

# Frontend (separate terminal) — Vite proxies /api to :8080
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Requires `pdflatex` on PATH for PDF compilation
(`brew install --cask mactex-no-gui`, or `texlive-latex-recommended` on Linux).

Run the tests with `pytest` (the PDF test auto-skips if `pdflatex` is absent).

## Deploying on `console`

1. Create a Neon Postgres project; note the connection string.
2. Register the project in the console; set the `DATABASE_URL` secret. (That's
   the only required secret — Cloudflare Access handles auth at the edge and
   injects the identity header. `CF_ACCESS_TEAM_DOMAIN`/`CF_ACCESS_AUD` are
   optional secrets that enable an extra JWT-signature check.)
3. In Cloudflare Access, gate `resume.samstuhl.com` with Google IdP and your
   email allowlist.
4. Copy `deploy.yml` to `.github/workflows/deploy.yml`. Push to `main` — GitHub
   Actions builds the image (Dockerfile bundles a minimal TeX distro and runs a
   PDF smoke test), and the console pulls and deploys it.
5. One-time: import your existing CLI data —
   `DATABASE_URL=<neon-url> python migrate_import.py you@example.com`.

## JSON schema

```json
{
  "personal":   { "name", "email", "phone", "github", "linkedin" },
  "summary":    "...",
  "experience": [ { "title", "organization", "location", "start_date", "end_date", "bullets": [] } ],
  "projects":   [ { "name", "stack", "bullets": [] } ],
  "leadership": [ { "title", "organization", "location", "start_date", "end_date", "bullets": [] } ],
  "skills":     { "Languages": "...", "Frameworks & Libraries": "...", ... },
  "education":  [ { "school", "location", "gpa", "start_date", "end_date", "coursework" } ]
}
```

## Privacy

This is a **public, code-only** repo. All personal data (`resume_data/`, PDFs,
the SQLite DB, the personal work log) is gitignored. Sample data lives in
`samples/sample_resume.json` (fictional). Secrets are never committed — they are
set as console secrets or a local `.env`.

## Legacy CLI

The original single-file interactive console (`resume.py`) still runs
standalone (`python resume.py`) against a local `resume_data/` folder. The web
app supersedes it; the shared logic now lives in `core/`.
