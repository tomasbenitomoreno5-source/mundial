"""Notificaciones a Telegram (Task 5.2).

Credenciales (en este orden de prioridad):
  1. Variables de entorno MUNDIAL_TG_TOKEN / MUNDIAL_TG_CHAT.
  2. Fichero `telegram.env` junto a este script (KEY=VALUE), FUERA de git
     (.gitignore) — para no hardcodear el secreto en el código versionado.

Sin credenciales: imprime el mensaje por stdout (no rompe el cron).
"""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
from pathlib import Path

CRED_FILE = Path(__file__).resolve().parent / "telegram.env"


def _credenciales() -> tuple[str | None, str | None]:
    """Token y chat_id desde env vars o, si faltan, desde telegram.env."""
    token = os.environ.get("MUNDIAL_TG_TOKEN")
    chat = os.environ.get("MUNDIAL_TG_CHAT")
    if (token and chat) or not CRED_FILE.exists():
        return token, chat
    vals = {}
    for line in CRED_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    return token or vals.get("MUNDIAL_TG_TOKEN"), chat or vals.get("MUNDIAL_TG_CHAT")


def enviar(texto: str) -> bool:
    """Envía un mensaje a Telegram. Devuelve True si se mandó."""
    token, chat = _credenciales()
    if not (token and chat):
        print("[notificación — sin Telegram configurado]\n" + texto)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=15) as r:
            return r.status == 200
    except Exception as e:  # noqa: BLE001 — el cron nunca debe romper por la notif
        print(f"[notificación falló: {e}]\n{texto}")
        return False


_MARCA = {"ok": "✅", "warn": "⚠️", "fail": "❌"}


def _estado(p: dict) -> str:
    """Estado del paso: 'ok' | 'warn' | 'fail'.

    Compatibilidad: si el paso solo trae el bool `ok`, se mapea a ok/fail.
    """
    est = p.get("estado")
    if est in _MARCA:
        return est
    return "ok" if p.get("ok", True) else "fail"


def formatear_resumen(pasos: list[dict], ts: str) -> str:
    """Construye el resumen de una ejecución del cron.

    pasos: lista de {nombre, estado: 'ok'|'warn'|'fail', detalle: str}
    (también acepta el antiguo {ok: bool}).

    Encabezado: ✅ todo OK · ⚠️ algún paso degradado (p.ej. fuente bloqueada)
    · ❌ algún fallo duro. El ❌/⚠️ del encabezado hace imposible confundir una
    ejecución con problemas con una correcta.
    """
    estados = [_estado(p) for p in pasos]
    n = len(pasos)
    n_fail = estados.count("fail")
    n_warn = estados.count("warn")
    n_ok = n - n_fail - n_warn

    # Semáforo: salud global de un vistazo (primera línea).
    if n_fail:
        sem, palabra = "🔴", "REVISAR"
    elif n_warn:
        sem, palabra = "🟠", "AVISOS"
    else:
        sem, palabra = "🟢", "TODO OK"

    lineas = [f"{sem} {palabra} · {n_ok}/{n}", f"Mundial · cron {ts}"]
    # Una línea por extractor: icono + nombre + dato clave (si lo hay).
    for p, e in zip(pasos, estados):
        detalle = p.get("detalle", "").strip()
        lineas.append(f"{_MARCA[e]} {p['nombre']} — {detalle}" if detalle
                      else f"{_MARCA[e]} {p['nombre']}")
    return "\n".join(lineas)
