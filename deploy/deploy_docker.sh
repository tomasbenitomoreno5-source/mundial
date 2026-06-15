#!/usr/bin/env bash
# Deploy de CÓDIGO en el servidor Docker.
#
# Reconstruye la imagen de la web con el código nuevo (git pull + build), aplica
# el schema a la DB del VOLUMEN y recarga los datos. El volumen `dbdata` tapa el
# /data de la imagen, así que el `db push`/`seed` del Dockerfile NO actualiza la
# DB en marcha: hay que hacerlo aquí con `exec` contra el contenedor vivo.
#
# ¿Cuál usar?
#   - Código nuevo (features, páginas, schema)  -> ESTE script.
#   - Solo resultados/predicciones del día       -> actualizar_docker.sh (cron).
#
# Uso:  bash deploy/deploy_docker.sh
set -euo pipefail
cd "$(dirname "$0")/.."   # raíz del repo (donde está docker-compose.yml)

echo "==> git pull"
git pull --ff-only

echo "==> rebuild + (re)arranque del contenedor web"
docker compose up -d --build

echo "==> esperar a que el contenedor web acepte comandos"
sleep 5

echo "==> prisma db push (crea/actualiza tablas en la DB del volumen)"
docker compose exec -T web npx prisma db push --skip-generate

echo "==> seed (recarga los CSV de data/ en la DB del volumen)"
docker compose exec -T web npm run db:seed

echo "OK: desplegado (Docker). La web (ISR) recoge los cambios en <=60s."
