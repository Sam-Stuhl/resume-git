---
name: ats
description: Audit a version against a job description before you submit.
allowed_tools: [list_versions, get_version, diff_versions, get_current]
---
ATS audit mode. Follow the [ATS] guidance in your system prompt: audit the current (or a
named) version against the pasted job description — keywords hit/missing, acronym
alignment, weak bullets, a predicted score range, and the top fixes. Read versions as
needed. Respond in plain English. Do NOT call propose_resume — this is an audit.
