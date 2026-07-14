"""Export the local CLI's data to a single bundle file for the web app.

Reads the legacy ``resume_data/`` store (via the existing ``resume.py``
functions, which stay untouched) and writes ``resume_export.json``. Upload that
file in the web app's Import screen to bring every version across.

Usage:
    python export_cli.py                 # writes ./resume_export.json
    python export_cli.py my_bundle.json  # custom output path
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import resume  # the legacy CLI module; importing it has no side effects

BUNDLE_SCHEMA = "resume-manager/v1"


def build_bundle() -> dict:
    resume.init_storage()
    rows = resume.list_versions()  # (version, created_at, label, json_hash, is_base) desc
    versions = []
    base_so_far: int | None = None
    for version, created_at, label, json_hash, is_base in sorted(rows, key=lambda r: r[0]):
        rec = resume.get_version(version)  # (version, created_at, label, jd_text, json_hash, is_base)
        jd_text = rec[3] if rec else None
        data = resume.load_version(version)
        versions.append(
            {
                "version": version,
                "created_at": created_at,
                "label": label,
                "jd_text": jd_text,
                "json_hash": json_hash,
                "is_base": bool(is_base),
                "forked_from": None if is_base else base_so_far,
                "data": data,
            }
        )
        if is_base:
            base_so_far = version
    return {
        "schema": BUNDLE_SCHEMA,
        "current_version": resume.current_version(),
        "versions": versions,
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("resume_export.json")
    bundle = build_bundle()
    if not bundle["versions"]:
        print("No versions found in resume_data/. Nothing to export.")
        return
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported {len(bundle['versions'])} version(s) to {out.resolve()}")
    print("Upload this file in the web app: Settings -> Import from CLI.")


if __name__ == "__main__":
    main()
