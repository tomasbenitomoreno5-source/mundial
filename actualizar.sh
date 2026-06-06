#!/usr/bin/env bash
# Actualiza los resultados del Mundial y recarga la DB. Idempotente: se puede
# correr tantas veces como se quiera. Pensado para un cron cada ~2h durante el
# torneo (captura cada partido en ≤2h de acabar).
#
# Instalar en cron (cada 2h):
#   crontab -e
#   0 */2 * * * /Users/xavirodriguez/Desktop/Personal/Proyects/football-analytics/mundial/actualizar.sh >> /tmp/mundial_update.log 2>&1
#
# El sitio web es ISR (revalidate 1800s), así que recoge los datos nuevos solo;
# no hace falta reconstruir ni reiniciar.

set -euo pipefail
cd "$(dirname "$0")"

echo "[$(date '+%Y-%m-%d %H:%M')] actualizando resultados…"
.venv/bin/python extraer_resultados.py

# Si quieres, aquí también podrías re-scrapear telemetría de los partidos
# jugados (extraer_plantillas.py) para enriquecer mercados/fichas.

cd web && npm run db:seed >/dev/null
echo "[$(date '+%Y-%m-%d %H:%M')] DB recargada. OK"
