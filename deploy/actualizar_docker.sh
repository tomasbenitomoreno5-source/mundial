#!/usr/bin/env bash
# Wrapper para el cron del HOST: ejecuta el auto-update DENTRO del contenedor web.
# El scraper baja resultados y el seed reescribe la DB del volumen; la web (ISR)
# recoge los cambios sola.
#
# Cron (cada 2h):
#   0 */2 * * * /home/ubuntu/projects/mundial/deploy/actualizar_docker.sh >> /tmp/mundial_update.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."   # raíz del repo (donde está docker-compose.yml)
docker compose exec -T web bash /app/actualizar.sh
