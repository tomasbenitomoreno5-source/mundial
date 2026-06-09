#!/usr/bin/env bash
# Despliegue / actualización de CÓDIGO en el servidor.
# Uso:  bash deploy/deploy.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> git pull"
git pull --ff-only

echo "==> deps Python (venv)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -e .

echo "==> web: install + prisma + seed + build"
cd web
npm ci
npx prisma generate
npx prisma db push --skip-generate
npm run db:seed
npm run build

echo "==> reiniciar servicio"
sudo systemctl restart mundial-web
echo "OK: desplegado"
