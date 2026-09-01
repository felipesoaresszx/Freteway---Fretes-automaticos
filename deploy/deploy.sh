#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ENV_FILE="${ENV_FILE:-.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"

[[ -f "$ENV_FILE" ]] || { echo "Crie $ENV_FILE a partir de .env.production.example." >&2; exit 1; }
[[ -f backend/.env.production ]] || { echo "Crie backend/.env.production a partir do exemplo." >&2; exit 1; }
set -a; source "$ENV_FILE"; set +a
for variable in DOMAIN TLS_EMAIL POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_PASSWORD_URLENCODED; do
  [[ -n "${!variable:-}" ]] || { echo "Variável obrigatória ausente: $variable" >&2; exit 1; }
done
[[ "$POSTGRES_PASSWORD" != change-me* ]] || { echo "Troque POSTGRES_PASSWORD." >&2; exit 1; }

volume_name="frete-system_postgres_data"
if ! docker volume inspect "$volume_name" >/dev/null 2>&1; then
  echo "Volume obrigatório '$volume_name' ausente; deploy interrompido para evitar banco vazio." >&2
  exit 1
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet

storage_volume="${APP_STORAGE_VOLUME_NAME:-freteway_app_storage}"
if [[ -d backend/storage ]] && find backend/storage -type f -print -quit | grep -q . \
   && ! docker volume inspect "$storage_volume" >/dev/null 2>&1; then
  echo "Storage legado encontrado em backend/storage e volume '$storage_volume' ausente." >&2
  echo "Execute ./scripts/migrate_storage_to_volume.sh e valide os arquivos antes do deploy." >&2
  exit 1
fi
if docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps -q postgres | grep -q .; then
  ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" ./scripts/pre_deploy_backup.sh
else
  echo "PostgreSQL ainda não está ativo; confirme backup externo antes de migrar um servidor existente."
fi
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d postgres
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm backend alembic upgrade head
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm backend python -m app.bootstrap
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d backend worker frontend
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10)"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
if [[ "${ACTIVATE_PROXY:-false}" == "true" ]]; then
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d proxy
  echo "Proxy Caddy ativado."
else
  echo "Caddy NÃO foi iniciado (ACTIVATE_PROXY=false). O Nginx atual pode continuar em :80."
fi
echo "Deploy concluído sem remover volumes nem executar downgrade. Valide login e integrações."
