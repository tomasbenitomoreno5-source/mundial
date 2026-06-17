"""Fixtures compartidos: el dataset se carga una sola vez por sesión.

Los tests de regresión corren contra un `stats_final` CONGELADO (golden_data/),
NO contra el pool vivo. Motivo: el pool crece con cada partido del Mundial; si los
golden leyeran el pool vivo se romperían en cada jornada y no distinguirían un dato
nuevo (esperado) de un bug. La producción (predictor.cli) sigue usando el pool vivo.
"""

from pathlib import Path

import pytest

from predictor.dataset import Dataset, load_dataset

STATS_GOLDEN = Path(__file__).resolve().parent / "golden_data" / "stats_final.csv"


@pytest.fixture(scope="session")
def dataset() -> Dataset:
    return load_dataset(stats_path=STATS_GOLDEN)


@pytest.fixture(scope="session")
def dataset_legacy() -> Dataset:
    """Dataset SIN saneamiento (clubes, fechas, filas imputadas) — reproduce el
    estado con el que se generó el golden del R. Solo para tests de fidelidad
    del port frente al R."""
    return load_dataset(stats_path=STATS_GOLDEN, legacy=True)
