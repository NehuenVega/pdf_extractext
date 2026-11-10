#!/bin/sh
# Corre la prueba spike de k6 contra todos los PDFs de tests/stress/pdfs.
#
# k6 no puede listar carpetas desde el script, así que este wrapper arma la
# lista de PDFs y se la pasa en PDF_FILES. Así la prueba usa la carpeta
# oficial de la cátedra tal como venga, sin editar el script.
#
# Uso (desde la raíz del repo):
#   docker compose --profile stress run --rm k6
#   docker compose --profile stress run --rm -e UPLOAD_MODE=multipart k6
set -eu

STRESS_DIR=$(cd "$(dirname "$0")/.." && pwd)

files=""
for pdf in "$STRESS_DIR"/pdfs/*.pdf; do
  [ -e "$pdf" ] || { echo "No hay PDFs en $STRESS_DIR/pdfs" >&2; exit 1; }
  files="${files:+$files,}$(basename "$pdf")"
done

mkdir -p "$STRESS_DIR/results"
echo "PDFs: $files"

exec k6 run \
  -e BASE_URL="${BASE_URL:-http://localhost:8080}" \
  -e PDF_DIR="$STRESS_DIR/pdfs" \
  -e PDF_FILES="$files" \
  -e RESULTS_DIR="$STRESS_DIR/results" \
  -e UPLOAD_MODE="${UPLOAD_MODE:-binary}" \
  "$STRESS_DIR/k6/spike.js"
