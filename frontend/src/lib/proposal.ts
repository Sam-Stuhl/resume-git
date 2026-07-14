import type { ChatProposal, Resume, Section, SectionChange } from "../types";

/** Matches the backend's `core.diff._section_key` so accept-keys line up. */
export function sectionKey(sec: Section): string {
  return `${sec.type ?? ""}::${sec.title ?? ""}`;
}

/**
 * Merge the *accepted* section changes of a proposal onto the live working
 * resume. When every change is accepted we return the proposal's full document
 * verbatim (exact, preserves ordering); otherwise we apply the accepted units
 * onto a clone of `current` and leave rejected sections as they are.
 */
export function mergeProposal(
  current: Resume,
  proposal: ChatProposal,
  accepted: Set<string>
): Resume {
  const changes = proposal.section_changes;
  if (changes.length > 0 && changes.every((c) => accepted.has(c.key))) {
    return proposal.data;
  }

  const result: Resume = JSON.parse(JSON.stringify(current ?? {}));
  result.personal = result.personal ?? {};
  result.sections = result.sections ? [...result.sections] : [];

  for (const ch of changes) {
    if (!accepted.has(ch.key)) continue;
    applyChange(result, ch);
  }
  return result;
}

function applyChange(result: Resume, ch: SectionChange): void {
  if (ch.key === "personal") {
    result.personal = (ch.after ?? {}) as Resume["personal"];
    return;
  }
  const sections = result.sections ?? (result.sections = []);
  if (ch.status === "added") {
    sections.push(ch.after as Section);
  } else if (ch.status === "removed") {
    result.sections = sections.filter((s) => sectionKey(s) !== ch.key);
  } else {
    // modified: replace in place, or append if it isn't present yet.
    const i = sections.findIndex((s) => sectionKey(s) === ch.key);
    if (i >= 0) sections[i] = ch.after as Section;
    else sections.push(ch.after as Section);
  }
}
