"""congelar_jugados: conserva la predicción pre-partido de los jugados SIN perder
partidos. Regresión del bug que tiró 18 partidos finalizados de la web (jun-2026):
un finalizado ausente del CSV viejo no lo aportaba ni `viejo` ni `nuevo` -> se
caía del output y, al seguir finalizado, no volvía nunca (pérdida acumulativa)."""

import pandas as pd

from predictor.pipeline import congelar_jugados


def _escribe_viejo(tmp_path, df: pd.DataFrame):
    p = tmp_path / "predicciones_largo_py.csv"
    df.to_csv(p, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    return p


def _nuevo(pids, valor):
    """Predicción fresca: una fila 1X2 por partido (el motor cubre los 72)."""
    return pd.DataFrame({"partido_id": pids, "mercado": "1X2",
                         "evento_o_jugador": "gana_A", "probabilidad": valor})


def test_no_pierde_finalizado_ausente_del_viejo(tmp_path):
    # nuevo cubre A, B, C; viejo solo tiene A. B está finalizado pero NO en viejo.
    nuevo = _nuevo(["A", "B", "C"], 0.5)
    viejo = _escribe_viejo(tmp_path, _nuevo(["A"], 0.9))
    out = congelar_jugados(nuevo, viejo, finished_pids={"B"})
    assert set(out["partido_id"]) == {"A", "B", "C"}, "no debe perder ningún partido"


def test_congela_finalizado_presente_en_viejo(tmp_path):
    # A finalizado y presente en viejo -> se conserva el valor VIEJO (pre-partido).
    nuevo = _nuevo(["A", "B"], 0.5)
    viejo = _escribe_viejo(tmp_path, _nuevo(["A", "B"], 0.9))
    out = congelar_jugados(nuevo, viejo, finished_pids={"A"})
    assert out.loc[out["partido_id"] == "A", "probabilidad"].iloc[0] == 0.9  # congelado
    assert out.loc[out["partido_id"] == "B", "probabilidad"].iloc[0] == 0.5  # recalculado


def test_nunca_reduce_la_cobertura(tmp_path):
    # Sea cual sea el viejo, el resultado cubre TODOS los partidos del nuevo.
    nuevo = _nuevo([f"P{i}" for i in range(72)], 0.5)
    viejo = _escribe_viejo(tmp_path, _nuevo(["P0", "P1"], 0.9))
    out = congelar_jugados(nuevo, viejo, finished_pids={"P0", "P5", "P9"})
    assert out["partido_id"].nunique() == 72


def test_viejo_con_decimales_de_punto_vuelve_a_float(tmp_path):
    # Regresión (server, jul-2026): un CSV previo con probabilidades "0.9" (punto)
    # se leía como texto, el concat contaminaba la columna y el output se
    # reescribía con punto para siempre (validar_outputs dejaba de parsear).
    nuevo = _nuevo(["A", "B"], 0.5)
    p = tmp_path / "predicciones_largo_py.csv"
    p.write_text(
        "partido_id;mercado;evento_o_jugador;probabilidad\n"
        "A;1X2;gana_A;0.9\n",
        encoding="utf-8-sig",
    )
    out = congelar_jugados(nuevo, p, finished_pids={"A"})
    assert out["probabilidad"].dtype.kind == "f"
    assert out.loc[out["partido_id"] == "A", "probabilidad"].iloc[0] == 0.9
