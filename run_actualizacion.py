"""Orquestador del cron de actualización (Task 5.2).

Ejecuta los pasos de la actualización del Mundial, captura el resultado de cada
uno (OK/fallo + última línea de salida: nº de resultados, vía API/HTML, etc.) y
manda UNA notificación de resumen a Telegram por ejecución.

Lo llama actualizar.sh (que solo hace cd + lanza esto). Pensado para cron.
Uso:  python run_actualizacion.py
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

from notificar import enviar, formatear_resumen

ROOT = Path(__file__).resolve().parent
PY = sys.executable

# (nombre, comando, cwd). Orden = dependencias (resultados→ELO→…→seed).
PASOS = [
    ("resultados", [PY, "extraer_resultados.py"], ROOT),
    ("elo", [PY, "actualizar_torneo.py", "--solo-elo"], ROOT),
    ("fixtures", [PY, "actualizar_fixtures.py"], ROOT),
    ("designaciones", [PY, "extraer_designaciones.py", "--sofa"], ROOT),
    ("arbitros", [PY, "extraer_arbitros.py"], ROOT),
    ("predecir", [PY, "-m", "predictor.cli"], ROOT),
    ("torneo", [PY, "-m", "predictor.tournament"], ROOT),
    ("validar", [PY, "-m", "predictor.validar_outputs"], ROOT),
    ("rendimiento", [PY, "-m", "predictor.rendimiento"], ROOT),
    ("seed", ["npm", "run", "db:seed"], ROOT / "web"),
]


def _ultima_linea(texto: str) -> str:
    lineas = [l.strip() for l in (texto or "").splitlines() if l.strip()]
    return lineas[-1][:140] if lineas else ""


def ejecutar_paso(nombre: str, cmd: list[str], cwd: Path) -> dict:
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=1800)
        ok = r.returncode == 0
        detalle = _ultima_linea(r.stdout) if ok else _ultima_linea(r.stderr) or _ultima_linea(r.stdout)
        return {"nombre": nombre, "ok": ok, "detalle": detalle}
    except subprocess.TimeoutExpired:
        return {"nombre": nombre, "ok": False, "detalle": "timeout (>30 min)"}
    except FileNotFoundError as e:
        return {"nombre": nombre, "ok": False, "detalle": f"comando no encontrado: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"nombre": nombre, "ok": False, "detalle": str(e)[:140]}


def main() -> None:
    pasos = []
    for nombre, cmd, cwd in PASOS:
        res = ejecutar_paso(nombre, cmd, cwd)
        pasos.append(res)
        marca = "OK" if res["ok"] else "FALLO"
        print(f"[{marca}] {nombre}: {res['detalle']}")

    ts = dt.datetime.now().strftime("%d/%m %H:%M")
    enviar(formatear_resumen(pasos, ts))
    # Exit code != 0 si algún paso crítico falló (para el log del cron).
    if any(not p["ok"] for p in pasos):
        sys.exit(1)


if __name__ == "__main__":
    main()
