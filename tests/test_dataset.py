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


def test_elo_fuente_unica():
    """config.ELO_2026 se carga de data/elo_2026.csv (sin dict hardcoded)."""
    import csv

    from predictor import config

    with open(config.ELO_2026_CSV, encoding="utf-8-sig") as f:
        csv_elo = {r["equipo"].strip(): int(r["elo"])
                   for r in csv.DictReader(f, delimiter=";")}
    assert config.ELO_2026 == csv_elo
    assert len(config.ELO_2026) == 48


def test_sin_clubes_en_stats(dataset):
    """Clubes y no-selecciones colados como rivales de amistosos quedan fuera."""
    equipos = set(dataset.stats["equipo_nombre"])
    for club in ("ASWH", "Udinese", "Lecce", "VV Goes", "Basque Country"):
        assert club not in equipos, f"{club} sigue en el dataset"


def test_partidos_de_clubes_eliminados_enteros(dataset):
    """Se elimina el partido completo, no solo la fila del club: ningún
    mundialista conserva una fila cuyo oponente sea un equipo excluido."""
    import pandas as pd

    excluidos = set(
        pd.read_csv(config_excluidos(), sep=";", encoding="utf-8-sig")["equipo"]
    )
    op = set(dataset.stats["oponente"])
    assert not (op & excluidos), f"Oponentes excluidos presentes: {op & excluidos}"


def config_excluidos():
    from predictor import config

    return config.EQUIPOS_EXCLUIDOS_CSV


def test_stats_tiene_fecha(dataset):
    """Backfill de fecha mergeado (requiere data/partido_fechas.csv completo)."""
    from predictor import config

    if not config.PARTIDO_FECHAS_CSV.exists():
        import pytest

        pytest.skip("partido_fechas.csv aún no generado (scrape pendiente)")
    assert "fecha" in dataset.stats.columns
    cobertura = dataset.stats["fecha"].notna().mean()
    assert cobertura > 0.95, f"solo {cobertura:.0%} de filas con fecha"


def test_stats_tiene_torneo(dataset):
    from predictor import config

    if not config.PARTIDO_FECHAS_CSV.exists():
        import pytest

        pytest.skip("partido_fechas.csv aún no generado (scrape pendiente)")
    assert "torneo" in dataset.stats.columns


def test_flag_stats_completas(dataset):
    """Las filas sin stats reales quedan marcadas (para excluirlas del pool)."""
    assert "stats_completas" in dataset.stats.columns
    incompletas = (~dataset.stats["stats_completas"]).sum()
    assert 100 < incompletas < 350, f"filas imputadas marcadas: {incompletas}"


def test_sin_partidos_con_fecha_futura(dataset):
    """Fixtures futuros (marcadores espurios) quedan fuera del entrenamiento."""
    import datetime as dt

    from predictor import config

    if not config.PARTIDO_FECHAS_CSV.exists():
        import pytest

        pytest.skip("partido_fechas.csv aún no generado")
    hoy = dt.date.today().isoformat()
    futuros = dataset.stats[dataset.stats["fecha"].notna() & (dataset.stats["fecha"] > hoy)]
    assert len(futuros) == 0, f"{len(futuros)} filas con fecha futura: {set(futuros['fecha'])}"
