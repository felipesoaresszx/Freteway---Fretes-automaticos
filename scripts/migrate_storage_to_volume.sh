#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${STORAGE_SOURCE_DIR:-$ROOT_DIR/backend/storage}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.production}"
[[ -d "$SOURCE_DIR" ]] || { echo "Storage de origem não existe: $SOURCE_DIR" >&2; exit 1; }
find "$SOURCE_DIR" -type f -print -quit | grep -q . || { echo "Storage de origem está vazio; nada a migrar." >&2; exit 1; }

if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi
VOLUME_NAME="${APP_STORAGE_VOLUME_NAME:-freteway_app_storage}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y-%m-%d_%H%M%S)"
archive="$BACKUP_DIR/storage_${timestamp}.tar.gz"

source_files="$(find "$SOURCE_DIR" -type f | wc -l | tr -d ' ')"
source_bytes="$(du -sb "$SOURCE_DIR" | awk '{print $1}')"
echo "Origem: $SOURCE_DIR ($source_files arquivos; $source_bytes bytes em disco)"
echo "Destino: volume Docker $VOLUME_NAME"
echo "Backup prévio: $archive"
read -r -p "Digite MIGRAR_STORAGE para criar o backup e copiar: " confirmation
[[ "$confirmation" == "MIGRAR_STORAGE" ]] || { echo "Migração cancelada."; exit 1; }

tar -C "$SOURCE_DIR" -czf "$archive" .
[[ -s "$archive" ]] || { echo "Backup do storage falhou." >&2; exit 1; }

if docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
  existing="$(docker run --rm -v "$VOLUME_NAME:/data:ro" alpine:3.20 sh -c 'find /data -type f | wc -l')"
  [[ "$existing" -eq 0 ]] || {
    echo "Volume destino já contém $existing arquivos. Nada foi sobrescrito." >&2
    exit 1
  }
else
  docker volume create "$VOLUME_NAME" >/dev/null
fi

docker run --rm -v "$SOURCE_DIR:/source:ro" -v "$VOLUME_NAME:/dest" alpine:3.20 \
  sh -eu -c 'cp -a /source/. /dest/'
destination_files="$(docker run --rm -v "$VOLUME_NAME:/data:ro" alpine:3.20 sh -c 'find /data -type f | wc -l')"
[[ "$destination_files" -eq "$source_files" ]] || {
  echo "Contagem divergente: origem=$source_files destino=$destination_files. Preserve ambos e investigue." >&2
  exit 1
}
echo "Migração validada por contagem: $destination_files arquivos."
echo "Origem e backup foram preservados; não os apague antes da validação funcional."
