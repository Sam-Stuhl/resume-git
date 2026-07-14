# ── Stage 1: build the React SPA ─────────────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime with a minimal TeX distribution ───────────────────
FROM python:3.13-slim

# LaTeX packages the template needs: latexsym, fullpage, titlesec, marvosym,
# enumitem, hyperref, fancyhdr, babel, tabularx, glyphtounicode — all covered by
# texlive-latex-recommended + texlive-fonts-recommended, plus
# texlive-latex-extra for titlesec/enumitem (not in -recommended).
RUN apt-get update && apt-get install -y --no-install-recommends \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
        "fastapi>=0.115" "uvicorn[standard]>=0.30" \
        "sqlalchemy[asyncio]>=2.0" asyncpg aiosqlite \
        anthropic "pyjwt[crypto]>=2.8" "httpx>=0.27"

COPY core/ ./core/
COPY db/ ./db/
COPY api/ ./api/
COPY services.py ./
COPY samples/ ./samples/
COPY scripts/ ./scripts/
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Build-time smoke test: prove the TeX package set can compile the template
# (prints the LaTeX log tail on failure so a missing package is diagnosable).
RUN PYTHONPATH=/app python scripts/pdf_smoke_test.py

EXPOSE 8080
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
