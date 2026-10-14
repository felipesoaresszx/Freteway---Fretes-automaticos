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
# Preserve ajustes feitos diretamente no servidor antes de atualizar. Arquivos
# ignorados (env, storage e backups) permanecem no lugar. Nao reaplique o stash
# automaticamente: isso publicaria codigo que nao passou pelo CI.
if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
  backup_dir="/home/ubuntu/freteway-server-backups"
  install -m 700 -d "$backup_dir"
  backup_stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
  git stash push --include-untracked -m "pre-ci-deploy-$backup_stamp"
  stash_revision="$(git rev-parse refs/stash)"
  backup_file="$backup_dir/local-changes-$backup_stamp.patch"
  (umask 077; git stash show --patch --binary --include-untracked "$stash_revision" > "$backup_file")
  echo "Alteracoes locais preservadas em stash $stash_revision e $backup_file."
fi
git checkout main
git merge --ff-only origin/main

ENV_FILE=.env.production COMPOSE_FILE=docker-compose.production.yml ./deploy/deploy.sh

curl --fail --silent --show-error --max-time 15 http://127.0.0.1/health >/dev/null
echo "Deploy automático concluído em $(git rev-parse --short HEAD)."
