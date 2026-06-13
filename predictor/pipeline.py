"""Orquestación: predice los 72 partidos y arma las salidas (bloque 8 del R)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .dataset import Dataset, load_dataset
from .markets import calcular_mercados
from .simulate import dixon_coles_matrix
from .pool import ajustar_pool_por_calidad_rival, construir_pool
from .simulate import simular_partido_bootstrap
from .strength import compute_strength
from .style import compute_style_knn

LARGO_COLS = [
    "partido_id", "fecha", "equipo_a", "equipo_b", "mercado", "ambito",
    "evento_o_jugador", "linea_o_target", "probabilidad", "periodo",
]


def factor_arbitro() -> dict[str, dict[str, float]]:
    """partido_id -> {'yellow_cards': fy, 'fouls': ff} del árbitro designado.

    Amarillas: tasa de carrera (amarillas/partidos_carrera) vs media; faltas:
    tasa de pool (faltas_pool/partidos_pool) vs media. Capado y con mínimos de
    muestra; árbitro no designado o sin muestra → factor 1.0 (neutro).
    """
    import csv

    if not (config.ARBITROS_CSV.exists() and config.CALENDARIO_CSV.exists()):
        return {}
    arb: dict[str, dict] = {}
    with open(config.ARBITROS_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            arb[str(r["sofa_id"]).strip()] = r

    def _num(x, d=0.0):
        try:
            return float(str(x).replace(",", "."))
        except (ValueError, TypeError):
            return d

    tasas_y = [_num(a["amarillas"]) / _num(a["partidos_carrera"])
               for a in arb.values() if _num(a["partidos_carrera"]) >= config.ARBITRO_MIN_CARRERA]
    tasas_f = [_num(a["faltas_pool"]) / _num(a["partidos_pool"])
               for a in arb.values() if _num(a["partidos_pool"]) >= config.ARBITRO_MIN_POOL]
    media_y = sum(tasas_y) / len(tasas_y) if tasas_y else 0.0
    media_f = sum(tasas_f) / len(tasas_f) if tasas_f else 0.0

    def _clip(v, cap):
        return max(cap[0], min(cap[1], v))

    out: dict[str, dict[str, float]] = {}
    with open(config.CALENDARIO_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            rid = str(r.get("referee_id", "")).split(".")[0].strip()
            a = arb.get(rid)
            if not a:
                continue
            fy = ff = 1.0
            if media_y > 0 and _num(a["partidos_carrera"]) >= config.ARBITRO_MIN_CARRERA:
                fy = _clip(_num(a["amarillas"]) / _num(a["partidos_carrera"]) / media_y,
                           config.ARBITRO_CAP_AMARILLAS)
            if media_f > 0 and _num(a["partidos_pool"]) >= config.ARBITRO_MIN_POOL:
                ff = _clip(_num(a["faltas_pool"]) / _num(a["partidos_pool"]) / media_f,
                           config.ARBITRO_CAP_FALTAS)
            out[str(r["partido_id"]).strip()] = {"yellow_cards": fy, "fouls": ff}
    return out


def cargar_reparto_1h() -> dict[str, float]:
    """Cuota de 1ª parte por métrica (data/reparto_mitades.csv); fallback prior."""
    shares = dict(config.REPARTO_1H_DEFAULT)
    if config.REPARTO_MITADES_CSV.exists():
        df = pd.read_csv(config.REPARTO_MITADES_CSV, sep=";", decimal=".")
        for _, r in df.iterrows():
            try:
                shares[str(r["metrica"])] = float(r["share_1h"])
            except (ValueError, TypeError, KeyError):
                pass
    return shares


def predict_all(
    dataset: Dataset | None = None,
    n_sim: int = config.N_SIM,
    seed: int = config.SEED,
    verbose: bool = False,
    scores_out: list | None = None,
    lambdas_out: dict | None = None,
) -> pd.DataFrame:
    """Devuelve el DataFrame en formato largo con todos los mercados Fase 1."""
    d = dataset or load_dataset()
    knn = compute_style_knn(d.stats, min_partidos=1 if d.legacy else config.KNN_MIN_PARTIDOS)
    fuerza = compute_strength(d.stats, d.equipos_mundial, usar_elo_mundo=not d.legacy)
    rng = np.random.default_rng(seed)

    cols_shrink = [c for c in config.COLS_RARAS_SHRINK if c in d.metricas_equipo]
    global_means = {
        c: float(d.stats[c].mean()) for c in cols_shrink if c in d.stats.columns
    }
    shares = cargar_reparto_1h()  # cuota 1ª parte por métrica (mercados por mitad)
    # En legacy reproducimos el R, que usaba W_FIFA=0.40 (antes de calibrar 3.1).
    w_fifa = 0.40 if d.legacy else config.W_FIFA
    farb = {} if d.legacy else factor_arbitro()  # efecto árbitro (Task 4.1/6.2)
    fbajas = {}  # ajuste por bajas (Task 4.2)
    if not d.legacy:
        from .bajas import factores_por_equipo
        fbajas = factores_por_equipo(d.equipos_mundial)

    filas: list[dict] = []
    for i, row in d.pred.reset_index(drop=True).iterrows():
        pid, fecha = row["partido_id"], str(row["fecha"])
        eA, eB = row["equipo_a"], row["equipo_b"]

        pool_A = construir_pool(eA, eB, d.stats, knn, fuerza, fecha_ref=fecha)
        pool_B = construir_pool(eB, eA, d.stats, knn, fuerza, fecha_ref=fecha)

        f_a = fuerza.get(eA, 0.0)
        f_b = fuerza.get(eB, 0.0)
        pool_A = ajustar_pool_por_calidad_rival(pool_A, f_b, fuerza)
        pool_B = ajustar_pool_por_calidad_rival(pool_B, f_a, fuerza)

        sims = simular_partido_bootstrap(
            pool_A, pool_B, d.metricas_equipo, cols_shrink, global_means,
            eA, eB, rng, n_sim=n_sim, w_fifa=w_fifa,
            factor_a=fbajas.get(eA, 1.0), factor_b=fbajas.get(eB, 1.0),
            sharp_k=1.0 if d.legacy else config.LAMBDA_SHARP_K,
        )
        # Efecto del árbitro designado: escala amarillas y faltas simuladas.
        fa = farb.get(str(pid))
        if sims is not None and fa:
            for met in ("yellow_cards", "fouls"):
                if met in sims.metricas:
                    j = sims.metricas.index(met)
                    sims.A[:, j] = sims.A[:, j] * fa[met]
                    sims.B[:, j] = sims.B[:, j] * fa[met]

        if sims is None:
            if verbose:
                print(f"  [WARN] {pid} sin sims (pool vacío)")
            continue
        filas.extend(
            calcular_mercados(sims, pid, fecha, eA, eB, rng=rng, n_sim=n_sim, shares=shares)
        )
        if lambdas_out is not None and np.isfinite(sims.lam_a_blend) and np.isfinite(sims.lam_b_blend):
            lambdas_out[pid] = (float(sims.lam_a_blend), float(sims.lam_b_blend))

        # Probabilidad de marcador exacto (matriz Dixon-Coles), opcional.
        if (
            scores_out is not None
            and np.isfinite(sims.lam_a_blend)
            and np.isfinite(sims.lam_b_blend)
        ):
            M = dixon_coles_matrix(sims.lam_a_blend, sims.lam_b_blend)
            total = float(M.sum())
            if total > 0:
                for ga in range(M.shape[0]):
                    for gb in range(M.shape[1]):
                        p = float(M[ga, gb]) / total
                        if p >= 0.001:
                            scores_out.append(
                                {"partido_id": pid, "a": ga, "b": gb,
                                 "prob": round(p, 4)}
                            )

        if verbose and (i + 1) % 12 == 0:
            print(f"  {i + 1}/{len(d.pred)} partidos")

    return pd.DataFrame(filas, columns=LARGO_COLS)


def build_resumen(largo: pd.DataFrame) -> pd.DataFrame:
    """Formato ancho con los mercados clave (como predicciones_resumen.csv)."""
    # El resumen es solo de mercados de partido completo (FT).
    ft = largo[largo.get("periodo", "FT").eq("FT")] if "periodo" in largo.columns else largo

    base = ft[ft["mercado"] == "1X2"].pivot_table(
        index=["partido_id", "fecha", "equipo_a", "equipo_b"],
        columns="evento_o_jugador", values="probabilidad", aggfunc="first",
    ).reset_index().rename(columns={"gana_A": "p_1", "empate": "p_X", "gana_B": "p_2"})

    def _ou(mercado, linea, over_name, under_name):
        sub = ft[(ft["mercado"] == mercado) & (ft["ambito"] == "TOTAL")
                 & (ft["linea_o_target"] == linea)]
        piv = sub.pivot_table(index="partido_id", columns="evento_o_jugador",
                              values="probabilidad", aggfunc="first").reset_index()
        return piv.rename(columns={"over": over_name, "under": under_name})

    btts = ft[ft["mercado"] == "btts"].pivot_table(
        index="partido_id", columns="evento_o_jugador", values="probabilidad",
        aggfunc="first").reset_index().rename(columns={"si": "btts_si", "no": "btts_no"})

    res = base.merge(btts, on="partido_id", how="left")
    res = res.merge(_ou("goles", 2.5, "goles_over_2_5", "goles_under_2_5"),
                    on="partido_id", how="left")
    res = res.merge(_ou("corner_kicks", 9.5, "corners_over_9_5", "corners_under_9_5"),
                    on="partido_id", how="left")

    cols = ["partido_id", "fecha", "equipo_a", "equipo_b", "p_1", "p_X", "p_2",
            "btts_si", "btts_no", "goles_over_2_5", "goles_under_2_5",
            "corners_over_9_5", "corners_under_9_5"]
    return res[[c for c in cols if c in res.columns]]


def write_outputs(largo: pd.DataFrame, prefix: str = "predicciones") -> tuple[str, str]:
    """Escribe largo y resumen (sufijo _py para no pisar el golden del R)."""
    config.DATA_DIR.mkdir(exist_ok=True)
    fout_largo = str(config.DATA_DIR / f"{prefix}_largo_py.csv")
    fout_res = str(config.DATA_DIR / f"{prefix}_resumen_py.csv")
    largo.to_csv(fout_largo, sep=";", decimal=",", index=False,
                 encoding="utf-8-sig")
    build_resumen(largo).to_csv(fout_res, sep=";", decimal=",", index=False,
                                encoding="utf-8-sig")
    return fout_largo, fout_res


def write_scores(scores: list[dict]) -> str:
    """Escribe las probabilidades de marcador exacto por partido."""
    config.DATA_DIR.mkdir(exist_ok=True)
    fout = str(config.DATA_DIR / "marcadores_py.csv")
    pd.DataFrame(scores, columns=["partido_id", "a", "b", "prob"]).to_csv(
        fout, sep=";", decimal=",", index=False, encoding="utf-8-sig"
    )
    return fout
