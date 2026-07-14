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
# texlive-latex-recommended + texlive-fonts-recommended.
RUN apt-get update && apt-get install -y --no-install-recommends \
        texlive-latex-recommended \
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
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Build-time smoke test: prove the TeX package set can compile the template.
RUN python -c "import json; from core.pdf import compile_pdf_bytes; \
    d=json.load(open('samples/sample_resume.json')); \
    pdf=compile_pdf_bytes(d); assert pdf[:4]==b'%PDF', 'compile failed'; \
    print('PDF smoke test OK', len(pdf), 'bytes')"

EXPOSE 8080
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
