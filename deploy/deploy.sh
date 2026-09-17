#!/usr/bin/env bash
set -Eeuo pipefail

# No deploy pelo GitHub Actions, a chave chega exclusivamente via stdin. Esta
# etapa roda depois da atualização do repositório, inclusive no primeiro deploy
# que introduz este mecanismo.
if [[ ! -t 0 ]] && IFS= read -r SANKHYA_API_KEY; then
  [[ ${#SANKHYA_API_KEY} -ge 32 ]] || { echo "SANKHYA_API_KEY ausente ou muito curta." >&2; exit 1; }
  backend_env="backend/.env.production"
  [[ -f "$backend_env" ]] || { echo "Arquivo $backend_env ausente." >&2; exit 1; }
  temp_env="$(mktemp "backend/.env.production.XXXXXX")"
  trap 'rm -f "$temp_env"' EXIT
  chmod 600 "$temp_env"
  found_sankhya_key=false
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == SANKHYA_API_KEY=* ]]; then
      printf 'SANKHYA_API_KEY=%s\n' "$SANKHYA_API_KEY" >> "$temp_env"
      found_sankhya_key=true
    else
      printf '%s\n' "$line" >> "$temp_env"
    fi
  done < "$backend_env"
  if [[ "$found_sankhya_key" == false ]]; then
    printf 'SANKHYA_API_KEY=%s\n' "$SANKHYA_API_KEY" >> "$temp_env"
  fi
  mv "$temp_env" "$backend_env"
  chmod 600 "$backend_env"
fi

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
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --wait postgres
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm --no-deps backend alembic upgrade head
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm --no-deps backend python -m app.bootstrap
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --wait backend worker frontend
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10); urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=10)"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T frontend \
  wget --quiet --tries=1 --spider http://127.0.0.1/
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend alembic current | grep -q '(head)'
worker_id="$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps -q worker)"
[[ -n "$worker_id" && "$(docker inspect -f '{{.State.Status}}' "$worker_id")" == "running" ]] || {
  echo "Worker nÃ£o estÃ¡ ativo." >&2
  exit 1
}
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
if [[ "${ACTIVATE_PROXY:-false}" == "true" ]] || \
   docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps -q proxy | grep -q .; then
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --wait proxy
  echo "Proxy Caddy ativado."
else
  echo "Caddy NÃO foi iniciado (ACTIVATE_PROXY=false). O Nginx atual pode continuar em :80."
fi
echo "Deploy concluído sem remover volumes nem executar downgrade. Valide login e integrações."
