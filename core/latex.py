"""JSON resume -> LaTeX source.

A faithful port of the renderers in the original ``resume.py`` (lines ~382-555).
The template is a Jake's-Resume-inspired, ATS-friendly single-page layout. The
functions are pure: they take resume ``dict`` data and return LaTeX strings.
"""

from __future__ import annotations

from core.sections import normalize

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
    # Tolerant of partial data so the live preview never crashes mid-edit.
    name = tex_escape(personal.get("name", ""))
    email = tex_escape(personal.get("email", ""))
    phone = tex_escape(personal.get("phone", ""))
    github = personal.get("github", "")
    linkedin = personal.get("linkedin", "")
    return (
        r"\begin{center}" + "\n"
        + rf"    \textbf{{\Huge \scshape {name}}} \\ \vspace{{1pt}}" + "\n"
        + rf"    \small {phone} $|$ \href{{mailto:{email}}}{{\underline{{{email}}}}} $|$" + "\n"
        + rf"    \href{{https://{linkedin}}}{{\underline{{{tex_escape(linkedin)}}}}} $|$" + "\n"
        + rf"    \href{{https://{github}}}{{\underline{{{tex_escape(github)}}}}}" + "\n"
        + r"\end{center}"
    )


def render_text(title: str, text: str) -> str:
    if not text:
        return ""
    return f"\n\\section*{{{tex_escape(title)}}}\n\\small {tex_escape(text)}\n\\vspace{{2pt}}\n"


def render_role_block(items: list, section_title: str) -> str:
    if not items:
        return ""
    out = [f"\n\\section{{{tex_escape(section_title)}}}", r"\resumeSubHeadingListStart"]
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


def render_projects(entries: list, title: str = "Projects") -> str:
    if not entries:
        return ""
    out = [f"\n\\section{{{tex_escape(title)}}}", r"\resumeSubHeadingListStart"]
    for p in entries:
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


def render_skills(groups: list, title: str = "Technical Skills") -> str:
    if not groups:
        return ""
    rows = [
        rf"\textbf{{{tex_escape(g.get('category', ''))}}}{{: {tex_escape(g.get('items', ''))}}}"
        for g in groups
    ]
    body = " \\\\\n     ".join(rows)
    return (
        f"\n\\section{{{tex_escape(title)}}}\n"
        " \\begin{itemize}[leftmargin=0.15in, label={}]\n"
        f"    \\small{{\\item{{\n     {body} \\\\\n    }}}}\n"
        " \\end{itemize}\n"
    )


def render_education(entries: list, title: str = "Education") -> str:
    if not entries:
        return ""
    out = [f"\n\\section{{{tex_escape(title)}}}", r"\resumeSubHeadingListStart"]
    for ed in entries:
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


def render_bullets(title: str, items: list) -> str:
    if not items:
        return ""
    out = [f"\n\\section{{{tex_escape(title)}}}", r"\resumeSubHeadingListStart", r"\resumeItemListStart"]
    for item in items:
        out.append(rf"\resumeItem{{{tex_escape(item)}}}")
    out.append(r"\resumeItemListEnd")
    out.append(r"\resumeSubHeadingListEnd")
    return "\n".join(out)


_RENDERERS = {
    "text": lambda s: render_text(s.get("title", ""), s.get("text", "")),
    "roles": lambda s: render_role_block(s.get("entries", []), s.get("title", "")),
    "projects": lambda s: render_projects(s.get("entries", []), s.get("title", "Projects")),
    "skills": lambda s: render_skills(s.get("groups", []), s.get("title", "Technical Skills")),
    "education": lambda s: render_education(s.get("entries", []), s.get("title", "Education")),
    "bullets": lambda s: render_bullets(s.get("title", ""), s.get("items", [])),
}


def render_section(sec: dict) -> str:
    """Dispatch a single typed section to its renderer. Unknown types render nothing."""
    renderer = _RENDERERS.get(sec.get("type", ""))
    return renderer(sec) if renderer else ""


def build_latex(data: dict) -> str:
    """Assemble the full LaTeX document from the (normalized) section model."""
    data = normalize(data)
    parts = [PREAMBLE, r"\begin{document}", render_header(data["personal"])]
    for sec in data["sections"]:
        rendered = render_section(sec)
        if rendered:
            parts.append(rendered)
    parts.append(r"\end{document}")
    return "\n".join(parts)
