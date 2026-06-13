"""Tests de la agregación de árbitros (extraer_arbitros / extraer_designaciones)."""

import json

from extraer_arbitros import load_pool_agg
from extraer_designaciones import resolve_name


def _write_pool(tmp_path, recs):
    p = tmp_path / "arbitro_pool.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def test_pool_agg_suma_tarjetas_faltas_y_sesgo(tmp_path):
    recs = [
        {"partido_id": "1", "referee_id": 10, "yellow": 5, "yellow_home": 1,
         "yellow_away": 4, "red": 1, "fouls": 20.0, "goals_home": 2, "goals_away": 1},
        {"partido_id": "2", "referee_id": 10, "yellow": 3, "yellow_home": 2,
         "yellow_away": 1, "red": 0, "fouls": 30.0, "goals_home": 0, "goals_away": 0},
    ]
    by_ref, by_event = load_pool_agg(_write_pool(tmp_path, recs))
    a = by_ref[10]
    assert a["games"] == 2
    assert a["yellow"] == 8
    assert a["yellow_home"] == 3 and a["yellow_away"] == 5  # sesgo a visitante
    assert a["red"] == 1
    # faltas/partido medio = (20 + 30) / 2
    assert a["fouls"] / a["fouls_n"] == 25.0
    # goles/partido medio = (3 + 0) / 2
    assert a["goals"] / a["goals_n"] == 1.5
    # mapeo por evento (amarillas reales por partido)
    assert by_event["1"] == 5 and by_event["2"] == 3


def test_pool_agg_ignora_eventos_sin_arbitro(tmp_path):
    recs = [
        {"partido_id": "1", "referee_id": None, "yellow": 4},
        {"partido_id": "2", "referee_id": 7, "yellow": 2, "yellow_home": 1,
         "yellow_away": 1, "red": 0, "fouls": None, "goals_home": 1, "goals_away": 1},
    ]
    by_ref, by_event = load_pool_agg(_write_pool(tmp_path, recs))
    assert set(by_ref.keys()) == {7}        # el evento sin árbitro no cuenta
    assert by_ref[7]["fouls_n"] == 0         # fouls None no rompe la media


def test_pool_agg_vacio_si_no_existe(tmp_path):
    by_ref, by_event = load_pool_agg(tmp_path / "no_existe.jsonl")
    assert by_ref == {} and by_event == {}


def test_factor_arbitro_rango_y_neutro():
    """El factor árbitro existe, está capado y es neutro donde no hay designación."""
    from predictor import config
    from predictor.pipeline import factor_arbitro

    factores = factor_arbitro()
    if not factores:
        import pytest

        pytest.skip("sin arbitros.csv/calendario.csv")
    for f in factores.values():
        assert config.ARBITRO_CAP_AMARILLAS[0] <= f["yellow_cards"] <= config.ARBITRO_CAP_AMARILLAS[1]
        assert config.ARBITRO_CAP_FALTAS[0] <= f["fouls"] <= config.ARBITRO_CAP_FALTAS[1]


def test_resolve_name_por_apellido_y_acentos():
    ids = {
        "alejandro hernandez hernandez": {"sofa_id": "111", "nombre": "Alejandro Hernández Hernández"},
        "szymon marciniak": {"sofa_id": "222", "nombre": "Szymon Marciniak"},
    }
    # acento + nombre completo
    assert resolve_name("Szymon Marciniak", ids)["sofa_id"] == "222"
    # solo apellido / forma corta
    assert resolve_name("Hernández", ids)["sofa_id"] == "111"
    # desconocido
    assert resolve_name("John Doe", ids) is None
