# ICP Lead Finder — local demo

Verified on this machine on 2026-11-02. The stack is already built and the database volume already exists.

## Open the app

http://127.0.0.1:3012

Use that address, or http://localhost:3012. Both are listed in `CORS_ALLOWED_ORIGINS`. Opening the app on port 3000 will hit a different application (Nexus) and will fail this app's origin check.

| Check | URL | Expected |
| --- | --- | --- |
| Dashboard | http://127.0.0.1:3012 | Search form, no sign-in page |
| Frontend health | http://127.0.0.1:3012/api/health | `{"status":"ok","service":"backend"}` |
| Database health | http://127.0.0.1:8012/health/ready | `{"status":"ok","database":"ok"}` |
| API docs | http://127.0.0.1:8012/docs | Swagger UI |

## Start tomorrow

From `/home/rootx/projects/icp-lead-finder`:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d
docker compose -f docker-compose.yml -f docker-compose.demo.yml ps
```

`db`, `backend`, and `frontend` should each show `healthy`. This command reuses the existing images and the Postgres volume. It does not reinstall dependencies.

Stop, keeping saved leads and search history:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml down
```

Do not add `-v`. That deletes the database volume.

Rebuild only if an image is missing or the code changed:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build
```

## Why the ports are not 3000 and 8000

`docker-compose.yml` publishes the frontend on `127.0.0.1:3000` and the backend on `127.0.0.1:8000`. Those host ports are already used by Nexus (`nexus-frontend-1` and `nexus-backend-1`). Nexus was left running.

`docker-compose.demo.yml` changes only the host side:

- frontend `127.0.0.1:3012` → container `3000`
- backend `127.0.0.1:8012` → container `8000`

Postgres stays on the Docker network and is not published. `.env` is local, mode `0600`, and ignored by Git. `AUTH_REQUIRED=false`. `CONTACT_PROVIDER` is empty, which selects the built-in mock provider in development.

## What the demo uses

Sign-in is off. The dashboard opens directly and uses one shared workspace. Searches return fictional records from the mock provider (DEMO badge, `.example` email addresses, `555-01xx` phone numbers). No API key is required, and the running app does not call Apollo.io or Hunter.io. Those providers are not implemented; setting `CONTACT_PROVIDER` to either of them makes the backend refuse to start.

Saved Leads contains 63 records, all owned by the shared workspace user: 50 fictional prospects with data source “Excel import”, the 12 fictional prospects from `samples/sample-prospects.xlsx` (“Sample spreadsheet (fictional)”), and Kendall Kingsley at Clearpath Medical Group (DEMO). Search history contains the earlier dashboard searches. Uploading the sample workbook again shows 12 duplicates and does not add rows unless **Update saved leads that match these rows** is checked. A verified backup and restore procedure is in `docs/BACKUP_AND_RESTORE.md`.

Docker must be running. The mock demo does not need an external contact-data API. Rebuilding images needs network access to the image registries and package indexes.

## Import a spreadsheet

Saved Leads has an **Import Leads** button. It accepts `.xlsx` files up to 10 MB and 5,000 rows. Legacy `.xls` files are rejected. The workbook is read in memory and is not stored on disk.

A fictional sample workbook is at `samples/sample-prospects.xlsx` (12 prospects). To try it:

1. Open http://127.0.0.1:3012/saved
2. Click **Import Leads**
3. Choose `samples/sample-prospects.xlsx`
4. The preview shows 12 valid rows. They are already saved, so each is marked Duplicate and the import button stays disabled
5. Imported rows already in the list show an **Imported** badge. The mock lead still shows **DEMO**
6. Leave **Update saved leads that match these rows** unchecked. Confirming an import of this file skips all 12 and leaves the 63 saved leads unchanged

No database migration is required. `docker compose down` without `-v` keeps imported leads.
