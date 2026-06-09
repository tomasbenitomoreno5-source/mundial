#!/usr/bin/env bash
set -e
# WORKDIR = /app/web. La DB está en el volumen /data.
# Si el volumen está vacío (primer arranque sin copia de la imagen), siembra.
if [ ! -f /data/dev.db ]; then
  echo "[entrypoint] DB no encontrada en /data, sembrando…"
  npx prisma db push --skip-generate
  npm run db:seed
fi
echo "[entrypoint] arrancando next start"
exec npm run start
