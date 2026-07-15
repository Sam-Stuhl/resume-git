---
name: tailor
description: Adapt your resume to a job and open it as a branch.
allowed_tools: [list_versions, get_version, diff_versions, get_current, propose_resume]
---
Tailor mode. Follow the [TAILOR] guidance in your system prompt to adapt the resume to
the pasted job description, truthfully. Read the baseline/history as needed. When the
tailored resume is ready, call propose_resume with intent="tailor", the COMPLETE
{personal, sections} document, and a `branch_name` — a short slug from the company/role
(e.g. "halcyon-backend", "stripe-swe-intern"). Add one sentence explaining what you changed.
