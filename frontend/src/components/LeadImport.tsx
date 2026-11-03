"use client";

import { useRef, useState } from "react";
import { ApiError, CSRF_HEADER, errorText, navigation, readCookie } from "@/lib/api";
import { fullName } from "@/lib/format";
import type { ImportPreview, ImportResult } from "@/lib/types";

interface Props {
  onImported: () => void;
}

const STATUS_LABEL = { ready: "Ready", duplicate: "Duplicate", invalid: "Invalid" } as const;

export function LeadImport({ onImported }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [overwrite, setOverwrite] = useState(false);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "upload" | "working">("idle");
  const [progress, setProgress] = useState(0);

  const busy = phase !== "idle";

  async function send(target: File, path: string, extra: Record<string, string> = {}): Promise<Response> {
    const form = new FormData();
    form.set("file", target);
    const columnMap = Object.fromEntries(Object.entries(mapping).filter(([, value]) => value !== undefined));
    if (Object.keys(columnMap).length > 0) form.set("mapping", JSON.stringify(columnMap));
    for (const [key, value] of Object.entries(extra)) form.set(key, value);
    return postForm(path, form, (loaded, total) => {
      setPhase("upload");
      setProgress(total > 0 ? loaded / total : 0);
    });
  }

  async function previewFile(target: File, nextMapping = mapping) {
    setFile(target);
    setMapping(nextMapping);
    setResult(null);
    setError(null);
    setPreview(null);
    setPhase("upload");
    setProgress(0);
    try {
      const form = new FormData();
      form.set("file", target);
      if (Object.keys(nextMapping).length > 0) form.set("mapping", JSON.stringify(nextMapping));
      const response = await postForm("/api/leads/import/preview", form, (loaded, total) => {
        setProgress(total > 0 ? loaded / total : 0);
      });
      setPhase("working");
      const body = (await response.json()) as ImportPreview;
      setPreview(body);
      setMapping((current) => {
        const merged = { ...current };
        for (const header of body.unmapped_headers) {
          if (!(header in merged)) merged[header] = "";
        }
        return merged;
      });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPhase("idle");
    }
  }

  async function confirmImport() {
    if (!file) return;
    setError(null);
    setPhase("upload");
    setProgress(0);
    try {
      const response = await send(file, "/api/leads/import", { overwrite: overwrite ? "true" : "false" });
      setPhase("working");
      setResult((await response.json()) as ImportResult);
      setPreview(null);
      onImported();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPhase("idle");
    }
  }

  async function downloadErrors() {
    if (!file) return;
    setError(null);
    setPhase("working");
    try {
      const response = await send(file, "/api/leads/import/errors");
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") ?? "";
      const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "import-errors.csv";
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPhase("idle");
    }
  }

  function choose(next: File | undefined) {
    if (!next || busy) return;
    void previewFile(next, {});
  }

  const canImport =
    !!preview && (preview.ready_records > 0 || (overwrite && preview.existing_duplicates > 0));

  return (
    <section className="card" aria-labelledby="import-heading">
      <div className="card-header">
        <h2 id="import-heading">Import leads</h2>
        <p className="muted">
          Upload an Excel workbook of prospects. Accepted format: <strong>.xlsx</strong>, up to 10 MB and 5,000 rows.
          Legacy .xls files are not accepted. Nothing is saved until you confirm.
        </p>
      </div>

      <div
        className={dragOver ? "dropzone dropzone-active" : "dropzone"}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          choose(event.dataTransfer.files?.[0]);
        }}
      >
        <p>{file ? file.name : "Drag an Excel file here"}</p>
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => inputRef.current?.click()}>
          Browse for a file
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          hidden
          onChange={(event) => {
            choose(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </div>

      {busy && (
        <div role="status">
          <progress className="import-progress" value={phase === "working" ? 1 : progress} max={1} />
          <p className="hint">{phase === "upload" && progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : "Checking the spreadsheet…"}</p>
        </div>
      )}

      {error && (
        <div className="alert alert-error" role="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="alert alert-success" role="status">
          <p>
            Imported {result.imported}. Updated {result.updated}. Skipped {result.skipped_duplicates} duplicate
            {result.skipped_duplicates === 1 ? "" : "s"}. Rejected {result.rejected}.
          </p>
          {result.rejected > 0 && file && (
            <button type="button" className="btn btn-secondary btn-small" disabled={busy} onClick={() => void downloadErrors()}>
              Download error report (CSV)
            </button>
          )}
        </div>
      )}

      {preview && (
        <>
          <div className="import-stats">
            <Stat label="Spreadsheet rows" value={preview.total_rows} />
            <Stat label="Blank rows ignored" value={preview.blank_rows} />
            <Stat label="Valid records" value={preview.valid_records} />
            <Stat label="Invalid records" value={preview.invalid_records} />
            <Stat label="Potential duplicates" value={preview.duplicate_records} />
            <Stat label="Ready to import" value={preview.ready_records} />
          </div>

          {preview.unmapped_headers.length > 0 && (
            <fieldset className="provider-filters">
              <legend>Unrecognized columns</legend>
              <p className="hint">These headers were not recognized. Choose a lead field, or leave them out of the import.</p>
              <div className="mapping-grid">
                {preview.unmapped_headers.map((header) => (
                  <label key={header} className="field">
                    <span>{header}</span>
                    <select
                      value={mapping[header] ?? ""}
                      onChange={(event) => setMapping((current) => ({ ...current, [header]: event.target.value }))}
                    >
                      <option value="">Don&apos;t import</option>
                      {preview.fields.map((field) => (
                        <option key={field.key} value={field.key}>
                          {field.label}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <div className="form-actions">
                <button type="button" className="btn btn-secondary" disabled={busy || !file} onClick={() => file && void previewFile(file, mapping)}>
                  Update preview
                </button>
              </div>
            </fieldset>
          )}

          <div className="table-wrapper">
            <table className="results-table">
              <caption className="visually-hidden">Import preview for {preview.sheet_name}</caption>
              <thead>
                <tr>
                  <th scope="col">Row</th>
                  <th scope="col">Status</th>
                  <th scope="col">Name</th>
                  <th scope="col">Company</th>
                  <th scope="col">Email</th>
                  <th scope="col">Issues</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row.row_number}>
                    <td>{row.row_number}</td>
                    <td>{STATUS_LABEL[row.status]}</td>
                    <td>{fullName(row)}</td>
                    <td>{row.company_name ?? "—"}</td>
                    <td>{row.email ?? "—"}</td>
                    <td>{row.errors.join(" ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {preview.rows_omitted > 0 && (
            <p className="hint">Showing {preview.rows_shown} of {preview.rows_shown + preview.rows_omitted} reviewed rows.</p>
          )}

          <label className="checkbox">
            <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} />
            Update saved leads that match these rows
          </label>
          <p className="hint">
            Matching rows are skipped unless you check this box. Imported leads are saved as your data and do not show the
            DEMO badge.
          </p>
          <div className="form-actions">
            <button type="button" className="btn btn-primary" disabled={busy || !canImport} onClick={() => void confirmImport()}>
              {preview.ready_records > 0 ? `Import ${preview.ready_records} lead${preview.ready_records === 1 ? "" : "s"}` : "Update matching leads"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy || preview.invalid_records === 0}
              onClick={() => void downloadErrors()}
            >
              Download error report (CSV)
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="import-stat">
      <strong>{value.toLocaleString()}</strong>
      <span className="hint">{label}</span>
    </div>
  );
}

function postForm(path: string, form: FormData, onProgress?: (loaded: number, total: number) => void): Promise<Response> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json, text/csv");
    const csrf = readCookie("ilf_csrf");
    if (csrf) xhr.setRequestHeader(CSRF_HEADER, csrf);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(event.loaded, event.total);
    };
    xhr.onload = () => {
      const response = new Response(xhr.response, {
        status: xhr.status,
        headers: xhr.getAllResponseHeaders()
          .trim()
          .split(/[\r\n]+/)
          .filter(Boolean)
          .map((line) => {
            const index = line.indexOf(":");
            return [line.slice(0, index), line.slice(index + 1).trim()] as [string, string];
          })
          .reduce((headers, [key, value]) => {
            if (key) headers.append(key, value);
            return headers;
          }, new Headers()),
      });
      if (xhr.status === 401) navigation.toLogin();
      if (xhr.status < 200 || xhr.status >= 300) {
        void response
          .clone()
          .json()
          .then((body: { detail?: unknown }) => {
            const detail = typeof body.detail === "string" ? body.detail : `Request failed (HTTP ${xhr.status})`;
            reject(new ApiError(xhr.status, detail));
          })
          .catch(() => reject(new ApiError(xhr.status, `Request failed (HTTP ${xhr.status})`)));
        return;
      }
      resolve(response);
    };
    xhr.onerror = () => reject(new ApiError(0, "The upload failed. Please try again."));
    xhr.responseType = "blob";
    xhr.send(form);
  });
}
