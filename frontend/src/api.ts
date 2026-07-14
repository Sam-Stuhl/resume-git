import type {
  DiffOut, Me, TailorPreview, VersionDetail, VersionMeta,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    credentials: "include",
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  me: () => req<Me>("/api/me"),
  settings: () => req<Me>("/api/settings"),
  saveSettings: (b: { default_model?: string; ai_enabled?: boolean }) =>
    req("/api/settings", { method: "PUT", body: JSON.stringify(b) }),
  saveApiKey: (api_key: string) =>
    req("/api/settings/api-key", { method: "PUT", body: JSON.stringify({ api_key }) }),

  versions: () => req<VersionMeta[]>("/api/versions"),
  version: (v: number) => req<VersionDetail>(`/api/versions/${v}`),
  current: () => req<VersionDetail>("/api/versions/current"),
  setCurrent: (version: number) =>
    req("/api/versions/current", { method: "PUT", body: JSON.stringify({ version }) }),

  createBase: (data: unknown, label: string | null) =>
    req<VersionMeta>("/api/base", { method: "POST", body: JSON.stringify({ data, label }) }),
  createTailor: (data: unknown, label: string | null, jd_text: string | null) =>
    req<VersionMeta>("/api/tailor", {
      method: "POST",
      body: JSON.stringify({ data, label, jd_text }),
    }),
  tailorPreview: (jd_text: string, model?: string) =>
    req<TailorPreview>("/api/tailor/preview", {
      method: "POST",
      body: JSON.stringify({ jd_text, model }),
    }),
  restore: (v: number) => req<VersionMeta>(`/api/versions/${v}/restore`, { method: "POST" }),
  diff: (a: number, b: number) => req<DiffOut>(`/api/versions/${a}/diff/${b}`),

  sessionPrompt: () => req<{ prompt: string }>("/api/prompts/session"),

  // Compile unsaved data to a PDF blob for the live preview.
  previewPdf: async (data: unknown): Promise<Blob> => {
    const res = await fetch("/api/preview/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ data }),
    });
    if (!res.ok) {
      let detail: unknown;
      try {
        detail = (await res.json()).detail;
      } catch {
        detail = res.statusText;
      }
      throw new ApiError(res.status, detail);
    }
    return res.blob();
  },

  importBundle: (
    bundle: { versions: unknown[]; current_version?: number | null },
    replace: boolean
  ) =>
    req<{ imported: number }>("/api/import", {
      method: "POST",
      body: JSON.stringify({
        versions: bundle.versions,
        current_version: bundle.current_version ?? null,
        replace,
      }),
    }),
};

export const pdfUrl = {
  current: () => "/api/pdf/current",
  version: (v: number) => `/api/versions/${v}/pdf`,
};
