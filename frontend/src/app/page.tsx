export const dynamic = "force-dynamic";

type BackendStatus = { ok: true } | { ok: false; message: string };

async function getBackendStatus(): Promise<BackendStatus> {
  const baseUrl = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${baseUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) {
      return { ok: false, message: `Backend responded with HTTP ${res.status}` };
    }
    const body = (await res.json()) as { status?: unknown };
    return body.status === "ok"
      ? { ok: true }
      : { ok: false, message: "Backend reported an unexpected status" };
  } catch {
    return { ok: false, message: "Backend is unreachable" };
  }
}

export default async function DashboardPage() {
  const backend = await getBackendStatus();

  return (
    <>
      <header className="page-header">
        <h1>Dashboard</h1>
        <p className="muted">Define an ideal customer profile and review matching companies and contacts.</p>
      </header>

      <section className="card status-card" aria-live="polite">
        <span className={`status-dot ${backend.ok ? "status-ok" : "status-error"}`} aria-hidden="true" />
        <div>
          <strong>Backend API</strong>
          <p className="muted">{backend.ok ? "Connected and healthy" : backend.message}</p>
        </div>
      </section>

      <section className="card">
        <h2>ICP search</h2>
        <p className="muted">
          The search form will appear here in a later milestone. Initial searches will use clearly
          labeled demonstration data, not real contact records.
        </p>
      </section>

      <section className="card">
        <h2>Results</h2>
        <div className="empty-state">No searches yet.</div>
      </section>
    </>
  );
}
