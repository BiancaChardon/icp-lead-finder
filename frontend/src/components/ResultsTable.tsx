import type { ReactNode } from "react";
import { fullName, location, recordKey, safeHttpUrl } from "@/lib/format";
import type { Prospect, SortDir } from "@/lib/types";
import { ContactValue } from "./ContactValue";

interface SortProps {
  sortBy: string | null;
  sortDir: SortDir;
  sortFields: string[];
  onSort: (field: string) => void;
}

interface SelectionProps {
  selected: Set<string>;
  onToggle: (record: Prospect) => void;
  onToggleAll: (records: Prospect[], select: boolean) => void;
}

interface Props<T extends Prospect> {
  records: T[];
  sort?: SortProps;
  selection?: SelectionProps;
  rowAction?: (record: T) => ReactNode;
  caption: string;
}

const COLUMNS: { label: string; sortField?: string }[] = [
  { label: "Name", sortField: "last_name" },
  { label: "Job title", sortField: "job_title" },
  { label: "Company", sortField: "company_name" },
  { label: "Industry", sortField: "industry" },
  { label: "Email" },
  { label: "Phone" },
  { label: "Employees", sortField: "employee_count" },
  { label: "Location", sortField: "state" },
  { label: "Source" },
];

function SortHeader({ label, field, sort }: { label: string; field?: string; sort?: SortProps }) {
  if (!sort || !field || !sort.sortFields.includes(field)) return <th scope="col">{label}</th>;
  const active = sort.sortBy === field;
  const ariaSort = active ? (sort.sortDir === "asc" ? "ascending" : "descending") : "none";
  return (
    <th scope="col" aria-sort={ariaSort}>
      <button type="button" className="sort-button" onClick={() => sort.onSort(field)}>
        {label}
        <span aria-hidden="true" className="sort-indicator">
          {active ? (sort.sortDir === "asc" ? "▲" : "▼") : "↕"}
        </span>
      </button>
    </th>
  );
}

export function ResultsTable<T extends Prospect>({ records, sort, selection, rowAction, caption }: Props<T>) {
  const allSelected = !!selection && records.length > 0 && records.every((r) => selection.selected.has(recordKey(r)));

  return (
    <div className="table-wrapper">
      <table className="results-table">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {selection && (
              <th scope="col" className="col-select">
                <input
                  type="checkbox"
                  aria-label="Select all on this page"
                  checked={allSelected}
                  onChange={(e) => selection.onToggleAll(records, e.target.checked)}
                />
              </th>
            )}
            {COLUMNS.map((c) => (
              <SortHeader key={c.label} label={c.label} field={c.sortField} sort={sort} />
            ))}
            {rowAction && (
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {records.map((r) => {
            const key = recordKey(r);
            const website = safeHttpUrl(r.company_website);
            const isSelected = selection?.selected.has(key) ?? false;
            return (
              <tr key={key} className={isSelected ? "row-selected" : undefined}>
                {selection && (
                  <td className="col-select">
                    <input
                      type="checkbox"
                      aria-label={`Select ${fullName(r)}`}
                      checked={isSelected}
                      onChange={() => selection.onToggle(r)}
                    />
                  </td>
                )}
                <td className="cell-strong">{fullName(r)}</td>
                <td>{r.job_title ?? "—"}</td>
                <td>
                  <div>{r.company_name ?? "—"}</div>
                  {website && (
                    <a className="cell-sub" href={website} target="_blank" rel="noopener noreferrer nofollow">
                      {new URL(website).hostname}
                    </a>
                  )}
                </td>
                <td>{r.industry ?? "—"}</td>
                <td>
                  <ContactValue value={r.email} status={r.email_status} kind="email" />
                </td>
                <td>
                  <ContactValue value={r.phone} status={r.phone_status} kind="phone" />
                </td>
                <td className="cell-number">{r.employee_count?.toLocaleString() ?? "—"}</td>
                <td>{location(r)}</td>
                <td>
                  <div className="cell-sub">{r.data_source}</div>
                  {r.is_demo && <span className="demo-badge">DEMO</span>}
                  {!r.is_demo && r.provider === "excel_import" && <span className="import-badge">Imported</span>}
                </td>
                {rowAction && <td className="col-action">{rowAction(r)}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
