#!/usr/bin/env bash
set -Eeuo pipefail

[[ $# -eq 1 ]] || { echo "Uso: $0 backups/arquivo.dump" >&2; exit 2; }
DUMP_FILE="$1"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
[[ -s "$DUMP_FILE" ]] || { echo "Dump inexistente ou vazio: $DUMP_FILE" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "Env não encontrado: $ENV_FILE" >&2; exit 1; }

echo "Este restore NÃO limpa o banco. Ele é seguro apenas para um banco novo/vazio."
echo "Conflitos de objetos ou dados farão o comando falhar sem executar DROP/CLEAN."
read -r -p "Digite RESTAURAR para continuar: " confirmation
[[ "$confirmation" == "RESTAURAR" ]] || { echo "Restore cancelado."; exit 1; }

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres sh -eu -c \
  'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null'
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres sh -eu -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl --exit-on-error' < "$DUMP_FILE"
echo "Restore concluído. Valide contagens, tenants e alembic_version antes de liberar tráfego."
