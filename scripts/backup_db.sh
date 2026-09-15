#!/usr/bin/env bash
set -Eeuo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
BACKUP_DIR="${BACKUP_DIR:-backups}"

[[ -f "$COMPOSE_FILE" ]] || { echo "Compose não encontrado: $COMPOSE_FILE" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "Env não encontrado: $ENV_FILE" >&2; exit 1; }
mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y-%m-%d_%H%M%S)"
output="$BACKUP_DIR/freteway_${timestamp}.dump"

container="$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps -q postgres)"
[[ -n "$container" ]] || { echo "PostgreSQL não está em execução." >&2; exit 1; }

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres sh -eu -c \
  'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null && pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
  > "$output"
[[ -s "$output" ]] || { rm -f "$output"; echo "Dump vazio; backup cancelado." >&2; exit 1; }
echo "Backup criado: $output"
