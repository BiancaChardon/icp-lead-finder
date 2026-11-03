# ICP Lead Finder — production-readiness audit

Audit date: 2026-11-02. Scope is the working tree at `/home/rootx/projects/icp-lead-finder` and the running local demo at http://127.0.0.1:3012. This pass did not change code, data, containers, credentials, or integrations.

**Verdict:** the application is a solid single-team prospect workspace for demonstration data, spreadsheet import, and saved-lead lookup. It is not ready to operate as a multi-provider discovery and CRM platform. The provider interface can accept one real source later. The database, identity model, and product surface do not yet support enrichment, scoring, pipeline, or cross-provider search.

The latest commit on `master` is `9e07248` (“Make sign-in optional”). Excel import, contact search, the local port overlay, and this report are uncommitted. A fresh clone of `origin/master` does not contain those features.

## Current architecture

```text
Browser (Next.js 16 / React 19, port 3012 on this machine)
    │  same-origin /api/*
    ▼
Next.js rewrite ──► FastAPI (Python 3.12, container port 8000, host 8012)
                        │
                        ├─ one ProspectProvider (today: mock)
                        ├─ PostgreSQL 17 (Docker volume postgres_data, not published)
                        └─ in-memory rate limiter
```

Local startup uses `docker-compose.yml` plus `docker-compose.demo.yml`, which moves the host ports from 3000/8000 to 3012/8012 because another application already owns 3000 and 8000. Production compose (`docker-compose.prod.yml`) publishes only Caddy on 80/443 and keeps the app and database on internal networks. Migrations run when the backend starts.

The running configuration is development mode, sign-in off, cookies not marked Secure, contact provider unset (so the mock provider is used), and CORS limited to `http://localhost:3012` and `http://127.0.0.1:3012`. The database password is set and is not recorded here.

## Feature classification

| Feature | Status | Evidence |
| --- | --- | --- |
| Dashboard search form (industry, titles, location, size, keywords, company) | IMPLEMENTED | `SearchForm.tsx`, `POST /api/search`, mock provider filters |
| Contact search (first, last, full name, email, phone) | IMPLEMENTED | `contact_search.py`, Saved Leads form, mock matcher. Full name in one field matches both columns. |
| Search results table, sort, pagination | IMPLEMENTED | `ResultsTable.tsx`, `Dashboard.tsx`. Page size 10/25/50, max page 20. |
| Save selected results | IMPLEMENTED | `POST /api/leads`. Skips an existing `(provider, provider_record_id)`. |
| Saved Leads list, remove, contact search | IMPLEMENTED | `saved/page.tsx`, `GET/DELETE /api/leads` |
| Excel `.xlsx` import with preview, mapping, duplicates, error CSV | IMPLEMENTED | `excel_import.py`, `LeadImport.tsx`. Local and uncommitted. `.xls` is rejected. |
| CSV export of results and saved leads | IMPLEMENTED | `POST /api/export/csv`, `GET /api/leads/export.csv`. UTF-8 BOM and formula escaping. This is not an Excel export. |
| Search history (criteria and count, rerun) | IMPLEMENTED | `search_history` stores criteria JSON, not the result rows. History page can run the search again. |
| Sign-in, sessions, CSRF, roles, admin user management | IMPLEMENTED, off in this demo | Argon2 passwords, hashed session cookies, CSRF on unsafe methods when auth is on. `AUTH_REQUIRED=false` uses one shared workspace. |
| Health and readiness | IMPLEMENTED | `/health`, `/health/ready`, and the `/api/` aliases |
| Demonstration provider | SIMULATED | `MockProvider` generates 960 fictional records. Emails use `.example`. Phones use `555-01xx`. Results are badged DEMO. |
| Apollo.io | NOT IMPLEMENTED | `build_provider("apollo")` raises `ProviderNotConfiguredError`. Production refuses to start if the name is not a registered provider. |
| Hunter.io | NOT IMPLEMENTED | Same as Apollo. |
| Multi-provider search in one query | NOT IMPLEMENTED | The process holds exactly one provider. |
| New Prospects Only | NOT IMPLEMENTED | No filter compares provider results with saved leads. |
| Contact enrichment | NOT IMPLEMENTED | No reveal/enrich endpoint, no credit ledger, no enrichment columns. |
| Lead scoring | NOT IMPLEMENTED | No score column, rule, or job. |
| Pipeline and follow-up | NOT IMPLEMENTED | No stage, owner, note, task, or activity table. |
| Analytics and reporting | NOT IMPLEMENTED | Audit events record counts only. No dashboard of volume, conversion, or provider usage. |
| Excel export | NOT IMPLEMENTED | Export is CSV only. |
| Scheduled backups on this machine | NOT IMPLEMENTED | `scripts/backup-db.sh` exists. No `backups/` dumps are present. Cron is documented, not installed here. |

## 1. Dashboard and frontend

Pages:

| Route | What it does |
| --- | --- |
| `/` | Ideal-customer search, contact search, provider filters, results, save, CSV export |
| `/saved` | Shared or per-user saved leads, Excel import, contact search, remove, CSV export |
| `/history` | Prior searches and “run again” |
| `/settings` | Provider status, and, when sign-in is on, password change and team administration |
| `/login` | Sign-in. Redirects to `/` while sign-in is off. |

Working search behavior, verified against the current code and the recent live checks:

- Company criteria and contact criteria combine with AND.
- A full name in one field (`Sophia Price`, `Price, Sophia`, any case, extra spaces) matches first and last name together.
- Email match is case-insensitive and partial.
- Phone match ignores formatting and a leading US `1`.
- Empty optional fields do not filter.
- The mock provider rejects a contact field it does not declare instead of silently dropping it. The mock declares all five name/contact fields.
- Saved-lead search uses the same name rules on `saved_leads`. It does not query Apollo or Hunter.

Usability and error handling that already exist:

- API errors surface as alerts from `errorText` / `ApiError`.
- Validation errors from FastAPI are joined into one message.
- HTTP 401 sends the browser to `/login`.
- HTTP 429 has a plain-language message.
- Import uses upload progress and a preview before commit.
- Results distinguish DEMO data from imported rows.

Gaps:

- There is no “new prospects only” control.
- Dashboard search and Saved Leads search are separate. A dashboard search does not look inside imported spreadsheets, and a saved-lead search does not call the provider.
- Saved-lead search has no industry or company fields in the form. The API accepts `company_name` and `industry`; the page does not send them.
- Export on Saved Leads always exports the full list, not the current filter.
- Frontend tests cover criteria parsing, the API client, contact badges, and the results table (27 tests on the last run). They do not drive the search page, import page, or history page in a browser.
- The Next.js production build rewrites `tsconfig.json` inside the image. That notice is build noise, not a runtime defect.

## 2. Backend and APIs

| Method | Path | Role |
| --- | --- | --- |
| GET | `/health`, `/api/health` | Liveness. Does not reveal configuration. |
| GET | `/health/ready`, `/api/health/ready` | Database readiness. |
| POST | `/api/auth/login` | Password login. Rate limited. |
| POST | `/api/auth/logout` | Ends the session when auth is on. |
| GET | `/api/auth/me` | Current user. Shared workspace user when auth is off. |
| POST | `/api/auth/change-password` | Rejected while sign-in is off. |
| GET/POST/PATCH | `/api/users`, `/api/users/{id}`, `/api/users/{id}/password` | Admin user management. Unavailable while sign-in is off. |
| GET | `/api/search/provider` | Active provider name, demo flag, sort fields, filters, contact fields. |
| POST | `/api/search` | Provider search. Records history on page 1 unless `record_history` is false. |
| POST | `/api/export/csv` | CSV of posted result rows (max 1,000). |
| GET | `/api/leads` | Saved leads, with optional name, email, phone, company, and industry filters. |
| POST | `/api/leads` | Save up to 100 prospects. |
| DELETE | `/api/leads/{id}` | Remove one owned lead. |
| GET | `/api/leads/export.csv` | CSV of up to 5,000 saved leads. |
| POST | `/api/leads/import/preview` | Parse `.xlsx`, no write. |
| POST | `/api/leads/import` | Commit ready rows in one transaction. |
| POST | `/api/leads/import/errors` | CSV of rejected rows. |
| GET | `/api/history`, `/api/history/{id}` | Criteria history for the current user. |

Functional versus simulated:

- Auth, persistence, import, export, history, and saved-lead search talk to PostgreSQL and are functional.
- Prospect discovery talks only to `MockProvider`. That data is generated in memory from a fixed seed. It is simulated.
- Provider failures become generic HTTP 502/503/429 messages. Logs record the exception type, not the provider URL or credentials.

Security controls that are present:

- Argon2 password hashes. Login checks a dummy hash when the user does not exist.
- Session cookie is `HttpOnly`, `SameSite=Lax`. The raw token is stored only as SHA-256.
- CSRF cookie is readable by the page and required on unsafe methods when sign-in is on.
- Browser `Origin` on unsafe methods must be in `CORS_ALLOWED_ORIGINS`, even when sign-in is off.
- Production refuses wildcard CORS, non-HTTPS origins, `COOKIE_SECURE=false`, and an unset provider.
- OpenAPI docs are disabled in production.
- API responses set `nosniff`, `DENY` framing, `no-referrer`, `no-store`, and a locked-down content security policy.
- Spreadsheet formulas and macros are rejected. CSV cells that start with `=`, `+`, `-`, `@`, tab, or return are escaped.
- Uploads are limited to 10 MB and 5,000 data rows. The expanded workbook is limited to 50 MB. Files are not stored.

Security and reliability limits:

- With `AUTH_REQUIRED=false`, anyone who can open the site can search, export, import, and delete every saved lead. On this machine the site is bound to `127.0.0.1`. A production deploy that leaves sign-in off and publishes HTTPS is an open workspace.
- The rate limiter is an in-memory sliding window in one process. A restart clears it. A second replica would not share it. Import is limited to 30 requests a minute the same way.
- Search history and audit details are counts and criteria, which is appropriate, but criteria can contain a searched email or phone.
- There is no account lockout beyond the login rate limit, no session listing, and no forced logout of every device except by changing the password (which keeps the current session).
- Saved-lead name search uses `ILIKE` on a concatenated name with no trigram or expression index. That is acceptable at the current list size and will get slower as the table grows.

Provider extension point:

`ProspectProvider.search(ProspectQuery) -> ProspectPage` is the only integration method. A new source registers in `build_provider()`, declares sort fields, boolean filters, and which contact fields it can actually search, and reads secrets from the environment. The frontend never sees the key. That is the right seam for one provider. It is not a fan-out, waterfall, or credit-metering framework.

## 3. Database

Tables, from migration `0001` only:

| Table | Purpose | Relationships and indexes |
| --- | --- | --- |
| `users` | Accounts. Email unique and lowercase. Role `admin` or `member`. | Primary key. |
| `auth_sessions` | Hashed session token, CSRF token, expiry. | User FK, cascade delete. Indexes on user and expiry. |
| `saved_leads` | One prospect row per user, provider, and provider record id. | Unique `(user_id, provider, provider_record_id)`. Index `(user_id, created_at)`. Status checks on email, phone, and employee count. |
| `search_history` | Criteria JSON, provider name, result count. | User FK. Index `(user_id, created_at)`. |
| `audit_events` | Event type, optional target, JSON details. | Indexes on actor, time, and event type. |

`saved_leads` stores the contact fields the importer and the search already use: name, title, email, phone, verification status, company, website, industry, employees, city, state, country, demo flag, data source, and created time. There is no `updated_at`, owner, stage, score, note, tag, list, suppression flag, or enrichment payload.

Duplicate detection:

- Save and Excel import treat two rows as the same lead only when user, provider, and `provider_record_id` match.
- Excel ids are a SHA-256 of the normalized email, or, when email is missing, of company, first name, last name, and the phone text as stored. A formatted phone and an unformatted phone without an email become two ids.
- The same person returned by the mock provider and imported from Excel is two rows. There is no cross-provider person key.
- Re-import skips duplicates unless the user asks to update. A failed commit rolls back the whole file.

Readiness for later CRM features:

| Need | Ready? |
| --- | --- |
| Store a discovered or imported contact | Yes |
| Avoid a second insert of the same provider record | Yes |
| Know which rows came from demo data | Yes (`is_demo`, `data_source`) |
| Enrich a row in place with a verified email or phone | Partially. Columns exist, but there is no enrichment record, credit use, or “revealed at” time. Overwrite would destroy the previous value. |
| Score a lead | No column or history. |
| Pipeline, owner, follow-up | No. |
| “New prospects only” | Not without comparing provider ids, and later a person identity, to `saved_leads`. |
| Reporting | History and audit rows can count searches and imports. They cannot reconstruct which contacts were shown. |

The schema was not changed during this audit.

## 4. External providers

Registered adapter: `mock` only.

Apollo.io and Hunter.io need, before any code calls them:

1. A confirmed account plan, permitted use, rate limits, and pricing. Apollo people search and contact reveal are different operations; reveal can spend credits. Hunter email finding and verification are likewise separate and metered. Those terms have to be checked against the current vendor docs, not assumed from this repository.
2. An API key in `.env`, for example `APOLLO_API_KEY` or `HUNTER_API_KEY`. The key must not be committed, logged, or sent to the browser. `.env` is gitignored. `.env.example` only has a commented placeholder.
3. A provider class that implements `search()`, maps only fields the vendor returned, and sets `contact_search_fields` to the filters that vendor actually supports. Missing email or phone stays null and displays as unavailable. The app must not invent verification.
4. Registration in `build_provider()`.
5. Tests that use recorded HTTP responses. The test suite must not call the live vendor.
6. `CONTACT_PROVIDER=<name>` and a production origin on HTTPS.

The app is configured to refuse an unknown provider at startup, which is the correct failure. No live vendor call was made in this audit.

What the current adapter does not provide:

- Simultaneous providers, or a preferred order (Apollo, then Hunter, then the local list).
- A separate enrich action with a per-user credit cap and an audit row that contains counts, not contact details.
- Mapping of vendor ids onto the existing `provider` / `provider_record_id` unique key. That key is the right place to store a vendor id once a provider exists.
- Pagination beyond what the mock generates locally. A real provider must define its own page cap and sort fields.

## 5. Future functionality

| Capability | Readiness | What would have to be added |
| --- | --- | --- |
| New Prospects Only | PARTIALLY IMPLEMENTED as data, NOT IMPLEMENTED as a feature | Saved rows already have provider ids. The search response would exclude ids already saved for that user. Cross-provider “same person” needs a separate identity rule. |
| Contact enrichment | NOT IMPLEMENTED | Explicit reveal action, vendor enrich call, credit limit, audit event, and a way to store the new email or phone without losing the prior value. |
| Automated lead scoring | NOT IMPLEMENTED | A versioned rule (title, industry, size, location, email status) and a score column or side table. A learned model is not justified by the current data. |
| Pipeline and follow-up | NOT IMPLEMENTED | Stage, owner, next step, due time, and a note/activity table. Saved leads are a list, not a pipeline. |
| Search history | IMPLEMENTED for criteria | Optional later: store a result snapshot only if the product needs “what we saw,” with a retention limit, because that snapshot is contact data. |
| Analytics | NOT IMPLEMENTED | Counts can be derived from `search_history` and `audit_events`. Conversion and pipeline reports need the pipeline tables first. |
| Excel and CSV export | CSV IMPLEMENTED. Excel export NOT IMPLEMENTED | CSV covers the current columns and is formula-safe. An `.xlsx` download would be a new writer, not a change to import. |

## 6. Testing and deployment

Tests present in the tree:

- Backend modules cover auth, CSRF, origin checks, config, health, mock search, search validation, contact search, Excel import, CSV escaping, leads privacy, migrations, and the CLI. The last full run in this environment was **174 passed**.
- Frontend tests cover criteria, the API helper, contact badges, and the results table. The last run was **27 passed**, plus TypeScript check.
- Tests use a database whose name must end in `_test`. They do not write the demo volume when run through the compose test service.
- There is no browser end-to-end suite and no test that a real provider HTTP client is absent from the default path beyond the startup refusal.

Deployment assumptions:

- Docker Compose, PostgreSQL 17 Alpine, one backend process, one frontend process.
- This machine: host ports 3012 and 8012 via `docker-compose.demo.yml`.
- Production: Caddy, HTTPS, no published database port, `APP_ENV=production`, explicit provider, Secure cookies.
- Documented target is a DigitalOcean Ubuntu VM with a cloud firewall on 22/80/443. Docker-published ports can bypass host `ufw`; production compose avoids that by not publishing the app ports.
- Frontend image build needs enough RAM for `next build` (the deploy doc asks for 2 GB).

Logging, backup, recovery:

- Logs are container stdout. There is no external log store. Provider errors are logged as type names.
- `scripts/backup-db.sh` writes a custom-format `pg_dump` and deletes local dumps older than 14 days. Nothing has been written to `backups/` on this machine, and no cron entry was verified.
- Restore is documented and replaces tables. It has not been rehearsed here.
- Losing the Docker volume `postgres_data` loses users, leads, history, and audit events. `docker compose down -v` would delete that volume. The demo instructions say not to use `-v`.
- `.env` is required to restore a dump because it holds the database password. It is not in git. A password-manager copy is documented and was not verified.

## Critical issues

These block a real multi-provider CRM. They do not block the current local demo.

1. **No real provider is connected.** Selecting Apollo or Hunter will not search. It will fail at startup.
2. **Sign-in is off.** The demo is safe only because it listens on localhost. Shipping that setting on a public URL exposes every lead and any future provider credits.
3. **One provider per process.** The architecture cannot query two sources and merge them.
4. **Identity is a provider record id, not a person.** The same human from two sources, or an Excel row whose phone formatting changed and who has no email, will not collapse to one lead.
5. **The CRM objects do not exist.** There is nowhere to put a stage, owner, score, enrichment event, or follow-up.
6. **The provider, import, and contact-search work is uncommitted.** Deploying `9e07248` alone drops Excel import and full-name search.

## Recommended roadmap

Each phase assumes the previous one is accepted. Complexity is engineering time for this codebase, not vendor procurement.

### Phase 0 — Make the current product deployable

Complexity: **small** (a few days).

- Decide whether the uncommitted import and contact-search work is part of the product, and commit it before any deploy.
- Turn sign-in on for any shared or public host, or keep the firewall limited to known IPs and document that choice.
- Run `scripts/backup-db.sh` once, copy the dump off the machine, and restore it into a scratch database.
- Keep the mock provider labeled DEMO until a real source is tested.

### Phase 1 — One real search provider

Complexity: **medium** (about one to two weeks after API access and a written data-use decision).

- Implement one of Apollo or Hunter behind `ProspectProvider`, with recorded HTTP tests.
- Return only supplied fields. Leave email and phone empty when the search endpoint does not include them.
- Declare the contact filters that endpoint supports. Reject the rest.
- Add a provider-credit note in Settings. Do not add reveal yet.

### Phase 2 — Enrichment

Complexity: **medium to large** (about two to three weeks).

- A separate “Reveal contact” action on selected rows.
- Per-user daily cap, audit event with counts only, and storage that keeps the pre-reveal value.
- Tests with mocked reveal responses and a test that a search does not call reveal.

### Phase 3 — New prospects and identity

Complexity: **medium** (about one to two weeks).

- “New prospects only” by excluding saved `(provider, provider_record_id)`.
- Optional person key for email, and for phone only after the same digit normalization used by search.
- Do not merge across providers until that rule is explicit.

### Phase 4 — Scoring

Complexity: **medium** for rules (about one week). **Not recommended** as a model-training project yet.

- A small ordered ruleset (title, industry, location, size, email status) with a stored score and the rule version.
- Show the score on the result row. Do not block saving.

### Phase 5 — Pipeline

Complexity: **large** (about three to six weeks).

- Stages, owner, next step, due date, and notes on a saved lead.
- List and board views. Activity rows for stage changes.
- This is the point at which the product becomes a CRM rather than a search workspace.

### Phase 6 — Reporting

Complexity: **medium** (about one to two weeks, after Phase 5 if the reports include pipeline).

- Search volume, save rate, import counts, and provider errors from history and audit events.
- Pipeline counts only after stages exist.
- Keep contact details out of report exports unless the user asks for a lead export, which already exists as CSV.

## What this audit did not do

No source files other than this report were written. No packages were installed. No schema, row, container, credential, or external integration was changed. Tests were not re-run in this pass; the pass/fail counts above are from the last execution against this same tree.
