import type { Prospect } from "./types";

export function fullName(p: Pick<Prospect, "first_name" | "last_name">): string {
  return [p.first_name, p.last_name].filter(Boolean).join(" ") || "—";
}

export function location(p: Pick<Prospect, "city" | "state" | "country">): string {
  return [p.city, p.state, p.country].filter(Boolean).join(", ") || "—";
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function recordKey(p: Pick<Prospect, "provider" | "provider_record_id">): string {
  return `${p.provider}:${p.provider_record_id}`;
}

export function safeHttpUrl(url: string | null): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}
