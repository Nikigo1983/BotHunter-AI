#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${ROOT_DIR}/backups"
CONTAINER="${POSTGRES_CONTAINER:-bothunter-postgres}"
DB_USER="${POSTGRES_USER:-bothunter}"
DB_NAME="${POSTGRES_DB:-bothunter}"
TIMESTAMP="$(date -u +"%Y%m%d_%H%M%S")"
OUTPUT="${BACKUP_DIR}/bothunter_${TIMESTAMP}.sql"

mkdir -p "${BACKUP_DIR}"

if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  echo "Error: container '${CONTAINER}' is not running." >&2
  echo "Start stack: docker compose -f docker/docker-compose.yml up -d" >&2
  exit 1
fi

docker exec "${CONTAINER}" pg_dump -U "${DB_USER}" "${DB_NAME}" > "${OUTPUT}"
echo "Backup saved: ${OUTPUT}"
