export type ContactStatus = "verified" | "unverified" | "unavailable" | "unknown";
export type SortDir = "asc" | "desc";
export type Role = "admin" | "member";

export interface Prospect {
  provider: string;
  provider_record_id: string;
  is_demo: boolean;
  data_source: string;
  company_name: string | null;
  first_name: string | null;
  last_name: string | null;
  job_title: string | null;
  email: string | null;
  email_status: ContactStatus;
  phone: string | null;
  phone_status: ContactStatus;
  company_website: string | null;
  industry: string | null;
  employee_count: number | null;
  city: string | null;
  state: string | null;
  country: string | null;
}

export interface SavedLead extends Prospect {
  id: number;
  created_at: string;
}

export interface SearchCriteria {
  industry?: string | null;
  job_titles: string[];
  locations: string[];
  employee_min?: number | null;
  employee_max?: number | null;
  keywords: string[];
  company_name?: string | null;
  full_name?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  provider_filters: Record<string, boolean | number | string>;
}

export interface SearchResponse {
  provider: string;
  is_demo: boolean;
  results: Prospect[];
  page: number;
  per_page: number;
  total: number | null;
  total_pages: number | null;
  has_more: boolean;
  search_id: number | null;
}

export interface ProviderInfo {
  name: string;
  display_name: string;
  is_demo: boolean;
  sort_fields: string[];
  filters: { key: string; label: string; type: "boolean" }[];
  contact_search_fields: string[];
  max_page: number;
  per_page_options: number[];
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface SessionInfo {
  user: User;
  csrf_token: string;
  auth_required: boolean;
}

export interface Page<T> {
  items: T[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface HistoryEntry {
  id: number;
  provider: string;
  criteria: SearchCriteria;
  result_count: number | null;
  created_at: string;
}

export interface ImportField {
  key: string;
  label: string;
}

export interface ImportPreviewRow {
  row_number: number;
  status: "ready" | "duplicate" | "invalid";
  duplicate_reason: "in_file" | "already_saved" | null;
  errors: string[];
  provider_record_id: string | null;
  company_name: string | null;
  first_name: string | null;
  last_name: string | null;
  job_title: string | null;
  email: string | null;
  phone: string | null;
  company_website: string | null;
  industry: string | null;
  employee_count: number | null;
  city: string | null;
  state: string | null;
  country: string | null;
  data_source: string | null;
}

export interface ImportPreview {
  sheet_name: string;
  total_rows: number;
  blank_rows: number;
  valid_records: number;
  invalid_records: number;
  duplicate_records: number;
  existing_duplicates: number;
  repeated_rows: number;
  ready_records: number;
  columns: { header: string; field: string | null }[];
  unmapped_headers: string[];
  fields: ImportField[];
  rows: ImportPreviewRow[];
  rows_shown: number;
  rows_omitted: number;
}

export interface ImportResult {
  imported: number;
  updated: number;
  skipped_duplicates: number;
  rejected: number;
}
