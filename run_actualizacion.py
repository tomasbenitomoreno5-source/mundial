"""Orquestador del cron de actualización (Task 5.2).

Ejecuta los pasos de la actualización del Mundial, captura el resultado de cada
uno (estado + última línea de salida) y manda UNA notificación de resumen a
Telegram por ejecución.

Estados por paso:
  · ok   — el paso hizo su trabajo.
  · warn — corrió sin reventar pero DEGRADADO: fuente bloqueada, 0 datos nuevos,
           conservó lo previo, etc. Se detecta por código de salida 3 o por
           patrones de bloqueo en la salida (red de seguridad para extractores
           que hoy salen con código 0 aunque la fuente esté caída).
  · fail — fallo duro: excepción, crash, timeout, código de salida inesperado.

El encabezado del mensaje es ✅ / ⚠️ / ❌ según el peor estado, así que un cron
con la fuente bloqueada YA NO se reporta como ✅.

Cada ejecución deja un log completo en logs/cron_<ts>.log (stdout+stderr de cada
paso) para poder investigar. Si el propio orquestador revienta, manda igualmente
un ❌ a Telegram.

Lo llama actualizar.sh. Uso:  python run_actualizacion.py
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import subprocess
import sys
import traceback
from pathlib import Path

from notificar import enviar, formatear_resumen

ROOT = Path(__file__).resolve().parent
PY = sys.executable
LOG_DIR = ROOT / "logs"
LOG_RETENCION = 60  # nº de logs de ejecución a conservar

# (nombre, comando, cwd). Orden = dependencias (resultados→ELO→…→seed).
PASOS = [
    # --- Extracción de datos (fuentes nuevas tras la migración) ---
    ("fixtures", [PY, "extraer_fixtures_espn.py"], ROOT),          # cruces de eliminatoria (ESPN)
    ("resultados", [PY, "extraer_resultados_espn.py"], ROOT),      # ESPN
    ("stats", [PY, "extraer_stats_espn.py"], ROOT),                # ESPN + FotMob (xG)
    ("fechas", [PY, "extraer_fechas_espn.py"], ROOT),              # ESPN
    ("elo", [PY, "actualizar_torneo.py", "--solo-elo"], ROOT),     # eloratings (sin cambios)
    ("designaciones", [PY, "extraer_designaciones_espn.py"], ROOT),  # ESPN + Wikipedia
    ("pool_arbitro", [PY, "extraer_pool_arbitro_espn.py"], ROOT),    # tarjetas/penaltis por partido (eventos ESPN)
    ("arbitros", [PY, "extraer_arbitros.py", "--merge"], ROOT),      # fusiona pool -> arbitros.csv (carrera conservada)
    ("plantillas", [PY, "extraer_plantillas_espn.py"], ROOT),        # telemetría jugador (FotMob, incl. xG jugador)
    # --- Cómputo y publicación ---
    ("predecir", [PY, "-m", "predictor.cli"], ROOT),
    ("torneo", [PY, "-m", "predictor.tournament"], ROOT),
    ("validar", [PY, "-m", "predictor.validar_outputs"], ROOT),
    ("rendimiento", [PY, "-m", "predictor.rendimiento",
                     "--desde", "2026-06-01", "--torneo", "World Cup"], ROOT),  # solo Mundial
    ("seed", ["npm", "run", "db:seed"], ROOT / "web"),
]
# DEFERIDOS (baja urgencia):
#  - REFRESCO de carrera del árbitro: la carrera (partidos/amarillas/rojas de por
#    vida) se conserva del estado pre-bloqueo en arbitros.csv; worldreferee solo
#    cubre 37/51 (regresión), así que NO se refresca. El POOL por partido (tarjetas
#    casa/fuera, 1ª/2ª, penaltis) SÍ se actualiza vía pool_arbitro + arbitros --merge.
#  - bios/valor de mercado (Transfermarkt): extractor por construir (necesita IP
#    residencial / dump). El modelo de jugador está parqueado; la telemetría de
#    jugador (FotMob) SÍ se extrae ya (paso `plantillas`).

# Convención de códigos de salida: 0 = ok · 3 = degradado/bloqueo · otro = fallo.
# Todos los pasos del cron la respetan (extractores nuevos + validar exit 1, etc.),
# así que clasificamos SOLO por código de salida. (Antes había una heurística de
# patrones para los extractores viejos que salían con 0; daba falsos positivos
# —p.ej. "403" dentro de "1403 partidos"— y ya no hace falta.)
RC_WARN = 3

log = logging.getLogger("cron")


def _ultima_linea(texto: str) -> str:
    lineas = [l.strip() for l in (texto or "").splitlines() if l.strip()]
    if not lineas:
        return ""
    # Quita el prefijo de nivel de log (INFO/WARNING/...) si el extractor loguea
    # con ese formato, para que el detalle del mensaje quede limpio.
    return re.sub(r"^(INFO|WARNING|ERROR|DEBUG|CRITICAL)\s+", "", lineas[-1])[:140]


def _clasificar(returncode: int, stdout: str, stderr: str) -> tuple[str, str]:
    """(estado, detalle) según el código de salida (0 ok · 3 degradado · otro fallo).

    Detalle desde stdout y, si está vacío, stderr (los extractores que usan
    `logging` escriben a stderr; los que usan print(), a stdout).
    """
    detalle = _ultima_linea(stdout) or _ultima_linea(stderr)
    if returncode == 0:
        return "ok", detalle
    if returncode == RC_WARN:
        return "warn", detalle
    return "fail", _ultima_linea(stderr) or _ultima_linea(stdout) or f"código {returncode}"


def ejecutar_paso(nombre: str, cmd: list[str], cwd: Path) -> dict:
    log.info("── inicio paso «%s» (%s)", nombre, " ".join(cmd))
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=1800)
        # Log completo de la salida del paso para poder investigar.
        if r.stdout:
            log.info("[%s] stdout:\n%s", nombre, r.stdout.rstrip())
        if r.stderr:
            log.info("[%s] stderr:\n%s", nombre, r.stderr.rstrip())
        estado, detalle = _clasificar(r.returncode, r.stdout, r.stderr)
        return {"nombre": nombre, "estado": estado, "detalle": detalle}
    except subprocess.TimeoutExpired:
        log.error("[%s] timeout (>30 min)", nombre)
        return {"nombre": nombre, "estado": "fail", "detalle": "timeout (>30 min)"}
    except FileNotFoundError as e:
        log.error("[%s] comando no encontrado: %s", nombre, e)
        return {"nombre": nombre, "estado": "fail", "detalle": f"comando no encontrado: {e}"}
    except Exception as e:  # noqa: BLE001
        log.exception("[%s] excepción inesperada", nombre)
        return {"nombre": nombre, "estado": "fail", "detalle": str(e)[:140]}


def _configurar_logging(run_ts: str) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    logfile = LOG_DIR / f"cron_{run_ts}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(logfile, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    return logfile


def _limpiar_logs_viejos() -> None:
    logs = sorted(LOG_DIR.glob("cron_*.log"))
    for viejo in logs[:-LOG_RETENCION]:
        try:
            viejo.unlink()
        except OSError:
            pass


def main() -> None:
    run_ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    logfile = _configurar_logging(run_ts)
    log.info("=== cron actualización Mundial — %s ===", run_ts)

    try:
        pasos = []
        for nombre, cmd, cwd in PASOS:
            res = ejecutar_paso(nombre, cmd, cwd)
            pasos.append(res)
            log.info("[%s] => %s | %s", nombre, res["estado"].upper(), res["detalle"])

        ts = dt.datetime.now().strftime("%d/%m %H:%M")
        resumen = formatear_resumen(pasos, ts)
        # Si hubo problemas, apuntar al log para investigar.
        if any(p["estado"] != "ok" for p in pasos):
            resumen += f"\n  log: logs/{logfile.name}"
        enviar(resumen)
        log.info("resumen enviado:\n%s", resumen)
        _limpiar_logs_viejos()

        # Exit code != 0 si algún paso falló DURO (para el log del cron). Un
        # 'warn' no rompe el cron pero sí se ve en el ⚠️ del mensaje.
        if any(p["estado"] == "fail" for p in pasos):
            sys.exit(1)
    except Exception:  # noqa: BLE001 — el cron debe avisar aunque esto reviente
        tb = traceback.format_exc()
        log.exception("orquestador reventó")
        ts = dt.datetime.now().strftime("%d/%m %H:%M")
        enviar(f"❌ Mundial · cron {ts}\n  el orquestador reventó:\n  {_ultima_linea(tb)}\n"
               f"  log: logs/{logfile.name}")
        sys.exit(2)


if __name__ == "__main__":
    main()
