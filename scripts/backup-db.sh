#!/bin/sh
# Back up the PostgreSQL database to backups/ and prune local dumps older than RETENTION_DAYS.
# Usage: ./scripts/backup-db.sh
#   COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml" ./scripts/backup-db.sh   (production)
set -eu

cd "$(dirname "$0")/.."
RETENTION_DAYS="${RETENTION_DAYS:-14}"
COMPOSE_FILES="${COMPOSE_FILES:-}"

mkdir -p backups
chmod 700 backups
target="backups/icp-lead-finder-$(date +%Y%m%d-%H%M%S).dump"

# shellcheck disable=SC2086
docker compose $COMPOSE_FILES exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$target"
chmod 600 "$target"

if [ ! -s "$target" ]; then
  echo "Backup failed: $target is empty" >&2
  rm -f "$target"
  exit 1
fi

find backups -name 'icp-lead-finder-*.dump' -mtime +"$RETENTION_DAYS" -delete
echo "Backup written to $target"
