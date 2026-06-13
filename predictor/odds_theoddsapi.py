"""Cuotas de mercado (The Odds API) -> data/cuotas_mercado.csv.

The Odds API (plan gratis, 500 req/mes) es la única fuente que da cuotas del
Mundial 2026 EN VIVO y gratis, pero solo 1X2 (h2h) + O/U goles (totals). Los
mercados ricos (props/córners/tarjetas) están de pago en todos los proveedores
(ver decisión 2026-06-13). Aquí bajamos lo que sí es gratis y lo dejamos en
formato que cruza con la salida del modelo (predicciones_largo_py.csv) por
(partido_id, mercado, ambito, evento, linea, periodo).

Coste por llamada = nº regiones × nº mercados. Usamos regions=eu, markets=
h2h,totals => 2 peticiones por refresco. Con 1 refresco/día ~60/mes.

La clave vive en theoddsapi.env (gitignored) o en la variable THEODDSAPI_KEY.
"""

from __future__ import annotations

import csv
import json
import statistics
import urllib.parse
import urllib.request
from pathlib import Path

from . import config

SPORT = "soccer_fifa_world_cup"
BASE = "https://api.the-odds-api.com/v4"
REGIONS = "eu"           # eu da Pinnacle/Bet365/Betfair... barato (1 región)
MARKETS = "h2h,totals"   # lo único gratis para el Mundial
ODDS_FORMAT = "decimal"

CUOTAS_CSV = config.DATA_DIR / "cuotas_mercado.csv"
ENV_FILE = config.REPO_ROOT / "theoddsapi.env"

# The Odds API usa nombres en inglés; difieren 4 del canon del dataset.
NAME_MAP = {
    "Cape Verde": "Cabo Verde",
    "Czech Republic": "Czechia",
    "Ivory Coast": "Côte d'Ivoire",
    "Turkey": "Türkiye",
}


def _canon(name: str) -> str:
    return NAME_MAP.get(name.strip(), name.strip())


def cargar_clave() -> str:
    import os

    k = os.environ.get("THEODDSAPI_KEY")
    if k:
        return k.strip()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("THEODDSAPI_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError(
        "Falta THEODDSAPI_KEY (variable de entorno o theoddsapi.env)."
    )


def _cargar_fixtures() -> dict[frozenset[str], dict]:
    """frozenset({equipo_a, equipo_b}) -> {partido_id, equipo_a, equipo_b, fecha}."""
    idx: dict[frozenset[str], dict] = {}
    with open(config.PARTIDOS_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            a, b = r["equipo_a"].strip(), r["equipo_b"].strip()
            idx[frozenset((a, b))] = {
                "partido_id": r["partido_id"].strip(),
                "equipo_a": a,
                "equipo_b": b,
                "fecha": r.get("fecha", "").strip(),
            }
    return idx


def fetch_odds(api_key: str) -> list[dict]:
    qs = urllib.parse.urlencode(
        {"apiKey": api_key, "regions": REGIONS, "markets": MARKETS,
         "oddsFormat": ODDS_FORMAT}
    )
    url = f"{BASE}/sports/{SPORT}/odds/?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "mundial/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        rem = resp.headers.get("x-requests-remaining")
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, dict) and data.get("message"):
        raise RuntimeError(f"The Odds API: {data['message']}")
    return data, rem  # type: ignore[return-value]


def _devig(implied: dict[str, float]) -> dict[str, float]:
    """Quita el margen de la casa normalizando a suma 1."""
    s = sum(implied.values())
    if s <= 0:
        return implied
    return {k: v / s for k, v in implied.items()}


def _consenso(odds: list[float]) -> tuple[float, float]:
    """(mediana, máximo) de cuotas decimales entre casas."""
    return statistics.median(odds), max(odds)


def construir_filas(eventos: list[dict]) -> tuple[list[dict], list[str]]:
    fixtures = _cargar_fixtures()
    filas: list[dict] = []
    sin_match: list[str] = []

    for ev in eventos:
        home, away = _canon(ev["home_team"]), _canon(ev["away_team"])
        fx = fixtures.get(frozenset((home, away)))
        if not fx:
            sin_match.append(f"{ev['home_team']} vs {ev['away_team']}")
            continue
        a, b = fx["equipo_a"], fx["equipo_b"]
        base = {"partido_id": fx["partido_id"], "fecha": fx["fecha"],
                "equipo_a": a, "equipo_b": b}

        # --- recolectar cuotas por mercado/resultado entre casas -----------
        h2h: dict[str, list[float]] = {"gana_A": [], "empate": [], "gana_B": []}
        # totals[linea]["over"/"under"] = [cuotas]
        tot: dict[str, dict[str, list[float]]] = {}

        for bk in ev.get("bookmakers", []):
            for m in bk.get("markets", []):
                if m["key"] == "h2h":
                    for o in m["outcomes"]:
                        nm = _canon(o["name"])
                        if nm == a:
                            h2h["gana_A"].append(o["price"])
                        elif nm == b:
                            h2h["gana_B"].append(o["price"])
                        elif o["name"].lower() in ("draw", "tie", "empate"):
                            h2h["empate"].append(o["price"])
                elif m["key"] == "totals":
                    for o in m["outcomes"]:
                        linea = str(o.get("point", "")).strip()
                        if not linea:
                            continue
                        ev_ou = "over" if o["name"].lower() == "over" else "under"
                        tot.setdefault(linea, {}).setdefault(ev_ou, []).append(
                            o["price"])

        # --- 1X2 (de-vig conjunto de los 3 resultados) ---------------------
        if all(h2h[k] for k in h2h):
            medias = {k: _consenso(v) for k, v in h2h.items()}
            implied = {k: 1.0 / medias[k][0] for k in medias}
            probs = _devig(implied)
            for k in ("gana_A", "empate", "gana_B"):
                filas.append({**base, "mercado": "1X2", "ambito": "-",
                              "evento": k, "linea": "-", "periodo": "FT",
                              "cuota_media": round(medias[k][0], 3),
                              "cuota_max": round(medias[k][1], 3),
                              "prob_implicita": round(probs[k], 4),
                              "n_casas": len(h2h[k])})

        # --- O/U goles TOTAL (de-vig over+under por línea) -----------------
        for linea, ou in tot.items():
            if "over" not in ou or "under" not in ou:
                continue
            mo, mu = _consenso(ou["over"]), _consenso(ou["under"])
            probs = _devig({"over": 1.0 / mo[0], "under": 1.0 / mu[0]})
            for evt, med in (("over", mo), ("under", mu)):
                filas.append({**base, "mercado": "goles", "ambito": "TOTAL",
                              "evento": evt, "linea": linea, "periodo": "FT",
                              "cuota_media": round(med[0], 3),
                              "cuota_max": round(med[1], 3),
                              "prob_implicita": round(probs[evt], 4),
                              "n_casas": len(ou[evt])})

    return filas, sin_match


COLS = ["partido_id", "fecha", "equipo_a", "equipo_b", "mercado", "ambito",
        "evento", "linea", "periodo", "cuota_media", "cuota_max",
        "prob_implicita", "n_casas"]


def escribir_csv(filas: list[dict]) -> str:
    config.DATA_DIR.mkdir(exist_ok=True)
    with open(CUOTAS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter=";")
        w.writeheader()
        for r in filas:
            row = dict(r)
            # decimal con coma para consistencia con el resto de CSVs
            for c in ("cuota_media", "cuota_max", "prob_implicita"):
                row[c] = str(row[c]).replace(".", ",")
            w.writerow(row)
    return str(CUOTAS_CSV)


def actualizar() -> dict:
    """Punto de entrada para el cron. Devuelve resumen para notificar."""
    key = cargar_clave()
    eventos, rem = fetch_odds(key)
    filas, sin_match = construir_filas(eventos)
    ruta = escribir_csv(filas)
    partidos = len({f["partido_id"] for f in filas})
    return {"ruta": ruta, "eventos_api": len(eventos), "partidos_casados": partidos,
            "filas": len(filas), "sin_match": sin_match, "req_restantes": rem}


if __name__ == "__main__":
    r = actualizar()
    print(f"Escrito {r['ruta']}")
    print(f"  eventos API: {r['eventos_api']} | partidos casados: {r['partidos_casados']}"
          f" | filas: {r['filas']}")
    print(f"  peticiones restantes (mes): {r['req_restantes']}")
    if r["sin_match"]:
        print(f"  SIN MATCH ({len(r['sin_match'])}): {r['sin_match']}")
