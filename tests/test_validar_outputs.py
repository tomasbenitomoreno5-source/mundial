"""Tests del validador de coherencia (0.6) y del formateo de notificaciones (5.2)."""

import pandas as pd

from notificar import formatear_resumen
from predictor.validar_outputs import validar_largo, validar_torneo


def _fila(mercado, ambito, evento, linea, prob, periodo="FT"):
    return {"partido_id": "X_Y", "mercado": mercado, "ambito": ambito,
            "evento_o_jugador": evento, "linea_o_target": linea,
            "probabilidad": prob, "periodo": periodo}


def test_detecta_sot_mayor_que_ts():
    filas = [
        _fila("shots_on_target", "A", "over", 4.5, 0.80),
        _fila("shots_on_target", "A", "under", 4.5, 0.20),
        _fila("total_shots", "A", "over", 4.5, 0.50),
        _fila("total_shots", "A", "under", 4.5, 0.50),
    ]
    assert any("shots_on_target" in e for e in validar_largo(pd.DataFrame(filas)))


def test_coherente_no_da_falsos():
    filas = [
        _fila("total_shots", "A", "over", 4.5, 0.80),
        _fila("total_shots", "A", "under", 4.5, 0.20),
        _fila("shots_on_target", "A", "over", 4.5, 0.30),
        _fila("shots_on_target", "A", "under", 4.5, 0.70),
    ]
    assert validar_largo(pd.DataFrame(filas)) == []


def test_detecta_1x2_no_suma_uno():
    filas = [
        _fila("1X2", "-", "gana_A", "-", 0.5),
        _fila("1X2", "-", "empate", "-", 0.3),
        _fila("1X2", "-", "gana_B", "-", 0.3),  # suma 1.1
    ]
    assert any("1X2" in e for e in validar_largo(pd.DataFrame(filas)))


def test_torneo_rondas_no_monotonas():
    df = pd.DataFrame([{"equipo": "X", "p_grupo": 0.5, "p_r16": 0.6,
                        "p_qf": 0.1, "p_sf": 0.05, "p_final": 0.02, "p_campeon": 0.01}])
    assert validar_torneo(df)


def test_formato_notificacion_marca_fallo():
    ok = formatear_resumen([{"nombre": "a", "ok": True, "detalle": "5 nuevos"}], "13/06 20:00")
    assert ok.startswith("✅")
    mal = formatear_resumen([{"nombre": "a", "ok": False, "detalle": "403"}], "13/06 20:00")
    assert mal.startswith("⚠️") and "✗ a" in mal
