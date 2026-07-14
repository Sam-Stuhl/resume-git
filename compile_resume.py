#!/usr/bin/env python3
"""
Resume Compiler — JSON to LaTeX to PDF

Takes a structured JSON resume and compiles it into a polished, ATS-friendly
PDF using a Jake's Resume-inspired LaTeX template.

Usage:
    python compile_resume.py                              # uses resume_data.json
    python compile_resume.py path/to/data.json            # custom input
    python compile_resume.py data.json output_name        # custom output name

Requirements:
    - Python 3.8+
    - A LaTeX distribution with pdflatex (MacTeX, TeX Live, MiKTeX)
      Install: https://www.latex-project.org/get/

The script is the rendering layer. The JSON is your single source of truth —
this is what an agent edits when tailoring your resume to a job posting.
"""

import json
import subprocess
import sys
import shutil
from pathlib import Path


# ---------------------------------------------------------------------------
# LaTeX escaping
# ---------------------------------------------------------------------------
LATEX_SPECIAL_CHARS = {
    '\\': r'\textbackslash{}',
    '&':  r'\&',
    '%':  r'\%',
    '$':  r'\$',
    '#':  r'\#',
    '_':  r'\_',
    '{':  r'\{',
    '}':  r'\}',
    '~':  r'\textasciitilde{}',
    '^':  r'\textasciicircum{}',
}


def latex_escape(text: str) -> str:
    """Escape LaTeX special characters in user-provided strings."""
    if text is None:
        return ''
    # Backslash must come first so we don't double-escape
    result = text.replace('\\', LATEX_SPECIAL_CHARS['\\'])
    for char, escaped in LATEX_SPECIAL_CHARS.items():
        if char == '\\':
            continue
        result = result.replace(char, escaped)
    return result


# ---------------------------------------------------------------------------
# LaTeX preamble — Jake's Resume style, ATS-friendly
# ---------------------------------------------------------------------------
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

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.6in}
\addtolength{\evensidemargin}{-0.6in}
\addtolength{\textwidth}{1.2in}
\addtolength{\topmargin}{-.85in}
\addtolength{\textheight}{1.6in}

\urlstyle{same}

\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

% Make machine readable (critical for ATS)
\pdfgentounicode=1

%-------------------------
% Custom commands
\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\setlength{\footskip}{4.08003pt}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
"""


def render_header(personal: dict) -> str:
    name = latex_escape(personal['name'])
    email = latex_escape(personal['email'])
    phone = latex_escape(personal['phone'])
    github = personal['github']
    linkedin = personal['linkedin']
    return rf"""
\begin{{center}}
    \textbf{{\Huge \scshape {name}}} \\ \vspace{{1pt}}
    \small {phone} $|$ \href{{mailto:{email}}}{{\underline{{{email}}}}} $|$
    \href{{https://{linkedin}}}{{\underline{{{latex_escape(linkedin)}}}}} $|$
    \href{{https://{github}}}{{\underline{{{latex_escape(github)}}}}}
\end{{center}}
"""


def render_summary(summary: str) -> str:
    if not summary:
        return ''
    return rf"""
\section*{{Summary}}
\small {latex_escape(summary)}
\vspace{{2pt}}
"""


def render_experience(experience: list) -> str:
    if not experience:
        return ''
    out = ['\n\\section{Experience}', '\\resumeSubHeadingListStart']
    for job in experience:
        title = latex_escape(job['title'])
        org = latex_escape(job['organization'])
        location = latex_escape(job.get('location', ''))
        start = latex_escape(job.get('start_date', ''))
        end = latex_escape(job.get('end_date', ''))
        date_range = f"{start} -- {end}" if start and end else (start or end)
        out.append(rf"\resumeSubheading{{{title}}}{{{date_range}}}{{{org}}}{{{location}}}")
        if job.get('bullets'):
            out.append(r'\resumeItemListStart')
            for bullet in job['bullets']:
                out.append(rf"\resumeItem{{{latex_escape(bullet)}}}")
            out.append(r'\resumeItemListEnd')
    out.append(r'\resumeSubHeadingListEnd')
    return '\n'.join(out)


def render_projects(projects: list) -> str:
    if not projects:
        return ''
    out = ['\n\\section{Projects}', '\\resumeSubHeadingListStart']
    for proj in projects:
        name = latex_escape(proj['name'])
        stack = latex_escape(proj.get('stack', ''))
        heading = rf"\textbf{{{name}}} $|$ \emph{{{stack}}}" if stack else rf"\textbf{{{name}}}"
        out.append(rf"\resumeProjectHeading{{{heading}}}{{}}")
        if proj.get('bullets'):
            out.append(r'\resumeItemListStart')
            for bullet in proj['bullets']:
                out.append(rf"\resumeItem{{{latex_escape(bullet)}}}")
            out.append(r'\resumeItemListEnd')
    out.append(r'\resumeSubHeadingListEnd')
    return '\n'.join(out)


def render_leadership(leadership: list) -> str:
    if not leadership:
        return ''
    out = ['\n\\section{Leadership \\& Extracurriculars}', '\\resumeSubHeadingListStart']
    for role in leadership:
        title = latex_escape(role['title'])
        org = latex_escape(role['organization'])
        location = latex_escape(role.get('location', ''))
        start = latex_escape(role.get('start_date', ''))
        end = latex_escape(role.get('end_date', ''))
        date_range = f"{start} -- {end}" if start and end else (start or end)
        out.append(rf"\resumeSubheading{{{title}}}{{{date_range}}}{{{org}}}{{{location}}}")
        if role.get('bullets'):
            out.append(r'\resumeItemListStart')
            for bullet in role['bullets']:
                out.append(rf"\resumeItem{{{latex_escape(bullet)}}}")
            out.append(r'\resumeItemListEnd')
    out.append(r'\resumeSubHeadingListEnd')
    return '\n'.join(out)


def render_skills(skills: dict) -> str:
    if not skills:
        return ''
    rows = []
    for category, items in skills.items():
        rows.append(rf"\textbf{{{latex_escape(category)}}}{{: {latex_escape(items)}}}")
    body = ' \\\\\n     '.join(rows)
    return rf"""
\section{{Technical Skills}}
 \begin{{itemize}}[leftmargin=0.15in, label={{}}]
    \small{{\item{{
     {body} \\
    }}}}
 \end{{itemize}}
"""


def render_education(education: list) -> str:
    if not education:
        return ''
    out = ['\n\\section{Education}', '\\resumeSubHeadingListStart']
    for ed in education:
        school = latex_escape(ed['school'])
        location = latex_escape(ed.get('location', ''))
        gpa = latex_escape(ed.get('gpa', ''))
        gpa_str = f"GPA: {gpa}" if gpa else ''
        start = latex_escape(ed.get('start_date', ''))
        end = latex_escape(ed.get('end_date', ''))
        date_range = f"{start} -- {end}" if start and end else (start or end)
        out.append(rf"\resumeSubheading{{{school}}}{{{location}}}{{{gpa_str}}}{{{date_range}}}")
        if ed.get('coursework'):
            out.append(r'\resumeItemListStart')
            out.append(rf"\resumeItem{{\textbf{{Relevant Coursework:}} {latex_escape(ed['coursework'])}}}")
            out.append(r'\resumeItemListEnd')
    out.append(r'\resumeSubHeadingListEnd')
    return '\n'.join(out)


def build_latex(data: dict) -> str:
    """Assemble the full LaTeX document from JSON resume data."""
    parts = [PREAMBLE, r'\begin{document}']
    parts.append(render_header(data['personal']))
    if data.get('summary'):
        parts.append(render_summary(data['summary']))
    parts.append(render_experience(data.get('experience', [])))
    parts.append(render_projects(data.get('projects', [])))
    parts.append(render_leadership(data.get('leadership', [])))
    parts.append(render_skills(data.get('skills', {})))
    parts.append(render_education(data.get('education', [])))
    parts.append(r'\end{document}')
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------
def compile_pdf(tex_source: str, output_name: str, working_dir: Path) -> Path:
    """Compile a LaTeX string to PDF using pdflatex."""
    if shutil.which('pdflatex') is None:
        raise RuntimeError(
            "pdflatex not found. Install a LaTeX distribution:\n"
            "  macOS:   brew install --cask mactex-no-gui\n"
            "  Ubuntu:  sudo apt install texlive-latex-recommended texlive-fonts-recommended\n"
            "  Windows: install MiKTeX from https://miktex.org/"
        )

    working_dir.mkdir(parents=True, exist_ok=True)
    tex_path = working_dir / f"{output_name}.tex"
    tex_path.write_text(tex_source, encoding='utf-8')

    # Run twice for correct cross-references (standard LaTeX practice)
    for run in range(2):
        result = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', tex_path.name],
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log_path = working_dir / f"{output_name}.log"
            tail = ''
            if log_path.exists():
                tail = '\n'.join(log_path.read_text(errors='ignore').splitlines()[-30:])
            raise RuntimeError(
                f"pdflatex failed on run {run + 1}.\n"
                f"Last lines of log:\n{tail}"
            )

    pdf_path = working_dir / f"{output_name}.pdf"
    if not pdf_path.exists():
        raise RuntimeError("Compilation completed but no PDF was produced.")
    return pdf_path


def cleanup_build_artifacts(working_dir: Path, output_name: str) -> None:
    """Remove .aux, .log, .out — keep .tex and .pdf."""
    for ext in ('.aux', '.log', '.out', '.fls', '.fdb_latexmk'):
        artifact = working_dir / f"{output_name}{ext}"
        if artifact.exists():
            artifact.unlink()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]
    json_path = Path(args[0]) if len(args) >= 1 else Path('resume_data.json')
    output_name = args[1] if len(args) >= 2 else 'resume'

    if not json_path.exists():
        print(f"Error: {json_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Reading: {json_path}")
    tex_source = build_latex(data)

    build_dir = Path('build')
    print(f"Compiling to PDF in: {build_dir}/")
    pdf_path = compile_pdf(tex_source, output_name, build_dir)
    cleanup_build_artifacts(build_dir, output_name)

    final_pdf = Path(f"{output_name}.pdf")
    shutil.copy(pdf_path, final_pdf)
    print(f"Done: {final_pdf.resolve()}")


if __name__ == '__main__':
    main()
