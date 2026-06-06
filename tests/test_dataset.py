"""Tests de la capa de datos (bloques 1-2 del R portados)."""

import unicodedata

import pandas as pd


def test_pred_72_partidos_48_equipos(dataset):
    assert len(dataset.pred) == 72
    assert len(dataset.equipos_mundial) == 48


def test_encoding_equipos_especiales(dataset):
    nombres = set(dataset.stats["equipo_nombre"])
    for esperado in ("Curaçao", "Türkiye", "Côte d'Ivoire"):
        assert unicodedata.normalize("NFC", esperado) in nombres


def test_oponente_derivado(dataset):
    s = dataset.stats
    assert {"oponente", "goles_op"}.issubset(s.columns)
    # Ningún equipo es su propio oponente
    assert (s["equipo_nombre"] != s["oponente"]).all()


def test_sin_nas_en_metricas(dataset):
    """El bootstrap multivariado no tolera NaNs en la matriz simulada."""
    s = dataset.stats
    for m in dataset.metricas_equipo:
        assert not s[m].isna().any(), f"NaN restante en métrica {m}"


def test_metricas_numericas(dataset):
    s = dataset.stats
    for m in dataset.metricas_equipo:
        assert pd.api.types.is_numeric_dtype(s[m]), f"{m} no es numérica"


def test_metricas_subconjunto_canonico(dataset):
    from predictor import config

    assert len(dataset.metricas_equipo) > 0
    assert set(dataset.metricas_equipo).issubset(set(config.METRICAS_EQUIPO))


def test_eventos_raros_imputados_a_cero(dataset):
    s = dataset.stats
    for c in ("red_cards",):
        if c in s.columns:
            assert not s[c].isna().any()


def test_los_48_mundialistas_tienen_elo(dataset):
    from predictor import config

    sin_elo = [e for e in dataset.equipos_mundial if e not in config.ELO_2026]
    assert sin_elo == [], f"Equipos del Mundial sin ELO: {sin_elo}"
