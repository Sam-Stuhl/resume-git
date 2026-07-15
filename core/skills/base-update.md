---
name: base-update
description: Apply a real life change to your baseline resume.
allowed_tools: [list_versions, get_version, diff_versions, get_current, propose_resume]
---
Base-update mode. Follow the [BASE UPDATE] guidance in your system prompt to incorporate
a real life change (or removal) into the baseline. Read the baseline/history as needed.
When ready, call propose_resume with intent="base_update" and the COMPLETE updated
{personal, sections} document, plus one sentence explaining what you changed.
