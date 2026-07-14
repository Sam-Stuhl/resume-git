"""Build-time smoke test: prove the image's TeX packages compile the template.

Prints the LaTeX log tail on failure so a missing package is diagnosable from
the Docker build output.
"""

import json
import sys

from core.pdf import CompileError, compile_pdf_bytes

data = json.load(open("samples/sample_resume.json"))
try:
    pdf = compile_pdf_bytes(data)
except CompileError as e:
    print("PDF smoke test FAILED:", e, file=sys.stderr)
    if e.log_tail:
        print("--- pdflatex log tail ---", file=sys.stderr)
        print(e.log_tail, file=sys.stderr)
    sys.exit(1)

assert pdf[:4] == b"%PDF", "output is not a PDF"
print(f"PDF smoke test OK — {len(pdf)} bytes")
