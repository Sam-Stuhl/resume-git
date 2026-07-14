"""Unit tests for the pure core library."""

import copy
import json
from pathlib import Path

import pytest

from core import schema
from core.diff import diff_lines, section_changes, summarize_changes
from core.latex import build_latex, tex_escape
from core.pdf import compile_pdf_bytes, compute_archive_name, compute_pdf_name, pdflatex_available
from core.util import hash_json

SAMPLE = json.loads(
    (Path(__file__).resolve().parent.parent / "samples" / "sample_resume.json").read_text()
)


def test_hash_json_stable_and_order_independent():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert hash_json(a) == hash_json(b)
    assert hash_json(a) != hash_json({"x": 1, "y": 3})


def test_schema_accepts_sample():
    assert schema.validate(copy.deepcopy(SAMPLE)) is not None


@pytest.mark.parametrize(
    "bad",
    [
        {"summary": "x"},                                              # no personal.name
        {"personal": {"name": ""}},                                   # empty name
        {"personal": {"name": "A"}, "sections": [{"type": "nope"}]},   # unknown section type
        {"personal": {"name": "A"}, "sections": [{"type": "roles", "entries": [{"title": "x"}]}]},  # role missing org
    ],
)
def test_schema_rejects(bad):
    with pytest.raises(schema.SchemaError):
        schema.validate(bad)


def test_normalize_legacy_to_sections():
    from core.sections import normalize

    norm = normalize(SAMPLE)
    assert "personal" in norm and isinstance(norm["sections"], list)
    types = [s["type"] for s in norm["sections"]]
    # sample has summary, experience, projects, leadership, skills, education
    assert types == ["text", "roles", "projects", "roles", "skills", "education"]
    # idempotent: normalizing the section model returns it unchanged in shape
    assert normalize(norm)["sections"] == norm["sections"]


def test_bullets_section_compiles():
    data = {"personal": {"name": "Jordan Sample"}, "sections": [
        {"type": "bullets", "title": "Certifications", "items": ["AWS Certified", "CKA"]},
    ]}
    schema.validate(data)
    tex = build_latex(data)
    assert "Certifications" in tex and "AWS Certified" in tex
    if pdflatex_available():
        pdf = compile_pdf_bytes(data)
        assert pdf[:4] == b"%PDF"


def test_all_section_types_compile():
    # A resume exercising every type must produce a valid PDF, not just valid text.
    data = {"personal": {"name": "Jordan Sample", "email": "j@x.com"}, "sections": [
        {"type": "text", "title": "Summary", "text": "Engineer."},
        {"type": "roles", "title": "Experience", "entries": [
            {"title": "SWE", "organization": "Acme", "bullets": ["Built things"]}]},
        {"type": "projects", "title": "Projects", "entries": [
            {"name": "Thing", "stack": "Py", "bullets": ["Did it"]}]},
        {"type": "skills", "title": "Skills", "groups": [{"category": "Lang", "items": "Python"}]},
        {"type": "education", "title": "Education", "entries": [{"school": "State U"}]},
        {"type": "bullets", "title": "Awards", "items": ["Dean's List"]},
    ]}
    schema.validate(data)
    if pdflatex_available():
        assert compile_pdf_bytes(data)[:4] == b"%PDF"


def test_tex_escape_specials():
    assert tex_escape("a & b % c _ d # e $ f") == r"a \& b \% c \_ d \# e \$ f"


def test_build_latex_contains_document():
    tex = build_latex(SAMPLE)
    assert r"\begin{document}" in tex and r"\end{document}" in tex
    assert "Jordan Sample" in tex


def test_summarize_and_diff():
    new = copy.deepcopy(SAMPLE)
    new["summary"] = "Different."
    changes = summarize_changes(SAMPLE, new)
    assert any("Summary" in c for c in changes)
    tags = {line["tag"] for line in diff_lines(SAMPLE, new)}
    assert "add" in tags and "del" in tags


def test_section_changes_add_remove_modify_personal():
    current = {
        "personal": {"name": "Jordan Sample", "email": "j@x.com"},
        "sections": [
            {"type": "text", "title": "Summary", "text": "Old summary."},
            {"type": "bullets", "title": "Awards", "items": ["Dean's List"]},
        ],
    }
    proposed = {
        "personal": {"name": "Jordan Sample", "email": "new@x.com"},  # modified
        "sections": [
            {"type": "text", "title": "Summary", "text": "New summary."},  # modified
            {"type": "skills", "title": "Skills",                          # added
             "groups": [{"category": "Lang", "items": "Python"}]},
            # "Awards" dropped -> removed
        ],
    }
    changes = {(c["key"], c["status"]) for c in section_changes(current, proposed)}
    assert ("personal", "modified") in changes
    assert ("text::Summary", "modified") in changes
    assert ("skills::Skills", "added") in changes
    assert ("bullets::Awards", "removed") in changes
    # Each change carries a non-empty tagged diff.
    for c in section_changes(current, proposed):
        assert isinstance(c["diff"], list) and c["diff"]

    # No changes -> empty list.
    assert section_changes(current, current) == []


def test_pdf_name():
    assert compute_pdf_name(SAMPLE).startswith("jsample_")
    assert compute_archive_name(SAMPLE, 7).endswith("_v0007.pdf")


@pytest.mark.skipif(not pdflatex_available(), reason="pdflatex not installed")
def test_compile_produces_pdf():
    from core.pdf import compile_pdf_bytes

    pdf = compile_pdf_bytes(SAMPLE)
    assert pdf[:4] == b"%PDF"
