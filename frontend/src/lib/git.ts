import type { VersionMeta } from "../types";

/** Turn a friendly label into a git-style branch slug. */
export function slugify(label: string | null | undefined): string {
  const s = (label || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
  return s || "tailored";
}

/** Short commit ref like `v0006`. */
export function ref(version: number): string {
  return "v" + String(version).padStart(4, "0");
}

/** The branch a version lives on: `main` for base commits, else the slug. */
export function branchName(v: VersionMeta): string {
  return v.is_base ? "main" : slugify(v.label);
}

/** Human date, compact. */
export function shortDate(iso: string): string {
  return iso ? iso.replace("T", " ").slice(0, 16) : "";
}
