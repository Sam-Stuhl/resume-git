export interface Me {
  email: string;
  ai_enabled: boolean;
  default_model: string;
  credential_kind?: "api" | "oauth" | null;
}

export interface VersionMeta {
  version: number;
  created_at: string;
  label: string | null;
  is_base: boolean;
  forked_from: number | null;
  json_hash: string;
}

export interface VersionDetail extends VersionMeta {
  jd_text: string | null;
  data: Record<string, unknown>;
}

export interface DiffLine {
  tag: "meta" | "hunk" | "add" | "del" | "ctx";
  text: string;
}

export interface DiffOut {
  summary: string[];
  lines: DiffLine[];
}

export interface TailorPreview {
  data: Record<string, unknown>;
  diff: DiffLine[];
  summary: string[];
}

// ── Resume content shape (edited by the section forms) ──
export interface Personal {
  name?: string; email?: string; phone?: string; github?: string; linkedin?: string;
}
export interface Role {
  title?: string; organization?: string; location?: string;
  start_date?: string; end_date?: string; bullets?: string[];
}
export interface Project {
  name?: string; stack?: string; bullets?: string[];
}
export interface Education {
  school?: string; location?: string; gpa?: string;
  start_date?: string; end_date?: string; coursework?: string;
}
export interface SkillGroup { category?: string; items?: string; }

export type SectionType = "text" | "roles" | "projects" | "skills" | "education" | "bullets";

// A single flexible interface (not a strict union) keeps the editor simple;
// the backend validates the per-type shape.
export interface Section {
  type: SectionType;
  title: string;
  text?: string;
  entries?: (Role | Project | Education)[];
  groups?: SkillGroup[];
  items?: string[];
}

export interface Resume {
  personal?: Personal;
  sections?: Section[];
}

// ── Resume Assistant chat ──
export interface SectionChange {
  key: string;
  title: string;
  status: "added" | "removed" | "modified";
  before: unknown;
  after: unknown;
  diff: DiffLine[];
}

export interface ChatProposal {
  data: Resume;
  intent: "tailor" | "base_update" | null;
  summary: string[];
  diff: DiffLine[];
  section_changes: SectionChange[];
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  proposal: ChatProposal | null;
  created_at: string;
}

export interface Skill { name: string; description: string; }
export interface ToolStep { name: string; summary: string; }
export interface AgentAction { tool: "checkout" | "restore"; args: Record<string, number>; summary: string; }
