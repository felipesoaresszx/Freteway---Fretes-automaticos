#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="/home/ubuntu/Freteway"
LOCK_FILE="/tmp/freteway-production-deploy.lock"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Outro deploy do FreteWay já está em execução." >&2
  exit 1
fi

cd "$ROOT_DIR"
# Permissoes de execucao ja sao versionadas. Ignore diferencas de modo locais
# para que um chmod externo nunca bloqueie a atualizacao do codigo.
git config core.fileMode false
git fetch --prune origin main
git checkout main
git merge --ff-only origin/main

ENV_FILE=.env.production COMPOSE_FILE=docker-compose.production.yml ./deploy/deploy.sh

curl --fail --silent --show-error --max-time 15 http://127.0.0.1/health >/dev/null
echo "Deploy automático concluído em $(git rev-parse --short HEAD)."
