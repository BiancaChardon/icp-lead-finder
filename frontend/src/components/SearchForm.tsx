"use client";

import type { FormEvent } from "react";
import { LIMITS, type SearchFormValues } from "@/lib/criteria";
import type { ProviderInfo } from "@/lib/types";

const INDUSTRY_SUGGESTIONS = [
  "Healthcare",
  "Financial Services",
  "Manufacturing",
  "Software",
  "Education",
  "Government Contracting",
  "Logistics",
  "Retail",
];

interface Props {
  values: SearchFormValues;
  onChange: (values: SearchFormValues) => void;
  onSubmit: () => void;
  onReset: () => void;
  provider: ProviderInfo | null;
  busy: boolean;
  errors: string[];
}

export function SearchForm({ values, onChange, onSubmit, onReset, provider, busy, errors }: Props) {
  function set<K extends keyof SearchFormValues>(key: K, value: SearchFormValues[K]) {
    onChange({ ...values, [key]: value });
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit();
  }

  return (
    <form className="card search-form" onSubmit={submit} noValidate aria-labelledby="search-heading">
      <div className="card-header">
        <h2 id="search-heading">Ideal customer profile</h2>
        <p className="muted">Fill in any combination of criteria. Separate multiple values as shown.</p>
      </div>

      <div className="form-grid">
        <label className="field">
          <span>Industry</span>
          <input
            list="industry-suggestions"
            value={values.industry}
            maxLength={LIMITS.shortText}
            placeholder="e.g. Healthcare"
            onChange={(e) => set("industry", e.target.value)}
          />
          <datalist id="industry-suggestions">
            {INDUSTRY_SUGGESTIONS.map((i) => (
              <option key={i} value={i} />
            ))}
          </datalist>
        </label>

        <label className="field">
          <span>Target job titles</span>
          <input
            value={values.jobTitles}
            placeholder="CIO, CTO, IT Director"
            onChange={(e) => set("jobTitles", e.target.value)}
          />
          <small className="hint">Comma-separated, up to {LIMITS.listItems}</small>
        </label>

        <label className="field">
          <span>Locations</span>
          <input
            value={values.locations}
            placeholder="Maryland; Virginia; Washington, D.C."
            onChange={(e) => set("locations", e.target.value)}
          />
          <small className="hint">Semicolon-separated: city, state, or country</small>
        </label>

        <fieldset className="field field-range">
          <legend>Company size (employees)</legend>
          <div className="range-inputs">
            <input
              inputMode="numeric"
              aria-label="Minimum employees"
              placeholder="Min, e.g. 100"
              value={values.employeeMin}
              onChange={(e) => set("employeeMin", e.target.value)}
            />
            <span aria-hidden="true">–</span>
            <input
              inputMode="numeric"
              aria-label="Maximum employees"
              placeholder="Max, e.g. 1000"
              value={values.employeeMax}
              onChange={(e) => set("employeeMax", e.target.value)}
            />
          </div>
        </fieldset>

        <label className="field">
          <span>Company keywords</span>
          <input
            value={values.keywords}
            placeholder="automation, cybersecurity"
            onChange={(e) => set("keywords", e.target.value)}
          />
          <small className="hint">Comma-separated</small>
        </label>

        <label className="field">
          <span>
            Company name <span className="optional">(optional)</span>
          </span>
          <input
            value={values.companyName}
            maxLength={LIMITS.companyName}
            onChange={(e) => set("companyName", e.target.value)}
          />
        </label>
      </div>

      {provider && provider.filters.length > 0 && (
        <fieldset className="provider-filters">
          <legend>Provider filters</legend>
          {provider.filters.map((f) => (
            <label key={f.key} className="checkbox">
              <input
                type="checkbox"
                checked={!!values.providerFilters[f.key]}
                onChange={(e) => set("providerFilters", { ...values.providerFilters, [f.key]: e.target.checked })}
              />
              {f.label}
            </label>
          ))}
        </fieldset>
      )}

      {errors.length > 0 && (
        <div className="alert alert-error" role="alert">
          <ul>
            {errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Searching…" : "Search Leads"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onReset} disabled={busy}>
          Clear
        </button>
      </div>
    </form>
  );
}
