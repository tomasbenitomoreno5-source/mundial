"""Mercados de jugador (port del bloque 7 del R, Task 6.1).

Hasta ahora la web calculaba las probabilidades de jugador con un Poisson naíf
en seed.ts (sobre la media bruta, sin rival ni minutos ni bootstrap). Esto es
el motor real: pool por jugador (50% sus partidos + 50% vs estilo del rival),
bootstrap escalado a 80', y los mercados (anotar, asistir, remates, pases,
entradas, faltas, tarjeta, paradas, primer goleador).

Usa telemetria_full.csv (plantillas completas) filtrada por convocatorias.csv.
Salida: data/predicciones_jugador_py.csv (formato largo).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .pool import _peso_recencia
from .style import StyleKNN

# Catálogo de mercados de jugador, alineado con web/lib/player-markets.ts
# (mismos `key` para que la web los renderice). (key, métrica, tipo).
# Métricas especiales: __goal_or_assist__, __yellow_card__.
MERCADOS_JUGADOR = [
    ("anytime_scorer", "goals", "binary"),
    ("assist", "goalAssist", "binary"),
    ("goal_or_assist", "__goal_or_assist__", "binary"),
    ("big_chance_created", "bigChanceCreated", "binary"),
    ("penalty_won", "penaltyWon", "binary"),
    ("yellow_card", "__yellow_card__", "binary"),
    ("shots", "totalShots", "ou"),
    ("shots_on_target", "onTargetScoringAttempt", "ou"),
    ("shots_off_target", "shotOffTarget", "ou"),
    ("shots_blocked", "blockedScoringAttempt", "ou"),
    ("big_chances_missed", "bigChanceMissed", "ou"),
    ("passes", "totalPass", "ou"),
    ("accurate_passes", "accuratePass", "ou"),
    ("key_passes", "keyPass", "ou"),
    ("crosses", "totalCross", "ou"),
    ("accurate_crosses", "accurateCross", "ou"),
    ("long_balls", "totalLongBalls", "ou"),
    ("dribbles", "wonContest", "ou"),
    ("dribbles_att", "totalContest", "ou"),
    ("touches", "touches", "ou"),
    ("tackles", "totalTackle", "ou"),
    ("won_tackles", "wonTackle", "ou"),
    ("interceptions", "interceptionWon", "ou"),
    ("clearances", "totalClearance", "ou"),
    ("recoveries", "ballRecovery", "ou"),
    ("duels_won", "duelWon", "ou"),
    ("aerials_won", "aerialWon", "ou"),
    ("blocks", "outfielderBlock", "ou"),
    ("fouls", "fouls", "ou"),
    ("fouled", "wasFouled", "ou"),
    ("offsides", "totalOffside", "ou"),
    ("possession_lost", "possessionLostCtrl", "ou"),
    ("dispossessed", "dispossessed", "ou"),
    ("saves", "saves", "ou"),
]
# Mercados cuya P(si) se capa (eventos de gol: muestra pequeña perfecta → no 1.0).
_CAP_KEYS = {"anytime_scorer", "assist", "goal_or_assist"}
# Métricas de conteo a simular = todas las del catálogo (no especiales).
CNT_COLS = sorted({m for _, m, _ in MERCADOS_JUGADOR if not m.startswith("__")})

# Jugador y evento en columnas SEPARADAS (over/under, si/no deben distinguirse).
LARGO_COLS = [
    "partido_id", "fecha", "equipo_a", "equipo_b", "mercado", "jugador", "team",
    "evento", "linea", "probabilidad", "n_apariciones",
]
# Recencia + fuerza-rival en el pool de jugador: desactivado (concentra pools
# pequeños y añade ruido). Flag para experimentar/medir, no para producción.
_DEBUG_PONDERAR = False
# Cap de P(anotar)/P(asistir): salvaguarda contra muestras pequeñas "perfectas".
# Con los minutos esperados (un suplente apenas juega → P baja) este cap rara vez
# actúa, pero protege el caso extremo de muestra de 1 partido.
P_MAX_JUGADOR = 0.90


def cargar_telemetria() -> pd.DataFrame:
    tel = pd.read_csv(config.DATA_DIR / "telemetria_full.csv", sep=";",
                      encoding="utf-8-sig", low_memory=False)
    cols = ["minutesPlayed", "saves", "totalKeeperSweeper", *CNT_COLS]
    for c in cols:
        if c in tel.columns:
            tel[c] = pd.to_numeric(tel[c], errors="coerce").fillna(0.0)
    # Fecha por partido (para recencia del pool de jugador, mejora 2).
    if config.PARTIDO_FECHAS_CSV.exists():
        f = pd.read_csv(config.PARTIDO_FECHAS_CSV, sep=";", encoding="utf-8-sig",
                        dtype={"partido_id": str})[["partido_id", "fecha"]]
        tel["partido_id"] = tel["partido_id"].astype(str)
        tel = tel.merge(f, on="partido_id", how="left")
    return tel


def _convocatorias() -> dict[str, set]:
    p = config.DATA_DIR / "convocatorias.csv"
    if not p.exists():
        return {}
    conv = pd.read_csv(p, sep=";", encoding="utf-8-sig")
    return conv.groupby("equipo")["jugador"].agg(set).to_dict()


def seleccion_de_jugador(tel: pd.DataFrame, equipos_mundial: list[str],
                         convocatorias: dict[str, set]) -> dict[str, str]:
    """jugador -> selección (moda de home/away), filtrado a mundialistas y, si
    hay convocatorias, a los convocados de su selección."""
    apil = pd.concat([
        tel[["jugador", "home_team"]].rename(columns={"home_team": "equipo"}),
        tel[["jugador", "away_team"]].rename(columns={"away_team": "equipo"}),
    ])
    apil = apil[apil["equipo"].notna() & (apil["equipo"] != "")]
    modas = apil.groupby("jugador")["equipo"].agg(lambda s: s.mode().iat[0])
    wc = set(equipos_mundial)
    out = {}
    for jug, sel in modas.items():
        if sel not in wc:
            continue
        if convocatorias and jug not in convocatorias.get(sel, set()):
            continue  # no convocado → no juega el Mundial
        out[jug] = sel
    return out


def minutos_esperados_por_jugador(tel: pd.DataFrame, sel_jug: dict[str, str],
                                  stats: pd.DataFrame, cap: float = 85.0) -> dict[str, float]:
    """Minutos que se espera juegue cada jugador, PONDERADOS por tipo de partido.

    minutos_esp = Σ(min_i · w_i) / Σ(w_i sobre los partidos de su selección),
    con w = PESO_AMISTOSO (0.6) en amistosos y 1.0 en competitivos. Así los
    amistosos (donde se rota/descansa) pesan menos: un titular que descansa en
    amistosos pero juega la competición sube; un suplente que solo juega
    amistosos baja. Capta titular≈70-85' vs suplente≈pocos, alineado al Mundial.
    Partidos sin aparición cuentan como 0 min (van en el denominador).
    """
    # Peso por partido (de la columna torneo del backfill). Sin torneo → 1.0.
    sp = stats.drop_duplicates(["equipo_nombre", "partido_id"]).copy()
    if "torneo" in sp.columns:
        es_amist = sp["torneo"].fillna("").str.contains("friendl", case=False)
        sp["w"] = np.where(es_amist, config.PESO_AMISTOSO, 1.0)
    else:
        sp["w"] = 1.0
    den_sel = sp.groupby("equipo_nombre")["w"].sum().to_dict()
    peso_part = dict(zip(sp["partido_id"].astype(str), sp["w"]))

    t = tel[["jugador", "partido_id", "minutesPlayed"]].copy()
    t["w"] = t["partido_id"].astype(str).map(peso_part).fillna(1.0)
    num_jug = (t["minutesPlayed"] * t["w"]).groupby(t["jugador"]).sum().to_dict()

    out: dict[str, float] = {}
    for jug, sel in sel_jug.items():
        den = den_sel.get(sel, 0.0)
        out[jug] = float(min(num_jug.get(jug, 0.0) / den, cap)) if den > 0 else 0.0
    return out


def construir_pool_jugador(jugador: str, propia: str, rival: str,
                           tel: pd.DataFrame, knn: StyleKNN,
                           fuerza_map: dict[str, float] | None = None,
                           fecha_ref: str | None = None,
                           bandwidth: float = config.POOL_BANDWIDTH,
                           half_life: float = config.RECENCIA_HALF_LIFE_DIAS
                           ) -> pd.DataFrame | None:
    rows = tel[tel["jugador"] == jugador].copy()
    if len(rows) == 0:
        return None
    rows["oponente"] = np.where(rows["home_team"] == propia,
                                rows["away_team"], rows["home_team"])
    # General (50%): todos sus partidos, peso uniforme.
    rows_gen = rows.copy()
    rows_gen["peso"] = 1.0 / len(rows_gen)
    # Contextual (50%): partidos contra rivales en el KNN del rival real.
    w_vec = knn.pesos(rival)
    rows_ctx = rows[rows["oponente"].isin(w_vec)].copy()
    if len(rows_ctx):
        w = rows_ctx["oponente"].map(w_vec).to_numpy(dtype=float)
        rows_ctx["peso"] = w / w.sum()

    presente = np.array([len(rows_gen) > 0, len(rows_ctx) > 0])
    glob = np.array([0.5, 0.5]) * presente
    if glob.sum() == 0:
        return None
    glob = glob / glob.sum()
    rows_gen["peso"] *= glob[0]
    if len(rows_ctx):
        rows_ctx["peso"] *= glob[1]
    pool = pd.concat([rows_gen, rows_ctx], ignore_index=True)
    # DESACTIVADO (recencia + fuerza-rival): los pools de jugador son pequeños
    # (10-30 filas), y ponderarlos concentra el peso en muy pocas filas → ruido
    # que rompía el orden (defensas por encima de delanteros). Las técnicas de
    # pool grande (equipo) no aplican a jugador. Ver _DEBUG_PONDERAR.
    if _DEBUG_PONDERAR:
        if fuerza_map is not None:
            f_rival = fuerza_map.get(rival, 0.0)
            f_o = pool["oponente"].map(lambda o: fuerza_map.get(o, 0.0)).to_numpy(dtype=float)
            pool["peso"] *= np.exp(-((f_rival - f_o) ** 2) / (2 * bandwidth ** 2))
        if fecha_ref is not None and "fecha" in pool.columns:
            pool["peso"] *= _peso_recencia(pool["fecha"], fecha_ref, half_life)
        if pool["peso"].sum() <= 0:
            return None
    pool["peso"] = pool["peso"] / pool["peso"].sum()
    return pool


def simular_jugador(pool: pd.DataFrame, rng: np.random.Generator, minutos: float,
                    n_sim: int = config.N_SIM) -> dict[str, np.ndarray] | None:
    """Bootstrap escalado a los MINUTOS ESPERADOS del jugador (no a 80' fijos).

    `minutos` = cuánto suele jugar (minutos totales / partidos de su selección).
    Así un suplente que apenas juega tiene tasas bajas en todos los mercados, y
    un titular las tiene altas — sin asumir que todos juegan 80'.

    Las TASAS por-90 se estiman de las apariciones sustanciales (filtro
    escalonado ≥45/≥30/≥15) para que sean estables; luego se escalan a `minutos`.
    """
    if pool is None or len(pool) == 0:
        return None
    pool = pool[pool["minutesPlayed"] > 0]
    if len(pool) == 0:
        return None
    # Filas para estimar la tasa por-90 (estabilidad), con fallback a las que haya.
    p45 = pool[pool["minutesPlayed"] >= 45]
    if len(p45) >= 5:
        base = p45
    else:
        p30 = pool[pool["minutesPlayed"] >= 30]
        if len(p30) >= 3:
            base = p30
        else:
            p15 = pool[pool["minutesPlayed"] >= 15]
            base = p15 if len(p15) > 0 else pool
    pool = base.copy()
    pool["peso"] = pool["peso"] / pool["peso"].sum()

    idx = rng.choice(len(pool), size=n_sim, replace=True, p=pool["peso"].to_numpy())
    mins = pool["minutesPlayed"].to_numpy()[idx]
    escala = np.where(mins > 0, minutos / mins, 0.0)

    out: dict[str, np.ndarray] = {}
    for c in [c for c in CNT_COLS if c in pool.columns]:
        val = pool[c].to_numpy(dtype=float)[idx] * escala
        val = np.where(np.isnan(val) | (val < 0), 0.0, val)
        out[c] = np.where(val < 1,
                          rng.binomial(1, np.minimum(val, 1.0)),
                          np.round(val)).astype(int)
    return out


def es_portero(jugador: str, tel: pd.DataFrame) -> bool:
    r = tel[tel["jugador"] == jugador]
    if len(r) == 0:
        return False
    cond = (r["saves"] > 0) | ((r["minutesPlayed"] > 60) & (r.get("totalKeeperSweeper", 0) > 0))
    return float(cond.mean()) > 0.5


def _ratio(stats: pd.DataFrame, equipo: str, num: str, den: str, default: float) -> float:
    g = stats[stats["equipo_nombre"] == equipo]
    s_den = pd.to_numeric(g.get(den), errors="coerce").sum() if den in g.columns else 0
    s_num = pd.to_numeric(g.get(num), errors="coerce").sum() if num in g.columns else 0
    return float(s_num / s_den) if s_den > 0 else default


def _lineas_jugador(mu: float) -> list[float]:
    """5 líneas semienteras alrededor de la media (floor-1 .. +3), como la web."""
    if mu is None or np.isnan(mu) or mu < 0:
        return []
    c = np.floor(mu)
    out = {round(c + o + 0.5, 1) for o in range(-1, 4)}
    return sorted(x for x in out if x >= 0.5)


def mercados_jugador_partido(pid, fecha, eA, eB, sel_jug, tel, knn, stats,
                             lam_a, lam_b, rng, minutos_esp, fuerza_map,
                             n_sim=config.N_SIM) -> list[dict]:
    filas: list[dict] = []
    triv = config.LINEA_PROB_TRIVIAL_JUGADOR

    def push(j, team, mercado, evento, linea, prob):
        filas.append({
            "partido_id": pid, "fecha": fecha, "equipo_a": eA, "equipo_b": eB,
            "mercado": mercado, "jugador": j, "team": team, "evento": evento,
            "linea": linea, "probabilidad": round(max(0.0, min(1.0, float(prob))), 4),
        })

    lam_goles_jug: dict[str, float] = {}
    jugs = {eA: [j for j, s in sel_jug.items() if s == eA],
            eB: [j for j, s in sel_jug.items() if s == eB]}

    for propio, rival in ((eA, eB), (eB, eA)):
        # ratio amarilla/falta del equipo (para el mercado de tarjeta del jugador)
        ratio_yf = _ratio(stats, propio, "yellow_cards", "fouls", 0.10)
        portero = None  # cache es_portero por jugador
        for j in jugs[propio]:
            pool = construir_pool_jugador(j, propio, rival, tel, knn,
                                          fuerza_map=fuerza_map, fecha_ref=fecha)
            sim = simular_jugador(pool, rng, minutos_esp.get(j, 0.0), n_sim=n_sim)
            if sim is None:
                continue
            lam_goles_jug[j] = float(sim["goals"].mean())
            es_gk = es_portero(j, tel)
            for key, metric, tipo in MERCADOS_JUGADOR:
                if key == "saves" and not es_gk:
                    continue  # paradas solo para porteros
                if tipo == "binary":
                    if metric == "__goal_or_assist__":
                        p = float(((sim["goals"] >= 1) | (sim["goalAssist"] >= 1)).mean())
                    elif metric == "__yellow_card__":
                        # xG/datos no dan tarjeta directa: heurística faltas×ratio.
                        p = float((1 - np.exp(-sim["fouls"] * ratio_yf)).mean())
                    elif metric in sim:
                        p = float((sim[metric] >= 1).mean())
                    else:
                        continue
                    if key in _CAP_KEYS:
                        p = min(p, P_MAX_JUGADOR)
                    push(j, propio, key, "si", "-", p)
                    push(j, propio, key, "no", "-", 1 - p)
                else:  # over/under
                    if metric not in sim:
                        continue
                    v = sim[metric]
                    for L in _lineas_jugador(float(v.mean())):
                        po = float((v > L).mean())
                        if triv <= po <= 1 - triv:  # corta líneas triviales
                            push(j, propio, key, "over", L, po)
                            push(j, propio, key, "under", L, 1 - po)

    # Primer goleador (rescalado para no sobre-asignar a los pocos observados).
    lam_total = lam_a + lam_b
    if lam_goles_jug and lam_total > 0:
        for propio, lam_eq in ((eA, lam_a), (eB, lam_b)):
            obs = [j for j in jugs[propio] if j in lam_goles_jug]
            s = sum(lam_goles_jug[j] for j in obs)
            fac = min(1.0, 0.70 * lam_eq / s) if s > 0 else 1.0
            for j in obs:
                lam_goles_jug[j] *= fac
        p_un_gol = 1 - np.exp(-lam_total)
        suma_obs = sum(lam_goles_jug.values())
        for j, lam_j in lam_goles_jug.items():
            push(j, sel_jug.get(j, "-"), "primer_goleador", "si", "-",
                 (lam_j / lam_total) * p_un_gol)
        push("otro_jugador", "-", "primer_goleador", "si", "-",
             ((lam_total - suma_obs) / lam_total) * p_un_gol)
        push("ninguno", "-", "primer_goleador", "no_goal", "-", float(np.exp(-lam_total)))

    return filas


def predict_players(dataset, knn: StyleKNN, lambdas: dict[str, tuple[float, float]],
                    n_sim: int = config.N_SIM, seed: int = config.SEED) -> pd.DataFrame:
    """Genera el largo de mercados de jugador para los 72 partidos.

    lambdas: {partido_id: (lam_a, lam_b)} del motor de equipo (para 1er goleador).
    """
    from .strength import compute_strength

    tel = cargar_telemetria()
    conv = _convocatorias()
    sel_jug = seleccion_de_jugador(tel, dataset.equipos_mundial, conv)
    minutos_esp = minutos_esperados_por_jugador(tel, sel_jug, dataset.stats)
    fuerza_map = compute_strength(dataset.stats, dataset.equipos_mundial,
                                  usar_elo_mundo=not dataset.legacy)
    rng = np.random.default_rng(seed)

    filas: list[dict] = []
    for _, row in dataset.pred.iterrows():
        pid, fecha = row["partido_id"], str(row["fecha"])
        eA, eB = row["equipo_a"], row["equipo_b"]
        lam_a, lam_b = lambdas.get(pid, (1.3, 1.1))
        filas.extend(mercados_jugador_partido(
            pid, fecha, eA, eB, sel_jug, tel, knn, dataset.stats,
            lam_a, lam_b, rng, minutos_esp, fuerza_map, n_sim=n_sim))
    if not filas:
        return pd.DataFrame(columns=LARGO_COLS)
    df = pd.DataFrame(filas)
    # Confianza: nº de apariciones sustanciales (≥30 min) del jugador.
    n_ap = tel.groupby("jugador")["minutesPlayed"].apply(lambda s: int((s >= 30).sum()))
    df["n_apariciones"] = df["jugador"].map(n_ap).fillna(0).astype(int)
    return df[LARGO_COLS]


def write_players(largo: pd.DataFrame) -> str:
    config.DATA_DIR.mkdir(exist_ok=True)
    fout = str(config.DATA_DIR / "predicciones_jugador_py.csv")
    largo.to_csv(fout, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    return fout
