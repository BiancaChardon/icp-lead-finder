# Backup manifest

This file describes the Git handoff of ICP Lead Finder. It is not a database backup.

## Included

- FastAPI backend, SQLAlchemy models, and Alembic revision `0001_initial_schema`
- Next.js frontend, including saved-lead search, CSV export, and the Import Leads UI
- Excel import API (`POST /api/leads/import/preview`, `POST /api/leads/import`,
  `POST /api/leads/import/errors`), parser, and pytest coverage
- CSV export of search selections and saved leads, with formula-injection protection
- Mock provider, which returns fictional demonstration prospects
- Docker Compose files for the default stack, the local demo ports, the test runners,
  and the Caddy production overlay
- `deploy/Caddyfile`
- `.env.example` with placeholders only
- `samples/sample-prospects.xlsx` (12 fictional prospects) and
  `samples/build_sample_prospects.py`
- README, demo instructions, environment notes, and backup/restore notes
- Backend pytest suite and frontend Vitest tests

## Intentionally excluded

- `.env` and any real `POSTGRES_PASSWORD`, session secret, or provider key
- `backups/` and `*.dump` files, including the local dump taken on 2026-11-02
- The live PostgreSQL volume and its saved leads, search history, and audit rows
- `node_modules/`, `.next/`, Python virtual environments, `__pycache__/`, pytest cache,
  and editor files
- Docker named volumes (`postgres_data`, `caddy_data`, `caddy_config`)

`.gitignore` already ignores `.env`, `backups/`, `*.dump`, virtual environments,
`node_modules/`, and `.next/`.

## Not in this tree

`samples/icp-lead-finder-30-additional-prospects.xlsx` was not found on this machine.
It was not recreated. Copy that workbook into `samples/` separately if another engineer
needs it.

## Known limitations

- The running demo uses `AUTH_REQUIRED=false`. That is a local setting, not a production
  recommendation.
- The mock provider is demonstration data. It is not a source of verified leads.
- Apollo.io and Hunter.io are documented as future provider names only. They are not
  connected.
- Excel import accepts `.xlsx` only, up to 10 MB, 5,000 data rows, and 50 columns.
  Duplicate Excel rows are skipped unless the importer asks to update them.
- The Caddy overlay is in the repository. No public host was deployed or verified for
  this backup. [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) contains an unverified
  DigitalOcean example; [DEPLOYMENT.md](DEPLOYMENT.md) is the guide to follow.
- The original Git remote remains `https://github.com/BiancaChardon/icp-lead-finder.git`.
  This handoff does not push to that repository.
