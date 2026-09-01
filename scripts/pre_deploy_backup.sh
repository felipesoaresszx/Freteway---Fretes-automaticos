#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

"$SCRIPT_DIR/backup_db.sh"
latest="$(find backups -maxdepth 1 -type f -name 'freteway_*.dump' -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
metadata="${latest%.dump}.metadata.txt"
{
  echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "git_commit=$(git rev-parse HEAD 2>/dev/null || echo unavailable)"
  echo "alembic_version=$(docker compose --env-file "${ENV_FILE:-.env.production}" -f "${COMPOSE_FILE:-docker-compose.production.yml}" exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT version_num FROM alembic_version"' 2>/dev/null || echo unavailable)"
} > "$metadata"
echo "Metadados criados: $metadata"
