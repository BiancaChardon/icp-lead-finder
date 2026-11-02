"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiJson, downloadCsv, errorText } from "@/lib/api";
import { EMPTY_FORM, buildCriteria, criteriaToForm, type SearchFormValues } from "@/lib/criteria";
import { recordKey } from "@/lib/format";
import type { HistoryEntry, Prospect, ProviderInfo, SearchCriteria, SearchResponse, SortDir } from "@/lib/types";
import { Pagination } from "./Pagination";
import { ResultsTable } from "./ResultsTable";
import { SearchForm } from "./SearchForm";

type Status = "idle" | "loading" | "success" | "error";

interface QueryState {
  page: number;
  perPage: number;
  sortBy: string | null;
  sortDir: SortDir;
  recordHistory: boolean;
}

const MAX_SAVE_AT_ONCE = 100;

export function Dashboard() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [provider, setProvider] = useState<ProviderInfo | null>(null);
  const [form, setForm] = useState<SearchFormValues>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<string[]>([]);

  const [criteria, setCriteria] = useState<SearchCriteria | null>(null);
  const [query, setQuery] = useState<QueryState>({ page: 1, perPage: 25, sortBy: null, sortDir: "asc", recordHistory: true });
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);

  const [selected, setSelected] = useState<Map<string, Prospect>>(new Map());
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  useEffect(() => {
    apiJson<ProviderInfo>("/api/search/provider")
      .then(setProvider)
      .catch(() => setProvider(null));
  }, []);

  const runSearch = useCallback(async (nextCriteria: SearchCriteria, next: QueryState) => {
    setStatus("loading");
    setError(null);
    setNotice(null);
    setActionError(null);
    try {
      const res = await apiJson<SearchResponse>("/api/search", {
        method: "POST",
        body: {
          criteria: nextCriteria,
          page: next.page,
          per_page: next.perPage,
          sort_by: next.sortBy,
          sort_dir: next.sortDir,
          record_history: next.recordHistory,
        },
      });
      setCriteria(nextCriteria);
      setQuery(next);
      setResponse(res);
      setStatus("success");
    } catch (err) {
      setError(errorText(err));
      setStatus("error");
    }
  }, []);

  const historyId = searchParams.get("history");
  const loadedHistory = useRef<string | null>(null);
  useEffect(() => {
    if (!historyId || loadedHistory.current === historyId) return;
    loadedHistory.current = historyId;
    apiJson<HistoryEntry>(`/api/history/${encodeURIComponent(historyId)}`)
      .then((entry) => {
        setForm(criteriaToForm(entry.criteria));
        setSelected(new Map());
        void runSearch(entry.criteria, { page: 1, perPage: 25, sortBy: null, sortDir: "asc", recordHistory: true });
      })
      .catch((err) => {
        setError(errorText(err));
        setStatus("error");
      })
      .finally(() => router.replace("/"));
  }, [historyId, router, runSearch]);

  function submit() {
    const built = buildCriteria(form);
    setFormErrors(built.errors);
    if (built.errors.length > 0) return;
    setSelected(new Map());
    void runSearch(built.criteria, { ...query, page: 1, recordHistory: true });
  }

  function reset() {
    setForm(EMPTY_FORM);
    setFormErrors([]);
  }

  function changeSort(field: string) {
    if (!criteria) return;
    const sortDir: SortDir = query.sortBy === field && query.sortDir === "asc" ? "desc" : "asc";
    void runSearch(criteria, { ...query, page: 1, sortBy: field, sortDir, recordHistory: false });
  }

  function changePage(page: number) {
    if (criteria) void runSearch(criteria, { ...query, page, recordHistory: false });
  }

  function changePerPage(perPage: number) {
    if (criteria) void runSearch(criteria, { ...query, page: 1, perPage, recordHistory: false });
  }

  function toggle(record: Prospect) {
    setSelected((prev) => {
      const next = new Map(prev);
      const key = recordKey(record);
      if (next.has(key)) next.delete(key);
      else next.set(key, record);
      return next;
    });
  }

  function toggleAll(records: Prospect[], select: boolean) {
    setSelected((prev) => {
      const next = new Map(prev);
      for (const r of records) {
        if (select) next.set(recordKey(r), r);
        else next.delete(recordKey(r));
      }
      return next;
    });
  }

  async function saveSelected() {
    const leads = [...selected.values()];
    if (leads.length > MAX_SAVE_AT_ONCE) {
      setActionError(`Select at most ${MAX_SAVE_AT_ONCE} leads to save at once.`);
      return;
    }
    setActionBusy(true);
    setActionError(null);
    try {
      const res = await apiJson<{ saved: number; already_saved: number }>("/api/leads", {
        method: "POST",
        body: { leads },
      });
      const parts = [`Saved ${res.saved} lead${res.saved === 1 ? "" : "s"}`];
      if (res.already_saved) parts.push(`${res.already_saved} already saved`);
      setNotice(parts.join(" · "));
      setSelected(new Map());
    } catch (err) {
      setActionError(errorText(err));
    } finally {
      setActionBusy(false);
    }
  }

  async function exportCsv() {
    const records = selected.size > 0 ? [...selected.values()] : (response?.results ?? []);
    if (records.length === 0) return;
    setActionBusy(true);
    setActionError(null);
    try {
      await downloadCsv("/api/export/csv", { method: "POST", body: { records } });
    } catch (err) {
      setActionError(errorText(err));
    } finally {
      setActionBusy(false);
    }
  }

  const results = response?.results ?? [];

  return (
    <>
      <header className="page-header">
        <h1>Dashboard</h1>
        <p className="muted">Define an ideal customer profile and review matching companies and decision-makers.</p>
      </header>

      {provider?.is_demo && (
        <div className="alert alert-demo" role="note">
          <strong>Demonstration mode.</strong> Searches use the mock provider. Every result is fictional demo data,
          not a real person or company.
        </div>
      )}

      <SearchForm
        values={form}
        onChange={setForm}
        onSubmit={submit}
        onReset={reset}
        provider={provider}
        busy={status === "loading"}
        errors={formErrors}
      />

      <section className="card" aria-labelledby="results-heading" aria-busy={status === "loading"}>
        <div className="card-header card-header-row">
          <div>
            <h2 id="results-heading">Results</h2>
            {status === "success" && response && (
              <p className="muted">
                {response.total?.toLocaleString() ?? results.length} matching prospect
                {response.total === 1 ? "" : "s"}
                {response.is_demo ? " (demo data)" : ""}
              </p>
            )}
          </div>
          {status === "success" && results.length > 0 && (
            <div className="toolbar">
              <span className="muted">{selected.size} selected</span>
              <button type="button" className="btn btn-primary" disabled={actionBusy || selected.size === 0} onClick={saveSelected}>
                Save selected
              </button>
              <button type="button" className="btn btn-secondary" disabled={actionBusy} onClick={exportCsv}>
                {selected.size > 0 ? "Export selected (CSV)" : "Export page (CSV)"}
              </button>
            </div>
          )}
        </div>

        {notice && (
          <div className="alert alert-success" role="status">
            {notice}
          </div>
        )}
        {actionError && (
          <div className="alert alert-error" role="alert">
            {actionError}
          </div>
        )}

        {status === "idle" && (
          <div className="empty-state">Enter an ideal customer profile above and click Search Leads.</div>
        )}
        {status === "loading" && (
          <div className="empty-state" role="status">
            <span className="spinner" aria-hidden="true" /> Searching…
          </div>
        )}
        {status === "error" && (
          <div className="alert alert-error" role="alert">
            {error}
          </div>
        )}
        {status === "success" && results.length === 0 && (
          <div className="empty-state">No matching prospects. Try broadening your criteria.</div>
        )}
        {status === "success" && response && results.length > 0 && (
          <>
            <ResultsTable
              records={results}
              caption="Search results"
              sort={{
                sortBy: query.sortBy,
                sortDir: query.sortDir,
                sortFields: provider?.sort_fields ?? [],
                onSort: changeSort,
              }}
              selection={{ selected: new Set(selected.keys()), onToggle: toggle, onToggleAll: toggleAll }}
            />
            <Pagination
              page={response.page}
              totalPages={response.total_pages}
              hasMore={response.has_more}
              onPage={changePage}
              perPage={query.perPage}
              perPageOptions={provider?.per_page_options ?? [10, 25, 50]}
              onPerPage={changePerPage}
            />
          </>
        )}
      </section>
    </>
  );
}
