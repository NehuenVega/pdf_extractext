#!/bin/sh
# Prueba de carga fija con Vegeta (modelo abierto).
#
# Perfil de la consigna: 50 req/s constantes durante 30 s (1.500 pedidos),
# rotando los PDFs de prueba, con timeout de cliente de 30 s.
#
# "Modelo abierto": Vegeta dispara 50 pedidos por segundo pase lo que pase,
# aunque el servicio no llegue a responder los anteriores. Si la capacidad es
# menor que 50 req/s, la cola crece sin parar; el desafío es que el servicio
# maneje esa congestión sin que las respuestas superen el timeout.
#
# Uso (desde la raíz del repo):
#   docker compose --profile stress run --rm vegeta
#   docker compose --profile stress run --rm -e RATE=30 vegeta
# Después, para compararlo con el profesor:
#   python scripts/compare_results.py
set -eu

STRESS_DIR=$(cd "$(dirname "$0")/.." && pwd)
TARGET_URL=${TARGET_URL:-http://localhost:8080/extract}
RATE=${RATE:-50}
DURATION=${DURATION:-30s}
TIMEOUT=${TIMEOUT:-30s}

# Un target por PDF: Vegeta los recorre en ronda (round-robin), así que en
# 1.500 pedidos cada PDF se pide la misma cantidad de veces.
targets=$(mktemp)
for pdf in "$STRESS_DIR"/pdfs/*.pdf; do
  [ -e "$pdf" ] || { echo "No hay PDFs en $STRESS_DIR/pdfs" >&2; exit 1; }
  printf 'POST %s\nContent-Type: application/pdf\n@%s\n\n' "$TARGET_URL" "$pdf"
done > "$targets"

mkdir -p "$STRESS_DIR/results"
out="$STRESS_DIR/results/vegeta-${RATE}rps-$(date -u +%Y-%m-%dT%H-%M-%SZ)"

echo "Atacando $TARGET_URL a $RATE req/s durante $DURATION (timeout $TIMEOUT)..."
# -max-body=0: Vegeta lee cada respuesta completa (la latencia incluye toda la
# transferencia) pero no la guarda; si no, el archivo de resultados ocuparía
# cientos de MB con el Markdown de cada respuesta.
vegeta attack -targets="$targets" -rate="$RATE/1s" -duration="$DURATION" -timeout="$TIMEOUT" \
  -max-body=0 > "$out.bin"

vegeta report "$out.bin" | tee "$out.txt"
vegeta report -type='hist[0,1s,2s,5s,10s,15s,20s,25s,30s]' "$out.bin" | tee -a "$out.txt"
vegeta report -type=json "$out.bin" > "$out.json"
# Un renglón por pedido (código y latencia): permite calcular percentiles
# solo de los pedidos exitosos, que el reporte de Vegeta no separa.
vegeta encode --to csv "$out.bin" > "$out.csv"
vegeta plot -title="Vegeta $RATE req/s" "$out.bin" > "$out.html"

echo "Resultados en tests/stress/results/$(basename "$out").{txt,json,csv,html}"
