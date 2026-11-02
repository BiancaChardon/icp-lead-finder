"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Pagination } from "@/components/Pagination";
import { apiJson, errorText } from "@/lib/api";
import { describeCriteria } from "@/lib/criteria";
import { formatDateTime } from "@/lib/format";
import type { HistoryEntry, Page } from "@/lib/types";

const PER_PAGE = 25;

export default function HistoryPage() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<HistoryEntry> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiJson<Page<HistoryEntry>>(`/api/history?page=${page}&per_page=${PER_PAGE}`)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(errorText(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page]);

  return (
    <>
      <header className="page-header">
        <h1>Search History</h1>
        <p className="muted">Your previous searches. Only the criteria are stored, not the results.</p>
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
            No searches yet. <Link href="/">Run your first search</Link>.
          </div>
        )}
        {data && data.items.length > 0 && (
          <>
            <div className="table-wrapper">
              <table className="results-table">
                <caption className="visually-hidden">Search history</caption>
                <thead>
                  <tr>
                    <th scope="col">When</th>
                    <th scope="col">Criteria</th>
                    <th scope="col">Results</th>
                    <th scope="col">Source</th>
                    <th scope="col">
                      <span className="visually-hidden">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((entry) => (
                    <tr key={entry.id}>
                      <td className="nowrap">{formatDateTime(entry.created_at)}</td>
                      <td>{describeCriteria(entry.criteria)}</td>
                      <td className="cell-number">{entry.result_count?.toLocaleString() ?? "—"}</td>
                      <td>{entry.provider === "mock" ? <span className="demo-badge">DEMO</span> : entry.provider}</td>
                      <td className="col-action">
                        <Link className="btn btn-secondary btn-small" href={`/?history=${entry.id}`}>
                          Run again
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={data.page}
              totalPages={data.total_pages}
              hasMore={data.page < data.total_pages}
              disabled={loading}
              onPage={setPage}
            />
          </>
        )}
      </section>
    </>
  );
}
