import type {
  ChatMessage, ChatProposal, DiffOut, Me, TailorPreview, VersionDetail, VersionMeta,
} from "./types";

export interface ChatStreamHandlers {
  onDelta: (text: string) => void;
  onProposal: (proposal: ChatProposal) => void;
  onError: (message: string) => void;
  onDone: () => void;
}

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

  // ── Resume Copilot chat ──
  chatHistory: (thread: string) =>
    req<ChatMessage[]>(`/api/chat/${encodeURIComponent(thread)}`),
  clearChat: (thread: string) =>
    req(`/api/chat/${encodeURIComponent(thread)}`, { method: "DELETE" }),

  // Stream one assistant turn over SSE, dispatching frames to handlers.
  chatStream: async (
    thread: string,
    body: { message: string; model?: string; current_data?: unknown },
    h: ChatStreamHandlers
  ): Promise<void> => {
    const res = await fetch(`/api/chat/${encodeURIComponent(thread)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    if (!res.ok || !res.body) {
      let detail: unknown;
      try {
        detail = (await res.json()).detail;
      } catch {
        detail = res.statusText;
      }
      throw new ApiError(res.status, detail);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = frame.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const evt = JSON.parse(line.slice(6)) as { type: string; data: unknown };
        if (evt.type === "delta") h.onDelta(evt.data as string);
        else if (evt.type === "proposal") h.onProposal(evt.data as ChatProposal);
        else if (evt.type === "error") h.onError(evt.data as string);
        else if (evt.type === "done") h.onDone();
      }
    }
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
