import { cookies } from "next/headers";
import type { SessionInfo } from "./types";

const SESSION_COOKIE = "ilf_session";

export type SessionResult =
  | { state: "authenticated"; session: SessionInfo }
  | { state: "anonymous" }
  | { state: "unavailable" };

/**
 * Server-side session check against the backend. Use only in server components.
 * When sign-in is turned off the backend answers with the shared workspace user.
 */
export async function getSession(): Promise<SessionResult> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  const headers: Record<string, string> = { accept: "application/json" };
  if (token) headers.cookie = `${SESSION_COOKIE}=${token}`;

  const baseUrl = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${baseUrl}/api/auth/me`, {
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (res.status === 401) return { state: "anonymous" };
    if (!res.ok) return { state: "unavailable" };
    return { state: "authenticated", session: (await res.json()) as SessionInfo };
  } catch {
    return { state: "unavailable" };
  }
}
