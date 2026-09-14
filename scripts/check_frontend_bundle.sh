#!/usr/bin/env bash
set -Eeuo pipefail
DIST_DIR="${1:-frontend/dist}"
[[ -d "$DIST_DIR" ]] || { echo "Bundle não encontrado: $DIST_DIR" >&2; exit 1; }
if grep -R -E "(localhost|127\.0\.0\.1):(8000|5173)" "$DIST_DIR"; then
  echo "ERRO: endpoint local encontrado no bundle de produção." >&2
  exit 1
fi
echo "Bundle sem endpoints locais proibidos."
