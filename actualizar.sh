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

echo "[$(date '+%Y-%m-%d %H:%M')] 1/4 resultados…"
.venv/bin/python extraer_resultados.py

echo "[$(date '+%Y-%m-%d %H:%M')] 2/4 detectar rondas nuevas (eliminatorias)…"
.venv/bin/python actualizar_fixtures.py

echo "[$(date '+%Y-%m-%d %H:%M')] 3/4 re-predecir (mercados de los partidos nuevos)…"
.venv/bin/python -m predictor.cli
.venv/bin/python -m predictor.tournament

echo "[$(date '+%Y-%m-%d %H:%M')] 4/4 recargar DB…"
cd web && npm run db:seed >/dev/null
echo "[$(date '+%Y-%m-%d %H:%M')] OK"
