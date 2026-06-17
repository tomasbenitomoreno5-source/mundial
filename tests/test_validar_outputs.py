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


def test_formato_notificacion_semaforo():
    # Todo OK -> semáforo verde + recuento; cada paso con ✅.
    ok = formatear_resumen([{"nombre": "a", "ok": True, "detalle": "5 nuevos"}], "13/06 20:00")
    assert ok.startswith("🟢 TODO OK · 1/1") and "✅ a — 5 nuevos" in ok
    # Fallo duro (compat bool ok=False) -> rojo + recuento + línea ❌.
    mal = formatear_resumen([{"nombre": "a", "ok": False, "detalle": "403"}], "13/06 20:00")
    assert mal.startswith("🔴 REVISAR · 0/1") and "❌ a — 403" in mal


def test_formato_notificacion_estados():
    # warn (sin fallos) -> naranja AVISOS.
    warn = formatear_resumen([{"nombre": "a", "estado": "warn", "detalle": "bloqueado"}], "13/06 20:00")
    assert warn.startswith("🟠 AVISOS · 0/1") and "⚠️ a — bloqueado" in warn
    # fail manda sobre warn -> rojo, recuento correcto, nombres en sus líneas.
    mixto = formatear_resumen(
        [{"nombre": "stats", "estado": "ok"},
         {"nombre": "xg", "estado": "warn", "detalle": "xgscore no disponible"},
         {"nombre": "arbitros", "estado": "fail", "detalle": "timeout"}], "13/06 20:00")
    assert mixto.startswith("🔴 REVISAR · 1/3")
    assert "⚠️ xg — xgscore no disponible" in mixto and "❌ arbitros — timeout" in mixto
