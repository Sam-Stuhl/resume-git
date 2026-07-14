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
