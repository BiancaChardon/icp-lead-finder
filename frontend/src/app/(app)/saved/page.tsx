"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { LeadImport } from "@/components/LeadImport";
import { Pagination } from "@/components/Pagination";
import { ResultsTable } from "@/components/ResultsTable";
import { useAuthRequired } from "@/components/UserContext";
import { apiJson, apiRequest, downloadCsv, errorText } from "@/lib/api";
import { fullName } from "@/lib/format";
import type { Page, SavedLead } from "@/lib/types";

const PER_PAGE = 25;

interface ContactFilters {
  fullName: string;
  firstName: string;
  lastName: string;
  phone: string;
  email: string;
}

const EMPTY_FILTERS: ContactFilters = { fullName: "", firstName: "", lastName: "", phone: "", email: "" };

function filtersActive(filters: ContactFilters): boolean {
  return Object.values(filters).some((value) => value.trim());
}

export default function SavedLeadsPage() {
  const authRequired = useAuthRequired();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<SavedLead> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [draft, setDraft] = useState<ContactFilters>(EMPTY_FILTERS);
  const [filters, setFilters] = useState<ContactFilters>(EMPTY_FILTERS);

  const load = useCallback(async (p: number, active: ContactFilters) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(PER_PAGE) });
      if (active.fullName.trim()) params.set("full_name", active.fullName.trim());
      if (active.firstName.trim()) params.set("first_name", active.firstName.trim());
      if (active.lastName.trim()) params.set("last_name", active.lastName.trim());
      if (active.phone.trim()) params.set("phone", active.phone.trim());
      if (active.email.trim()) params.set("email", active.email.trim());
      const res = await apiJson<Page<SavedLead>>(`/api/leads?${params.toString()}`);
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
    void load(page, filters);
  }, [page, filters, load]);

  async function remove(lead: SavedLead) {
    if (!window.confirm(`Remove ${fullName(lead)} from your saved leads?`)) return;
    setBusy(true);
    try {
      await apiRequest(`/api/leads/${lead.id}`, { method: "DELETE" });
      await load(page, filters);
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
        <div className="header-actions">
          <button type="button" className="btn btn-primary" onClick={() => setImportOpen((open) => !open)}>
            Import Leads
          </button>
          {data && data.total > 0 && (
            <button type="button" className="btn btn-secondary" onClick={exportAll} disabled={busy}>
              Export all (CSV)
            </button>
          )}
        </div>
      </header>

      {importOpen && (
        <LeadImport
          onImported={() => {
            if (page === 1) void load(1, filters);
            else setPage(1);
          }}
        />
      )}

      <form
        className="card"
        onSubmit={(event) => {
          event.preventDefault();
          if (draft.phone.trim() && !/\d/.test(draft.phone)) {
            setError("Phone number must include digits");
            return;
          }
          setError(null);
          setFilters(draft);
          setPage(1);
        }}
      >
        <div className="card-header">
          <h2>Find a saved lead</h2>
          <p className="muted">
            Search imported and saved prospects. Every field is optional. Type a full name in one field, including “Price, Sophia”.
          </p>
        </div>
        <div className="form-grid">
          {(
            [
              ["fullName", "Full name", "e.g. Sophia Price or Price, Sophia"],
              ["firstName", "First name", "e.g. Sophia or Sophia Price"],
              ["lastName", "Last name", "e.g. Lang"],
              ["phone", "Phone number", "e.g. (410) 555-0101"],
              ["email", "Email address", "e.g. lang@harbor"],
            ] as const
          ).map(([key, label, placeholder]) => (
            <label className="field" key={key}>
              <span>
                {label} <span className="optional">(optional)</span>
              </span>
              <input
                value={draft[key]}
                placeholder={placeholder}
                onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
              />
            </label>
          ))}
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            Search saved leads
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={loading || (!filtersActive(draft) && !filtersActive(filters))}
            onClick={() => {
              setDraft(EMPTY_FILTERS);
              setFilters(EMPTY_FILTERS);
              setPage(1);
              setError(null);
            }}
          >
            Clear
          </button>
        </div>
      </form>

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
        {data && data.items.length === 0 && filtersActive(filters) && (
          <div className="empty-state">No saved leads match this search.</div>
        )}
        {data && data.items.length === 0 && !filtersActive(filters) && (
          <div className="empty-state">
            No saved leads yet. Select results on the <Link href="/">Dashboard</Link> and click Save selected, or use
            Import Leads to upload an Excel file.
          </div>
        )}
        {data && data.items.length > 0 && (
          <>
            <p className="muted table-summary">
              {data.total.toLocaleString()} saved lead{data.total === 1 ? "" : "s"}
              {filtersActive(filters) ? " matching this search" : ""}
            </p>
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
