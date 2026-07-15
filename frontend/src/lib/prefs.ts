// Client-side UI preferences, persisted in localStorage (same pattern as theme).
// These are device-local behavior toggles, not account data; the server never
// sees them. Read on load to seed initial UI state; write on change.

export type LandingTab = "edit" | "compare" | "network" | "pdf";
export type EditorMode = "form" | "raw";
export type AssistantMode = "agent" | "copypaste";

const KEYS = {
  landingTab: "pref.landingTab",
  editorMode: "pref.editorMode",
  autoCompile: "pref.autoCompile",
  tourSeen: "pref.tourSeen",
  assistantMode: "pref.assistantMode",
  cpSessionHidden: "pref.cpSessionHidden",
} as const;

const LANDING_TABS: LandingTab[] = ["edit", "compare", "network", "pdf"];

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode); prefs just won't persist */
  }
}

export const prefs = {
  landingTab(): LandingTab {
    const v = read(KEYS.landingTab);
    return (LANDING_TABS as string[]).includes(v || "") ? (v as LandingTab) : "edit";
  },
  setLandingTab(v: LandingTab) {
    write(KEYS.landingTab, v);
  },

  editorMode(): EditorMode {
    return read(KEYS.editorMode) === "raw" ? "raw" : "form";
  },
  setEditorMode(v: EditorMode) {
    write(KEYS.editorMode, v);
  },

  // Auto-compile the live PDF preview on every edit. Default on.
  autoCompile(): boolean {
    return read(KEYS.autoCompile) !== "0";
  },
  setAutoCompile(v: boolean) {
    write(KEYS.autoCompile, v ? "1" : "0");
  },

  // Whether the first-run product tour has been shown.
  tourSeen(): boolean {
    return read(KEYS.tourSeen) === "1";
  },
  setTourSeen(v: boolean) {
    write(KEYS.tourSeen, v ? "1" : "0");
  },

  // Last chosen assistant mode. Null means "not chosen yet" (default by key).
  assistantMode(): AssistantMode | null {
    const v = read(KEYS.assistantMode);
    return v === "agent" || v === "copypaste" ? v : null;
  },
  setAssistantMode(v: AssistantMode) {
    write(KEYS.assistantMode, v);
  },

  // Whether the copy-paste "Set up a chat" section is collapsed.
  cpSessionHidden(): boolean {
    return read(KEYS.cpSessionHidden) === "1";
  },
  setCpSessionHidden(v: boolean) {
    write(KEYS.cpSessionHidden, v ? "1" : "0");
  },
};
