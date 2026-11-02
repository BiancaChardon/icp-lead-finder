"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Pagination } from "@/components/Pagination";
import { ResultsTable } from "@/components/ResultsTable";
import { useAuthRequired } from "@/components/UserContext";
import { apiJson, apiRequest, downloadCsv, errorText } from "@/lib/api";
import { fullName } from "@/lib/format";
import type { Page, SavedLead } from "@/lib/types";

const PER_PAGE = 25;

export default function SavedLeadsPage() {
  const authRequired = useAuthRequired();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<SavedLead> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const res = await apiJson<Page<SavedLead>>(`/api/leads?page=${p}&per_page=${PER_PAGE}`);
      if (res.items.length === 0 && p > 1) {
        setPage(p - 1);
        return;
      }
      setData(res);
      setError(null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(page);
  }, [page, load]);

  async function remove(lead: SavedLead) {
    if (!window.confirm(`Remove ${fullName(lead)} from your saved leads?`)) return;
    setBusy(true);
    try {
      await apiRequest(`/api/leads/${lead.id}`, { method: "DELETE" });
      await load(page);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function exportAll() {
    setBusy(true);
    try {
      await downloadCsv("/api/leads/export.csv");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="page-header page-header-row">
        <div>
          <h1>Saved Leads</h1>
          <p className="muted">
            {authRequired
              ? "Leads you saved from search results. Only you can see your saved leads."
              : "Leads saved from search results. Everyone using this site shares this list."}
          </p>
        </div>
        {data && data.total > 0 && (
          <button type="button" className="btn btn-secondary" onClick={exportAll} disabled={busy}>
            Export all (CSV)
          </button>
        )}
      </header>

      <section className="card" aria-busy={loading}>
        {error && (
          <div className="alert alert-error" role="alert">
            {error}
          </div>
        )}
        {loading && !data && (
          <div className="empty-state" role="status">
            <span className="spinner" aria-hidden="true" /> Loading…
          </div>
        )}
        {data && data.items.length === 0 && (
          <div className="empty-state">
            No saved leads yet. Select results on the <Link href="/">Dashboard</Link> and click Save selected.
          </div>
        )}
        {data && data.items.length > 0 && (
          <>
            <p className="muted table-summary">{data.total.toLocaleString()} saved lead{data.total === 1 ? "" : "s"}</p>
            <ResultsTable
              records={data.items}
              caption="Saved leads"
              rowAction={(lead) => (
                <button type="button" className="btn btn-danger btn-small" disabled={busy} onClick={() => remove(lead)}>
                  Remove
                </button>
              )}
            />
            <Pagination
              page={data.page}
              totalPages={data.total_pages}
              hasMore={data.page < data.total_pages}
              disabled={loading || busy}
              onPage={setPage}
            />
          </>
        )}
      </section>
    </>
  );
}
