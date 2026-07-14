export interface Me {
  email: string;
  ai_enabled: boolean;
  default_model: string;
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
export interface Resume {
  personal?: Personal;
  summary?: string;
  experience?: Role[];
  projects?: Project[];
  leadership?: Role[];
  skills?: Record<string, string>;
  education?: Education[];
}
