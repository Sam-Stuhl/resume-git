#!/usr/bin/env python3
"""
Resume Manager — an interactive console for versioning and compiling resumes.

The intelligence (tailoring to a job description) happens in Claude chats.
This tool handles everything local: storage, versioning, diffing, compilation,
and archiving.

Run:    python resume.py
Setup:  on first run, the tool will guide you through pasting your base JSON.

Requires:
  - Python 3.9+
  - pdflatex on PATH (TeX Live, MacTeX, or MiKTeX)
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------
# Data lives in a 'resume_data' folder next to this script, so everything
# stays self-contained and visible. Move the script and the folder together
# to migrate to a new machine.
SCRIPT_DIR = Path(__file__).resolve().parent
HOME = SCRIPT_DIR / "resume_data"
DB_PATH = HOME / "resume.db"
VERSIONS_DIR = HOME / "versions"
OUTPUT_DIR = HOME / "output"
ARCHIVE_DIR = HOME / "archive"
CURRENT_LINK = HOME / "current.json"

# Filename for the latest PDF (same every time — looks identical for every application)
LATEST_PDF_NAME = None  # computed at runtime from personal.name + current date


# ---------------------------------------------------------------------------
# Terminal styling (no external deps — basic ANSI)
# ---------------------------------------------------------------------------
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def style(text: str, *codes: str) -> str:
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + Style.RESET


def banner(text: str) -> None:
    line = "─" * (len(text) + 4)
    print(style(f"╭{line}╮", Style.CYAN))
    print(style(f"│  {text}  │", Style.CYAN))
    print(style(f"╰{line}╯", Style.CYAN))


def divider() -> None:
    print(style("─" * 56, Style.GRAY))


def info(text: str) -> None:
    print(style("→ ", Style.CYAN) + text)


def success(text: str) -> None:
    print(style("✓ ", Style.GREEN) + text)


def warn(text: str) -> None:
    print(style("! ", Style.YELLOW) + text)


def error(text: str) -> None:
    print(style("✗ ", Style.RED) + text)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_storage() -> None:
    HOME.mkdir(exist_ok=True)
    VERSIONS_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS versions (
            version    INTEGER PRIMARY KEY,
            created_at TEXT    NOT NULL,
            label      TEXT,
            jd_text    TEXT,
            json_hash  TEXT    NOT NULL,
            is_base    INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    db.commit()
    db.close()


def db_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def get_config(key: str, default: str | None = None) -> str | None:
    with db_conn() as db:
        row = db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_config(key: str, value: str) -> None:
    with db_conn() as db:
        db.execute(
            "INSERT INTO config(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        db.commit()


def next_version() -> int:
    with db_conn() as db:
        row = db.execute("SELECT MAX(version) FROM versions").fetchone()
    return (row[0] or 0) + 1


def latest_base_version() -> int | None:
    """Return the most recent base version, or None if none exist."""
    with db_conn() as db:
        row = db.execute(
            "SELECT MAX(version) FROM versions WHERE is_base=1"
        ).fetchone()
    return row[0] if row and row[0] else None


def list_versions() -> list[tuple]:
    with db_conn() as db:
        return db.execute(
            "SELECT version, created_at, label, json_hash, is_base "
            "FROM versions ORDER BY version DESC"
        ).fetchall()


def get_version(v: int) -> tuple | None:
    with db_conn() as db:
        return db.execute(
            "SELECT version, created_at, label, jd_text, json_hash, is_base "
            "FROM versions WHERE version=?",
            (v,),
        ).fetchone()


def insert_version(
    version: int,
    label: str | None,
    jd_text: str | None,
    json_hash: str,
    is_base: bool = False,
) -> None:
    with db_conn() as db:
        db.execute(
            "INSERT INTO versions(version,created_at,label,jd_text,json_hash,is_base) "
            "VALUES(?,?,?,?,?,?)",
            (
                version,
                dt.datetime.now().isoformat(timespec="seconds"),
                label,
                jd_text,
                json_hash,
                1 if is_base else 0,
            ),
        )
        db.commit()


# ---------------------------------------------------------------------------
# Version file I/O
# ---------------------------------------------------------------------------
def version_path(v: int) -> Path:
    return VERSIONS_DIR / f"v{v:04d}.json"


def load_version(v: int) -> dict:
    return json.loads(version_path(v).read_text(encoding="utf-8"))


def save_version(v: int, data: dict) -> None:
    version_path(v).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def hash_json(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:12]


def current_version() -> int | None:
    val = get_config("current_version")
    return int(val) if val else None


def set_current_version(v: int) -> None:
    set_config("current_version", str(v))
    if CURRENT_LINK.exists() or CURRENT_LINK.is_symlink():
        CURRENT_LINK.unlink()
    try:
        CURRENT_LINK.symlink_to(version_path(v))
    except OSError:
        # Windows without dev-mode — fall back to copying
        shutil.copy(version_path(v), CURRENT_LINK)


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------
def read_clipboard() -> str | None:
    """Read text from the system clipboard. Returns None if no clipboard tool available."""
    tools = []
    if sys.platform == "darwin":
        tools = [["pbpaste"]]
    elif sys.platform.startswith("win"):
        # Use PowerShell to read the clipboard reliably on Windows
        tools = [["powershell", "-Command", "Get-Clipboard"]]
    else:
        tools = [
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ]
    for cmd in tools:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def get_long_input(label: str, allow_clipboard: bool = True) -> str | None:
    """
    Read long input from the system clipboard.
    If clipboard is unavailable or empty, give the user clear guidance.
    Returns the text, or None if aborted.
    """
    print()
    info(f"Reading {label} from clipboard...")
    text = read_clipboard()

    if text is None:
        error("Could not access the clipboard.")
        print(style("  On macOS:  this should work out of the box (uses pbpaste).", Style.GRAY))
        print(style("  On Linux:  install one of: xclip, xsel, or wl-clipboard.", Style.GRAY))
        print(style("  On Windows: should work via PowerShell.", Style.GRAY))
        return None

    if not text.strip():
        warn("Clipboard is empty. Copy the JSON (or text) from your Claude chat and try again.")
        return None

    info(f"Read {len(text)} characters from clipboard.")
    return text.strip()


def ask(prompt_text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return input(style(f"{prompt_text}{suffix}: ", Style.CYAN)).strip() or default


def confirm(prompt_text: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    raw = input(style(f"{prompt_text} {suffix}: ", Style.CYAN)).strip().lower()
    if not raw:
        return default_yes
    return raw.startswith("y")


# ---------------------------------------------------------------------------
# Diff rendering
# ---------------------------------------------------------------------------
def render_diff(old: dict, new: dict, context: int = 1) -> str:
    """Pretty unified diff of two JSON documents."""
    old_text = json.dumps(old, indent=2, ensure_ascii=False, sort_keys=False).splitlines()
    new_text = json.dumps(new, indent=2, ensure_ascii=False, sort_keys=False).splitlines()
    diff = difflib.unified_diff(
        old_text, new_text, fromfile="previous", tofile="updated", n=context, lineterm=""
    )
    out = []
    for line in diff:
        if line.startswith("+++") or line.startswith("---"):
            out.append(style(line, Style.BOLD))
        elif line.startswith("@@"):
            out.append(style(line, Style.MAGENTA))
        elif line.startswith("+"):
            out.append(style(line, Style.GREEN))
        elif line.startswith("-"):
            out.append(style(line, Style.RED))
        else:
            out.append(style(line, Style.GRAY))
    return "\n".join(out)


def summarize_changes(old: dict, new: dict) -> list[str]:
    """High-level summary of what changed between two resume JSONs."""
    changes: list[str] = []

    def section(label: str, before, after, count_key: str | None = None) -> None:
        if before == after:
            return
        if count_key is None:
            changes.append(f"{label} modified")
        else:
            b = len(before) if hasattr(before, "__len__") else "?"
            a = len(after) if hasattr(after, "__len__") else "?"
            if b != a:
                changes.append(f"{label}: {b} → {a} {count_key}")
            else:
                changes.append(f"{label} reworded ({b} {count_key})")

    if old.get("summary") != new.get("summary"):
        ob = len(old.get("summary") or "")
        nb = len(new.get("summary") or "")
        changes.append(f"Summary rewritten ({ob} → {nb} chars)")

    section("Experience", old.get("experience"), new.get("experience"), "roles")
    section("Projects", old.get("projects"), new.get("projects"), "projects")
    section("Leadership", old.get("leadership"), new.get("leadership"), "roles")
    section("Education", old.get("education"), new.get("education"), "schools")

    old_skills = old.get("skills") or {}
    new_skills = new.get("skills") or {}
    if old_skills != new_skills:
        added = set(new_skills) - set(old_skills)
        removed = set(old_skills) - set(new_skills)
        for k in added:
            changes.append(f"Skills: added category '{k}'")
        for k in removed:
            changes.append(f"Skills: removed category '{k}'")
        for k in set(old_skills) & set(new_skills):
            if old_skills[k] != new_skills[k]:
                changes.append(f"Skills.{k} updated")

    if not changes:
        changes.append("No structural changes detected")
    return changes


# ---------------------------------------------------------------------------
# LaTeX compilation (imported from the earlier work)
# ---------------------------------------------------------------------------
LATEX_SPECIAL_CHARS = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def tex_escape(text: str) -> str:
    if not text:
        return ""
    result = text.replace("\\", LATEX_SPECIAL_CHARS["\\"])
    for ch, esc in LATEX_SPECIAL_CHARS.items():
        if ch == "\\":
            continue
        result = result.replace(ch, esc)
    return result


PREAMBLE = r"""
\documentclass[letterpaper,11pt]{article}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\input{glyphtounicode}
\pagestyle{fancy}\fancyhf{}\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}\renewcommand{\footrulewidth}{0pt}
\addtolength{\oddsidemargin}{-0.6in}
\addtolength{\evensidemargin}{-0.6in}
\addtolength{\textwidth}{1.2in}
\addtolength{\topmargin}{-.85in}
\addtolength{\textheight}{1.6in}
\urlstyle{same}
\raggedbottom\raggedright
\setlength{\tabcolsep}{0in}
\titleformat{\section}{\vspace{-4pt}\scshape\raggedright\large}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]
\pdfgentounicode=1
\newcommand{\resumeItem}[1]{\item\small{{#1 \vspace{-2pt}}}}
\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}}
\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\setlength{\footskip}{4.08003pt}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
"""


def render_header(personal: dict) -> str:
    name = tex_escape(personal["name"])
    email = tex_escape(personal["email"])
    phone = tex_escape(personal["phone"])
    github = personal["github"]
    linkedin = personal["linkedin"]
    return (
        r"\begin{center}" + "\n"
        + rf"    \textbf{{\Huge \scshape {name}}} \\ \vspace{{1pt}}" + "\n"
        + rf"    \small {phone} $|$ \href{{mailto:{email}}}{{\underline{{{email}}}}} $|$" + "\n"
        + rf"    \href{{https://{linkedin}}}{{\underline{{{tex_escape(linkedin)}}}}} $|$" + "\n"
        + rf"    \href{{https://{github}}}{{\underline{{{tex_escape(github)}}}}}" + "\n"
        + r"\end{center}"
    )


def render_summary(summary: str) -> str:
    if not summary:
        return ""
    return f"\n\\section*{{Summary}}\n\\small {tex_escape(summary)}\n\\vspace{{2pt}}\n"


def render_role_block(items: list, section_title: str) -> str:
    if not items:
        return ""
    out = [f"\n\\section{{{section_title}}}", r"\resumeSubHeadingListStart"]
    for job in items:
        title = tex_escape(job["title"])
        org = tex_escape(job["organization"])
        location = tex_escape(job.get("location", ""))
        start = tex_escape(job.get("start_date", ""))
        end = tex_escape(job.get("end_date", ""))
        date_range = f"{start} -- {end}" if start and end else (start or end)
        out.append(rf"\resumeSubheading{{{title}}}{{{date_range}}}{{{org}}}{{{location}}}")
        if job.get("bullets"):
            out.append(r"\resumeItemListStart")
            for b in job["bullets"]:
                out.append(rf"\resumeItem{{{tex_escape(b)}}}")
            out.append(r"\resumeItemListEnd")
    out.append(r"\resumeSubHeadingListEnd")
    return "\n".join(out)


def render_projects(projects: list) -> str:
    if not projects:
        return ""
    out = ["\n\\section{Projects}", r"\resumeSubHeadingListStart"]
    for p in projects:
        name = tex_escape(p["name"])
        stack = tex_escape(p.get("stack", ""))
        heading = rf"\textbf{{{name}}} $|$ \emph{{{stack}}}" if stack else rf"\textbf{{{name}}}"
        out.append(rf"\resumeProjectHeading{{{heading}}}{{}}")
        if p.get("bullets"):
            out.append(r"\resumeItemListStart")
            for b in p["bullets"]:
                out.append(rf"\resumeItem{{{tex_escape(b)}}}")
            out.append(r"\resumeItemListEnd")
    out.append(r"\resumeSubHeadingListEnd")
    return "\n".join(out)


def render_skills(skills: dict) -> str:
    if not skills:
        return ""
    rows = [rf"\textbf{{{tex_escape(k)}}}{{: {tex_escape(v)}}}" for k, v in skills.items()]
    body = " \\\\\n     ".join(rows)
    return (
        "\n\\section{Technical Skills}\n"
        " \\begin{itemize}[leftmargin=0.15in, label={}]\n"
        f"    \\small{{\\item{{\n     {body} \\\\\n    }}}}\n"
        " \\end{itemize}\n"
    )


def render_education(education: list) -> str:
    if not education:
        return ""
    out = ["\n\\section{Education}", r"\resumeSubHeadingListStart"]
    for ed in education:
        school = tex_escape(ed["school"])
        location = tex_escape(ed.get("location", ""))
        gpa = tex_escape(ed.get("gpa", ""))
        gpa_str = f"GPA: {gpa}" if gpa else ""
        start = tex_escape(ed.get("start_date", ""))
        end = tex_escape(ed.get("end_date", ""))
        date_range = f"{start} -- {end}" if start and end else (start or end)
        # Match experience/leadership layout: title + date on top, sub-info italic on bottom
        # Top-right is the date; bottom-left is GPA (italic); bottom-right is location (italic)
        out.append(rf"\resumeSubheading{{{school}}}{{{date_range}}}{{{gpa_str}}}{{{location}}}")
        if ed.get("coursework"):
            out.append(r"\resumeItemListStart")
            out.append(rf"\resumeItem{{\textbf{{Relevant Coursework:}} {tex_escape(ed['coursework'])}}}")
            out.append(r"\resumeItemListEnd")
    out.append(r"\resumeSubHeadingListEnd")
    return "\n".join(out)


def build_latex(data: dict) -> str:
    parts = [PREAMBLE, r"\begin{document}", render_header(data["personal"])]
    if data.get("summary"):
        parts.append(render_summary(data["summary"]))
    parts.append(render_role_block(data.get("experience", []), "Experience"))
    parts.append(render_projects(data.get("projects", [])))
    parts.append(render_role_block(data.get("leadership", []), "Leadership \\& Extracurriculars"))
    parts.append(render_skills(data.get("skills", {})))
    parts.append(render_education(data.get("education", [])))
    parts.append(r"\end{document}")
    return "\n".join(parts)


def compile_pdf(data: dict, output_path: Path) -> Path:
    if shutil.which("pdflatex") is None:
        raise RuntimeError(
            "pdflatex not found on PATH. Install a LaTeX distribution:\n"
            "  macOS:   brew install --cask mactex-no-gui\n"
            "  Ubuntu:  sudo apt install texlive-latex-recommended texlive-fonts-recommended\n"
            "  Windows: install MiKTeX from https://miktex.org/"
        )
    tex = build_latex(data)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tex_file = tmp_path / "resume.tex"
        tex_file.write_text(tex, encoding="utf-8")
        for run in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_file.name],
                cwd=tmp_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                log = (tmp_path / "resume.log")
                tail = "\n".join(log.read_text(errors="ignore").splitlines()[-20:]) if log.exists() else ""
                raise RuntimeError(f"pdflatex failed on run {run + 1}:\n{tail}")
        produced = tmp_path / "resume.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(produced, output_path)
    return output_path


# ---------------------------------------------------------------------------
# Filename strategy
# ---------------------------------------------------------------------------
def compute_pdf_name(data: dict) -> str:
    """sstuhl_2026_05.pdf — initials + YYYY_MM. Same name every application."""
    name = data["personal"]["name"]
    parts = [p for p in name.split() if p]
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[-1]).lower()
    else:
        initials = parts[0].lower() if parts else "resume"
    initials = "".join(c for c in initials if c.isalnum())
    today = dt.date.today()
    return f"{initials}_{today:%Y_%m}.pdf"


def compute_archive_name(data: dict, version: int) -> str:
    """sstuhl_2026_05_v0014.pdf — keeps each PDF for history."""
    base = compute_pdf_name(data).removesuffix(".pdf")
    return f"{base}_v{version:04d}.pdf"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_init() -> None:
    """First-run: paste base resume JSON. Offers the onboarding prompt for users without JSON."""
    info("First-time setup.")
    print()
    print(style("Do you already have your resume as JSON?", Style.BOLD))
    print("  [y] Yes  — I have the JSON ready to paste")
    print("  [n] No   — show me a prompt to convert my resume into JSON first")
    choice = ask("Choice", default="n").lower()

    if not choice.startswith("y"):
        print()
        print(style("─── Step 1: Copy the prompt below into a NEW Claude chat ───", Style.MAGENTA))
        print()
        print(ONBOARDING_PROMPT)
        print()
        print(style("─── End of prompt ───", Style.MAGENTA))
        print()
        print(style("Step 2:", Style.BOLD) + " Paste the prompt into a new Claude chat, then paste your")
        print("        resume below the prompt (where it says '[paste your resume here]').")
        print(style("Step 3:", Style.BOLD) + " Claude will return JSON. Copy the entire JSON.")
        print(style("Step 4:", Style.BOLD) + " Come back here and paste it below.")
        print()
        if not confirm("Ready to paste your JSON?", default_yes=True):
            warn("No problem. Run 'init' again when you have the JSON ready.")
            return

    print()
    raw = get_long_input("Base resume JSON")
    if not raw:
        warn("Aborted — nothing provided.")
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        error(f"Invalid JSON: {e}")
        print(style("Tip: make sure you copied ONLY the JSON, starting with { and ending with }.", Style.GRAY))
        print(style("     If Claude added any text before or after, remove it.", Style.GRAY))
        return
    if "personal" not in data or "name" not in data.get("personal", {}):
        error("JSON missing required field: personal.name")
        return
    v = next_version()
    save_version(v, data)
    insert_version(v, label="Base resume", jd_text=None, json_hash=hash_json(data), is_base=True)
    set_current_version(v)
    success(f"Saved as v{v:04d} (base). You can now run 'tailor' or 'compile'.")


def cmd_tailor() -> None:
    """Paste an updated JSON, diff against the latest base, save as a tailored fork."""
    base = latest_base_version()
    if base is None:
        warn("No base resume yet. Run 'init' or 'base' first.")
        return
    old = load_version(base)

    print()
    info(f"Tailoring from base v{base:04d}.")
    raw = get_long_input("Tailored JSON from your Claude chat")
    if not raw:
        warn("Aborted.")
        return
    try:
        new = json.loads(raw)
    except json.JSONDecodeError as e:
        error(f"Invalid JSON: {e}")
        return

    if hash_json(new) == hash_json(old):
        warn("This JSON is identical to the base — nothing to save.")
        return

    print()
    label = ask("Label for this tailored version (e.g. 'Jane Street SWE')")
    label = label or None
    include_jd = confirm("Add the job description to history? (helpful for tracking)", default_yes=False)
    jd_text = get_long_input("Job description") if include_jd else None
    jd_text = jd_text or None

    print()
    divider()
    print(style(f"Changes vs base v{base:04d}:", Style.BOLD))
    for change in summarize_changes(old, new):
        print(f"  • {change}")
    divider()

    choice = ask("Action — [y]es / [n]o / [d]iff to see line-by-line", default="y").lower()
    if choice.startswith("d"):
        print()
        print(render_diff(old, new, context=2))
        print()
        choice = ask("Save and compile? [y/n]", default="y").lower()
    if not choice.startswith("y"):
        warn("Discarded.")
        return

    v = next_version()
    save_version(v, new)
    insert_version(v, label=label, jd_text=jd_text, json_hash=hash_json(new), is_base=False)
    set_current_version(v)
    success(f"Saved as v{v:04d} (tailored, forked from base v{base:04d}).")

    compile_and_archive(new, v)


def cmd_base() -> None:
    """Update the factual baseline — life changes, new experiences, new schools."""
    prev_base = latest_base_version()
    if prev_base is None:
        warn("No baseline yet. Run 'init' first to create v0001 as your base.")
        return
    old = load_version(prev_base)

    print()
    info(f"Updating baseline. Current base is v{prev_base:04d}.")
    print(style("Use this for factual life changes (new role, new school, finished internship)", Style.GRAY))
    print(style("— NOT for tailoring to a specific job (use 'tailor' for that).", Style.GRAY))
    raw = get_long_input("Updated baseline JSON")
    if not raw:
        warn("Aborted.")
        return
    try:
        new = json.loads(raw)
    except json.JSONDecodeError as e:
        error(f"Invalid JSON: {e}")
        return

    if hash_json(new) == hash_json(old):
        warn("This JSON is identical to the current base — nothing to save.")
        return

    print()
    label = ask("Label describing what changed (e.g. 'Added NJIT admission')")
    label = label or "Base update"

    print()
    divider()
    print(style(f"Changes vs previous base v{prev_base:04d}:", Style.BOLD))
    for change in summarize_changes(old, new):
        print(f"  • {change}")
    divider()

    choice = ask("Action — [y]es / [n]o / [d]iff to see line-by-line", default="y").lower()
    if choice.startswith("d"):
        print()
        print(render_diff(old, new, context=2))
        print()
        choice = ask("Save as new base and compile? [y/n]", default="y").lower()
    if not choice.startswith("y"):
        warn("Discarded.")
        return

    v = next_version()
    save_version(v, new)
    insert_version(v, label=label, jd_text=None, json_hash=hash_json(new), is_base=True)
    set_current_version(v)
    success(f"Saved as v{v:04d} (new base). Future tailoring will fork from here.")

    compile_and_archive(new, v)


def compile_and_archive(data: dict, version: int) -> None:
    pdf_name = compute_pdf_name(data)
    out_path = OUTPUT_DIR / pdf_name
    try:
        compile_pdf(data, out_path)
    except RuntimeError as e:
        error(str(e))
        return
    archive_path = ARCHIVE_DIR / compute_archive_name(data, version)
    shutil.copy(out_path, archive_path)
    success(f"Compiled: {out_path}")
    print(style(f"  Archived as: {archive_path}", Style.GRAY))


def cmd_compile(arg: str | None) -> None:
    """Recompile the current (or a specified) version without altering JSON."""
    v = parse_version(arg) if arg else current_version()
    if v is None:
        warn("No version specified and no current version set.")
        return
    rec = get_version(v)
    if rec is None:
        error(f"v{v:04d} not found.")
        return
    data = load_version(v)
    compile_and_archive(data, v)


def cmd_history() -> None:
    rows = list_versions()
    if not rows:
        warn("No versions yet.")
        return
    cur = current_version()
    cur_base = latest_base_version()
    print()
    print(style(f"  {'Ver':<8} {'Created':<20} {'Type':<8} {'Label':<32}", Style.BOLD))
    divider()
    for version, created_at, label, _hash, is_base in rows:
        markers = []
        if version == cur:
            markers.append(style("current", Style.GREEN))
        if version == cur_base:
            markers.append(style("active base", Style.MAGENTA))
        marker_str = "  ← " + ", ".join(markers) if markers else ""
        # Use plain string for column alignment, color it after padding
        type_plain = "BASE" if is_base else "tailor"
        type_padded = f"{type_plain:<8}"
        type_colored = style(type_padded, Style.MAGENTA) if is_base else style(type_padded, Style.GRAY)
        label_display = (label or "—")[:32]
        ver_display = f"v{version:04d}"
        created_short = created_at.replace("T", " ")[:19]
        print(f"  {ver_display:<8} {created_short:<20} {type_colored} {label_display:<32}{marker_str}")
    print()


def cmd_show(arg: str | None) -> None:
    v = parse_version(arg)
    if v is None:
        return
    rec = get_version(v)
    if rec is None:
        error(f"v{v:04d} not found.")
        return
    version, created_at, label, jd_text, json_hash, is_base = rec
    print()
    print(style(f"Version v{version:04d}", Style.BOLD))
    print(f"  Created: {created_at}")
    print(f"  Label:   {label or '—'}")
    print(f"  Hash:    {json_hash}")
    print(f"  Base:    {'yes' if is_base else 'no'}")
    if jd_text:
        print()
        print(style("  Job description:", Style.BOLD))
        for line in jd_text.splitlines():
            print(style(f"    {line}", Style.GRAY))
    print()


def cmd_diff(args: list[str]) -> None:
    if len(args) < 2:
        warn("Usage: diff <v1> <v2>")
        return
    v1 = parse_version(args[0])
    v2 = parse_version(args[1])
    if v1 is None or v2 is None:
        return
    old = load_version(v1)
    new = load_version(v2)
    print()
    print(style(f"Summary: v{v1:04d} → v{v2:04d}", Style.BOLD))
    for change in summarize_changes(old, new):
        print(f"  • {change}")
    print()
    if confirm("Show full line-by-line diff?", default_yes=False):
        print()
        print(render_diff(old, new, context=2))
        print()


def cmd_restore(arg: str | None) -> None:
    v = parse_version(arg)
    if v is None:
        return
    rec = get_version(v)
    if rec is None:
        error(f"v{v:04d} not found.")
        return
    if not confirm(f"Promote v{v:04d} back to current?"):
        return
    data = load_version(v)
    new_v = next_version()
    save_version(new_v, data)
    insert_version(
        new_v,
        label=f"Restored from v{v:04d}",
        jd_text=None,
        json_hash=hash_json(data),
        is_base=False,
    )
    set_current_version(new_v)
    success(f"Restored v{v:04d} as new version v{new_v:04d}.")


def cmd_edit() -> None:
    """Open current JSON in $EDITOR, save as a new version if changed."""
    cur = current_version()
    if cur is None:
        warn("No base yet. Run 'init' first.")
        return
    editor = os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "nano")
    data = load_version(cur)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp_path = Path(tmp.name)
    try:
        subprocess.run([editor, str(tmp_path)], check=False)
        edited_raw = tmp_path.read_text(encoding="utf-8")
        try:
            edited = json.loads(edited_raw)
        except json.JSONDecodeError as e:
            error(f"Invalid JSON after edit: {e}")
            return
        if hash_json(edited) == hash_json(data):
            info("No changes.")
            return
        print()
        for change in summarize_changes(data, edited):
            print(f"  • {change}")
        print()
        is_base_edit = confirm(
            "Is this a factual change to your baseline (not a job-specific tweak)?",
            default_yes=True,
        )
        if not confirm("Save and compile?"):
            return
        v = next_version()
        save_version(v, edited)
        insert_version(
            v,
            label="Manual edit (base)" if is_base_edit else "Manual edit",
            jd_text=None,
            json_hash=hash_json(edited),
            is_base=is_base_edit,
        )
        set_current_version(v)
        kind = "new base" if is_base_edit else "tailored"
        success(f"Saved as v{v:04d} ({kind}).")
        compile_and_archive(edited, v)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


ONBOARDING_PROMPT = """\
You are helping me build a structured JSON representation of my resume that will be used by a local CLI tool. This is a one-time onboarding step.

I will paste my existing resume below (as plain text, a copy-paste from a PDF, or however I have it). Your job is to convert it into the exact JSON schema specified below, then return ONLY that JSON. No explanation, no commentary, no markdown code fences. Start your response with `{` and end with `}`.

REQUIRED SCHEMA:

{
  "personal": {
    "name":     "Full Name",
    "email":    "email@example.com",
    "phone":    "(123) 456-7890",
    "github":   "github.com/username",
    "linkedin": "linkedin.com/in/username"
  },
  "summary": "A 2-3 sentence professional summary.",
  "experience": [
    {
      "title":        "Job Title",
      "organization": "Company Name",
      "location":     "City, State or Remote",
      "start_date":   "Mon YYYY",
      "end_date":     "Mon YYYY or Present",
      "bullets": ["Action verb + what you did + tech used + impact if measurable."]
    }
  ],
  "projects":   [ { "name": "...", "stack": "...", "bullets": ["..."] } ],
  "leadership": [ { "title": "...", "organization": "...", "location": "...", "start_date": "...", "end_date": "...", "bullets": ["..."] } ],
  "skills": {
    "Languages":              "Comma-separated programming languages",
    "Frameworks & Libraries": "Comma-separated frameworks",
    "Cloud & Data":           "Comma-separated cloud and data tools",
    "Developer Tools":        "Comma-separated dev tools"
  },
  "education": [ { "school": "...", "location": "...", "gpa": "X.XX or empty", "start_date": "...", "end_date": "...", "coursework": "Comma-separated courses" } ]
}

CONVERSION RULES (informed by 2026 ATS and AI screener behavior):

1. **Faithful conversion only.** Do NOT invent or embellish. If a field is missing in the source, use empty string or empty array. Never guess.

2. **Acronym handling.** Modern ATS may match either the spelled-out form OR the acronym, not both. Best practice: spell out on first use AND include the acronym in parentheses. "Machine Learning (ML)", "Large Language Model (LLM)", "Command Line Interface (CLI)", "Amazon Web Services (AWS)". This way exact-match searches for either form will hit.

3. **Strong bullets.** Convert each bullet to: action verb + what you did + technologies used + measurable impact. Always include the exact technology names from the source (not generic terms) so they're available for keyword matching. Good action verbs: Built, Engineered, Designed, Migrated, Led, Implemented, Automated, Developed, Architected, Shipped, Optimized.

4. **Preserve numbers ruthlessly.** Any specific number in the source (percentages, user counts, dataset sizes, team sizes, performance improvements) is gold — AI ranking systems weight measurable evidence heavily. Keep every number. Never invent numbers if they aren't in the source.

5. **Character cleanup.** Replace em-dashes with semicolons or hyphens. Replace arrows with the word 'to'. Use straight quotes only. Avoid characters that might trip a LaTeX compiler or ATS parser.

6. **Empty sections.** If a section is missing in the source, return that key with an empty array. Do not omit top-level keys — the CLI tool requires the full schema.

7. **Skills categorization.** Group skills into the four categories shown. If the source lists skills in one block, split them by type. Include the exact technology names as they appear in the source. Omit a category key only if there is nothing to put in it.

8. **Section presence guidance for student / early-career.** If the user lists relevant coursework, certifications, competitions, or honors, preserve them — these are strong signals for early-career candidates. They can go in the education entry's coursework field or in the leadership section.

9. **Include everything from the source for now.** The user will trim later with the tailoring tool. Better to have too much in the baseline than to lose information.

Below is my resume. Return ONLY the JSON, starting with { and ending with }.

MY RESUME:
[paste your resume here]
"""


SESSION_PROMPT_TEMPLATE = """\
You are my dedicated resume advisor for an ongoing chat session. Across this chat, I will send you four kinds of requests, identified by a tag at the start of each message:

- [TAILOR] — adapt my current resume to a specific job description
- [BASE UPDATE] — apply a real change in my life (new role, new school, finished project, new skill, removed content, etc.)
- [ASK] — get your honest opinion on something resume-related, without committing to a change
- [ATS] — run a self-audit on a tailored version against a job description before I submit it

These four modes have different rules. Read all four sections carefully before responding.

═══════════════════════════════════════════════════════════════
MY CURRENT BASELINE
═══════════════════════════════════════════════════════════════

Below is my current baseline resume. Hold this in context for the rest of the chat. When I send a [TAILOR] request, work from this baseline. When I send a [BASE UPDATE] request, modify this baseline and remember the new version for subsequent requests. When I send an [ASK] or [ATS] request, just give your honest advice.

__BASELINE_JSON__

═══════════════════════════════════════════════════════════════
HOW MODERN ATS AND AI SCREENERS ACTUALLY WORK (2026)
═══════════════════════════════════════════════════════════════

Your decisions should be grounded in these facts about how my resume will actually be evaluated:

1. **Three layers of evaluation.** Parsing (extraction into structured fields), keyword matching (exact, fuzzy, and semantic), and AI ranking (Workday Illuminate, Greenhouse AI, iCIMS Copilot powered by GPT-4). All three must pass; being great at one does not compensate for failing another.

2. **Keyword location is weighted.** The summary and the first bullet of each role carry more weight than later bullets. Put the highest-value matching terms where both algorithms and humans look first.

3. **Exact-match still dominates scoring.** Even modern semantic systems weight exact-match keywords more heavily than synonyms. Mirror the job description's exact language wherever truthful.

4. **Acronyms cut both ways.** Some ATS only match "Machine Learning"; others only match "ML". The safest pattern is to include BOTH forms in close proximity at least once (e.g., "Machine Learning (ML)" on first use, then use whichever form the JD uses in later bullets). Same for AWS / Amazon Web Services, CI/CD / continuous integration, REST / RESTful APIs, etc.

5. **AI ranking layer rewards evidence.** Modern AI scorers look for measurable impact, not just claims. A bullet with a number ("reduced latency by 40%") outranks the same bullet without a number, even semantically. Whenever a real number is available in the baseline, use it. Never invent numbers.

6. **Career recency and trajectory matter.** Modern systems weight recent work more than old work. Position the strongest recent items first within each section.

7. **Keyword stuffing is now actively penalized.** Repetition of the same keyword across many bullets, or hidden white-on-white text, triggers fraud flagging in Workday, Greenhouse, and Lever. Integrate keywords naturally where the work genuinely happened.

8. **Section headings must match a built-in dictionary.** "Experience" (not "Career Journey"), "Education" (not "Academic Background"), "Skills" (not "Toolkit"). Creative headings cause parser miscategorization. My LaTeX template already uses standard headings — don't suggest changing them.

═══════════════════════════════════════════════════════════════
UNIVERSAL RULES (apply to all modes)
═══════════════════════════════════════════════════════════════

1. **Schema is sacred** (when producing JSON). Whatever JSON you produce must have exactly the same top-level keys, nested keys, and data types as the baseline. Never add new top-level keys. Use empty string or empty array for empty values rather than dropping keys.

2. **Never fabricate facts.** Do not invent technologies, employers, dates, schools, projects, accomplishments, metrics, or skills I have not told you about. Fabricated specifics are a serious problem and easy for recruiters to catch. If you need a number and one isn't available, omit the metric rather than invent one.

3. **ATS-friendly character set.** No em-dashes (use semicolons or hyphens). No arrows (use 'to'). No fancy quotes. No special Unicode characters. Standard ASCII punctuation only.

4. **One-page budget.** The resume compiles to a single letter-sized page. Page space is a finite resource — every addition has an opportunity cost. Treat it that way.

5. **Be an honest advisor, not a yes-man.** If I propose something that would make my resume worse — too crowded, irrelevant, weak content, or just a bad idea — say so plainly and explain why. Push back. Suggest better alternatives. You're not here to flatter me; you're here to help me get interviews. After pushback, if I still want to proceed, I will tell you to proceed and you should.

═══════════════════════════════════════════════════════════════
TAILOR MODE — strict, presentation only, ATS-optimized
═══════════════════════════════════════════════════════════════

When I send a [TAILOR] message with a job description, your job is to PRESENT my existing background in the way that maximizes scoring on both classical ATS keyword matching and modern AI ranking, while remaining truthful.

Required tailoring moves:

1. **Extract the JD's vocabulary first.** Before editing anything, identify the 10-15 highest-value keywords and exact phrases from the JD: required technologies, specific frameworks, methodologies, role-defining terms, and any unusual phrasings the company favors. These are your targets.

2. **Mirror the JD's exact language wherever truthful.** If the JD says "low-latency systems" and my baseline says "fast systems", change my wording to "low-latency systems" — provided the underlying work genuinely was about latency. Do not change wording if it would misrepresent the work.

3. **Rewrite the summary aggressively.** The summary is the highest-weighted location for both keyword scoring and AI candidate summarization. Lead with the role-defining terms from the JD. Pack 3-4 of the highest-value JD keywords into the first sentence where truthful. Keep it 2-3 sentences.

4. **Put the strongest matching bullet first in each role.** Reorder bullets so the one most relevant to the JD comes first. The first bullet is weighted heaviest within a role.

5. **Reorder projects and leadership.** Put the most JD-relevant entry first. Drop entries that don't match the role (keep at most 2 of each).

6. **Optimize acronyms for the JD.** If the JD uses "ML", use "ML" in this tailored version. If the JD uses "Machine Learning", use that. Include both forms once in the bullet where the work is most prominently described.

7. **Reorder within skill categories.** Put matching skills first in each category. Never invent skills.

You may NOT:
- Add new experience, projects, schools, roles, or bullets that aren't in the baseline
- Invent new skills, even if the JD requires them
- Change dates, organization names, or factual details
- Add metrics or numbers that aren't in the baseline
- Stuff keywords repetitively across many bullets (penalized as keyword stuffing)

**Output format for [TAILOR]:** JSON only, starting with `{` and ending with `}`. No preamble, no markdown code fences, no commentary. The output is fed directly into a CLI that will reject anything else.

═══════════════════════════════════════════════════════════════
BASE UPDATE MODE — thoughtful, with honest pushback and active trimming
═══════════════════════════════════════════════════════════════

When I send a [BASE UPDATE] message, I am telling you about a real change in my life and asking you to incorporate it into my baseline resume well. Your job is NOT find-and-replace. Your job is to help me build the strongest possible baseline given this new information.

This means:

1. **Evaluate the change first.** Before touching the JSON, ask yourself: is this worth adding? Will it strengthen the baseline or weaken it? Some things genuinely don't belong (middle school clubs, very old jobs, marginal coursework, three-line projects with no impact). If you think the change shouldn't be added, tell me so directly and explain your reasoning — then ask if I still want to add it.

2. **Think about where it fits.** Education? Experience? Projects? Leadership? Skills? If a change touches multiple sections, address all of them.

3. **Think about positioning within its section.** A new internship probably goes at the top of experience. A future degree program probably goes above the current high school. A new project probably leads the projects list if it's recent and impressive.

4. **Write strong content for new entries.** Proper resume bullets: action verb + what you did + technologies used + measurable impact (when a real number is available). Match the style and length of existing bullets. Always include the exact technologies used so they are available for future tailoring.

5. **Trim proactively when adding.** If adding new content would push the resume over a single page, identify the weakest existing content and propose what to cut. Be specific: "to fit the new internship, I suggest collapsing the MCC entry into a single line and dropping the second bullet on the Robotics role — both are now lower-signal than what you're adding." Then wait for me to confirm before producing the JSON.

6. **Remove things on request.** [BASE UPDATE] also covers removals: "remove my Notion Planner project," "drop AP CSP from coursework," "shorten my I-Genie bullets to two." Apply these directly.

7. **Make connected updates.** A major change often ripples. New school → summary may need to acknowledge it. Finished internship → end date changes from "Present" to a specific month.

8. **Don't invent specifics.** If I describe a new project vaguely ("a GroupMe bot") without telling you the stack or impact, ask me clarifying questions in plain English instead of inventing details. Or write a minimal entry with only what I told you and flag the gaps.

9. **Push for numbers when adding new entries.** When I describe a new project, internship, or accomplishment, ask me for measurable specifics: "How many users?" "What was the before/after on accuracy?" "How many bullets in the curriculum?" The AI ranking layer rewards measurable evidence heavily, so it's worth asking even when the answers feel small.

10. **It's okay to discuss before producing JSON.** If the change is complex, ambiguous, or has multiple reasonable interpretations, respond conversationally first. Only produce the final JSON once we agree on the approach.

**Output format for [BASE UPDATE]:**
- If clarification, pushback, or trimming discussion is needed: respond in plain English (no JSON yet)
- When ready to commit: respond with JSON only, starting with `{` and ending with `}`. No preamble, no markdown code fences, no commentary. This is what gets fed into the CLI.

After I confirm a base update, treat the new JSON as my baseline for subsequent requests in this chat.

═══════════════════════════════════════════════════════════════
ASK MODE — advice only, no JSON
═══════════════════════════════════════════════════════════════

When I send an [ASK] message, I want your honest opinion on a resume question. I am NOT yet committing to any change. Examples:

- "[ASK] Is my Alpha Detect project still pulling weight, or should I cut it now that I have the internship?"
- "[ASK] Should I add my middle school robotics team?"
- "[ASK] My summary feels generic. What would you change?"
- "[ASK] Is there anything obviously missing from my resume?"
- "[ASK] How does my resume look for a quant internship application?"

Respond conversationally in plain English. Give a clear, honest answer with specific reasoning grounded in what's actually in my baseline. Don't produce JSON. Don't recommend something just because I asked — recommend what's actually best.

If I later decide to act on your advice, I'll send a [BASE UPDATE] message to commit the change.

═══════════════════════════════════════════════════════════════
ATS MODE — self-audit before submitting
═══════════════════════════════════════════════════════════════

When I send an [ATS] message, I will paste a job description (and optionally a tailored JSON I'm about to submit). Run a structured audit using the ATS knowledge from earlier in this prompt. Respond in plain English (no JSON) with:

1. **Top JD keywords I'm hitting.** List the 5-10 highest-value JD keywords and which bullet/section each one appears in.

2. **Top JD keywords I'm missing.** List the keywords that appear in the JD but NOT in my resume. For each one, say whether I truthfully have the underlying experience (in which case the tailored resume should add it) or whether it's an honest gap.

3. **Acronym risk.** Identify any acronym/spelled-out mismatches between the JD and the resume.

4. **Weak bullets.** Identify bullets that lack measurable impact or use vague verbs. Suggest specific rewrites grounded in what's already in my baseline.

5. **Summary strength.** Rate the summary against the JD. Does the first sentence lead with the right keywords? Is it differentiated or generic?

6. **Predicted ATS score range.** Give a rough estimate (e.g., "60-70% match for keyword-based systems, likely higher for semantic systems") with reasoning.

7. **Top 3 specific fixes I should make before submitting.** Concrete, actionable, prioritized.

═══════════════════════════════════════════════════════════════
ACKNOWLEDGEMENT
═══════════════════════════════════════════════════════════════

If you understand these instructions and have parsed my baseline JSON above, respond to THIS first message ONLY with:

Ready. Send [TAILOR] for a job-specific resume, [BASE UPDATE] for a life change, [ASK] for advice, or [ATS] to audit a tailored resume before submitting.
"""


TURN_PROMPTS = """\
Inside an active session, send one of these short messages:


For a tailored resume:
─────────────────────────
[TAILOR]

(paste the job description here, including company, role title, requirements, and nice-to-haves)
─────────────────────────

Claude replies with JSON only. Copy it, return to the CLI, and use 't'.


For a baseline change (add, modify, or remove):
─────────────────────────
[BASE UPDATE]

(describe what changed. Claude will think about where it fits, may push back if it's a weak
addition, and may suggest trimming weaker existing content to make room. Will ask clarifying
questions before producing the final JSON if needed. Examples:

  "I got admitted to NJIT for BS Computer Science, enrolling Fall 2026."

  "I finished my I-Genie internship on Aug 31. Update the end date and write final-form bullets
   about what I actually accomplished: migrated their classifier from TF-IDF to FastText,
   designed LLM relabeling prompts, built Streamlit dashboards on Databricks."

  "Remove the Notion Planner project — it's not pulling weight anymore."

  "Drop AP CSP from my coursework, I want only the strongest courses listed.")
─────────────────────────

Claude may push back, ask questions, or suggest trims first. Once you agree, Claude sends
JSON only. Copy it, return to the CLI, and use 'b'.


For advice without committing to anything:
─────────────────────────
[ASK]

(ask any resume question. Examples:

  "Is my Alpha Detect project still worth keeping?"
  "Should I add my middle school robotics team?"
  "What's the weakest part of my resume right now?"
  "Does this look ready for a quant internship application?")
─────────────────────────

Claude replies in plain English with honest advice. No JSON. If you want to act on the advice,
send a [BASE UPDATE] message after.


For an ATS audit before submitting:
─────────────────────────
[ATS]

(paste the job description, and optionally the tailored JSON you're about to submit.
Claude will audit it against the JD: which keywords you're hitting, which you're missing,
whether acronyms are aligned with the JD, where bullets are weak, predicted score range,
and the top 3 specific fixes before you submit.)
─────────────────────────

Claude replies in plain English with a structured audit. No JSON. Use the feedback to send
another [TAILOR] turn if needed.
"""


def cmd_prompt() -> None:
    """Print one of three prompts: onboarding, session setup, or in-session turn."""
    print()
    print(style("Which prompt do you need?", Style.BOLD))
    print("  [o] Onboarding   — first-time setup, convert a raw resume into JSON")
    print("  [s] Session      — start a new long-running Claude chat (embeds current baseline)")
    print("  [u] Turn (Usage) — show the short message formats used INSIDE a session")
    choice = ask("Choice", default="s").lower()

    print()
    print(style("─── Copy from below into a new Claude chat ───", Style.MAGENTA))
    print()

    if choice.startswith("o"):
        print(ONBOARDING_PROMPT)
    elif choice.startswith("u"):
        print(TURN_PROMPTS)
    else:
        base = latest_base_version()
        if base is None:
            warn("No base resume yet. Run 'init' first, or use the [o]nboarding prompt.")
            return
        data = load_version(base)
        baseline_str = json.dumps(data, indent=2, ensure_ascii=False)
        print(SESSION_PROMPT_TEMPLATE.replace("__BASELINE_JSON__", baseline_str))

    print()
    print(style("─── End of prompt ───", Style.MAGENTA))
    print()


def parse_version(s: str | None) -> int | None:
    if not s:
        warn("Specify a version, e.g. 'v0003' or '3'.")
        return None
    s = s.strip().lstrip("v").lstrip("V")
    try:
        return int(s)
    except ValueError:
        error(f"Not a valid version: {s!r}")
        return None


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------
COMMANDS = {
    "t": "tailor", "tailor": "tailor",
    "b": "base", "base": "base",
    "c": "compile", "compile": "compile",
    "h": "history", "history": "history",
    "s": "show", "show": "show",
    "d": "diff", "diff": "diff",
    "r": "restore", "restore": "restore",
    "e": "edit", "edit": "edit",
    "p": "prompt", "prompt": "prompt",
    "i": "init", "init": "init",
    "?": "help", "help": "help",
    "q": "quit", "quit": "quit", "exit": "quit",
}


def show_menu() -> None:
    print()
    print(style("Commands:", Style.BOLD))
    rows = [
        ("[t] tailor",   "Paste tailored JSON from a Claude chat (forks from current base)"),
        ("[b] base",     "Update your factual baseline (new role, school, project, etc.)"),
        ("[c] compile",  "Recompile current (or 'compile v3') to PDF"),
        ("[h] history",  "Show all versions, bases and tailors"),
        ("[s] show",     "Show details of a version: 'show v3'"),
        ("[d] diff",     "Compare versions: 'diff v3 v5'"),
        ("[r] restore",  "Promote a past version: 'restore v3'"),
        ("[e] edit",     "Open current JSON in $EDITOR (manual tweak)"),
        ("[p] prompt",   "Print onboarding / session-start / turn prompts for Claude chats"),
        ("[i] init",     "Re-initialize from a pasted base JSON"),
        ("[q] quit",     "Exit"),
    ]
    for left, right in rows:
        print(f"  {left:<14} {style(right, Style.GRAY)}")
    print()


def repl() -> None:
    init_storage()
    banner("Resume Manager")
    cur = current_version()
    base = latest_base_version()
    if cur is None:
        warn("No base resume found. Let's set one up.")
        cmd_init()
    else:
        rec = get_version(cur)
        if rec:
            _, created_at, label, _, _, is_base = rec
            label_str = label or "(no label)"
            kind = "base" if is_base else "tailored"
            info(f"Current: v{cur:04d} ({kind}) — {label_str}  ({created_at[:10]})")
        if base is not None and base != cur:
            base_rec = get_version(base)
            if base_rec:
                _, _, base_label, _, _, _ = base_rec
                info(f"Active base: v{base:04d} — {base_label or '(no label)'}")
    show_menu()

    try:
        import readline  # noqa: F401 — enables history, line editing
    except ImportError:
        pass

    while True:
        try:
            raw = input(style("resume> ", Style.CYAN)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        tokens = raw.split()
        cmd_key = tokens[0].lower()
        args = tokens[1:]
        action = COMMANDS.get(cmd_key)
        if action is None:
            warn(f"Unknown command: {cmd_key!r}. Type '?' for help.")
            continue
        try:
            if action == "tailor":
                cmd_tailor()
            elif action == "base":
                cmd_base()
            elif action == "compile":
                cmd_compile(args[0] if args else None)
            elif action == "history":
                cmd_history()
            elif action == "show":
                cmd_show(args[0] if args else None)
            elif action == "diff":
                cmd_diff(args)
            elif action == "restore":
                cmd_restore(args[0] if args else None)
            elif action == "edit":
                cmd_edit()
            elif action == "prompt":
                cmd_prompt()
            elif action == "init":
                cmd_init()
            elif action == "help":
                show_menu()
            elif action == "quit":
                break
        except KeyboardInterrupt:
            print()
            warn("Cancelled.")
        except Exception as e:
            error(f"Unexpected error: {e}")

    print(style("Goodbye.", Style.GRAY))


if __name__ == "__main__":
    repl()