"""JSON resume -> LaTeX source.

A faithful port of the renderers in the original ``resume.py`` (lines ~382-555).
The template is a Jake's-Resume-inspired, ATS-friendly single-page layout. The
functions are pure: they take resume ``dict`` data and return LaTeX strings.
"""

from __future__ import annotations

LATEX_SPECIAL_CHARS = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def tex_escape(text: str) -> str:
    """Escape LaTeX special characters in user-provided strings."""
    if not text:
        return ""
    # Backslash first so we don't double-escape the replacements.
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
        out.append(rf"\resumeSubheading{{{school}}}{{{date_range}}}{{{gpa_str}}}{{{location}}}")
        if ed.get("coursework"):
            out.append(r"\resumeItemListStart")
            out.append(rf"\resumeItem{{\textbf{{Relevant Coursework:}} {tex_escape(ed['coursework'])}}}")
            out.append(r"\resumeItemListEnd")
    out.append(r"\resumeSubHeadingListEnd")
    return "\n".join(out)


def build_latex(data: dict) -> str:
    """Assemble the full LaTeX document from JSON resume data."""
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
