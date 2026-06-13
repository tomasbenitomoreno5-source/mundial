#!/usr/bin/env bash
# Actualiza los resultados del Mundial, re-predice, recarga la DB y NOTIFICA a
# Telegram el resumen de la ejecución. Idempotente: se puede correr a discreción.
#
# Toda la lógica vive en run_actualizacion.py (orquesta los pasos, captura el
# resultado de cada uno y manda una notificación por ejecución). Este wrapper
# solo fija el directorio y el entorno.
#
# Notificaciones (Telegram) — configurar antes (ver deploy/DEPLOY.md):
#   export MUNDIAL_TG_TOKEN=<token del bot de @BotFather>
#   export MUNDIAL_TG_CHAT=<tu chat_id>
# Sin esas variables, el resumen se imprime por stdout (no rompe el cron).
#
# Cron (cada 2h):
#   0 */2 * * * /ruta/al/repo/mundial/actualizar.sh >> /tmp/mundial_update.log 2>&1
# Recomendación: ejecutar desde IP RESIDENCIAL (SofaScore bloquea datacenter).

set -uo pipefail
cd "$(dirname "$0")"

.venv/bin/python run_actualizacion.py
