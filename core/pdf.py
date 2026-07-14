"""LaTeX -> PDF compilation.

Server-side compilation used by the web API. Unlike the original CLI (which
wrote the PDF next to the script), this returns the PDF as ``bytes`` so the
caller can stream it or store it without touching the filesystem — the app runs
in a stateless container, and compilation is deterministic, so PDFs are always
regenerated on demand from the stored JSON rather than persisted.
"""

from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import tempfile
from pathlib import Path

from core.latex import build_latex

# pdflatex can hang on a pathological document; cap each run.
COMPILE_TIMEOUT_SECONDS = 20


class CompileError(RuntimeError):
    """Raised when pdflatex fails. ``log_tail`` holds the last lines of the log."""

    def __init__(self, message: str, log_tail: str = "") -> None:
        super().__init__(message)
        self.log_tail = log_tail


def pdflatex_available() -> bool:
    return shutil.which("pdflatex") is not None


def compile_pdf_bytes(data: dict, *, timeout: int = COMPILE_TIMEOUT_SECONDS) -> bytes:
    """Compile resume ``data`` to a PDF and return its bytes.

    Runs pdflatex twice (standard practice for correct cross-references) in an
    isolated temp dir with shell-escape disabled, since the content is
    user/AI-generated. Raises :class:`CompileError` with a log tail on failure.
    """
    if not pdflatex_available():
        raise CompileError(
            "pdflatex not found on PATH. Install a LaTeX distribution "
            "(texlive-latex-recommended + texlive-fonts-recommended)."
        )
    tex = build_latex(data)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tex_file = tmp_path / "resume.tex"
        tex_file.write_text(tex, encoding="utf-8")
        for run in range(2):
            try:
                result = subprocess.run(
                    [
                        "pdflatex",
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-no-shell-escape",
                        tex_file.name,
                    ],
                    cwd=tmp_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                raise CompileError(
                    f"pdflatex timed out after {timeout}s on run {run + 1}."
                )
            if result.returncode != 0:
                log = tmp_path / "resume.log"
                tail = (
                    "\n".join(log.read_text(errors="ignore").splitlines()[-20:])
                    if log.exists()
                    else result.stdout[-2000:]
                )
                raise CompileError(
                    f"pdflatex failed on run {run + 1}.", log_tail=tail
                )
        produced = tmp_path / "resume.pdf"
        if not produced.exists():
            raise CompileError("Compilation finished but produced no PDF.")
        return produced.read_bytes()


def compute_pdf_name(data: dict, *, today: dt.date | None = None) -> str:
    """e.g. ``sstuhl_2026_05.pdf`` — initials + YYYY_MM.

    Deliberately generic so the same filename is used for every application.
    """
    name = data["personal"]["name"]
    parts = [p for p in name.split() if p]
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[-1]).lower()
    else:
        initials = parts[0].lower() if parts else "resume"
    initials = "".join(c for c in initials if c.isalnum())
    today = today or dt.date.today()
    return f"{initials}_{today:%Y_%m}.pdf"


def compute_archive_name(data: dict, version: int, *, today: dt.date | None = None) -> str:
    """e.g. ``sstuhl_2026_05_v0014.pdf`` — a per-version download name."""
    base = compute_pdf_name(data, today=today).removesuffix(".pdf")
    return f"{base}_v{version:04d}.pdf"
