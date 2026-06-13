"""Fixtures compartidos: el dataset se carga una sola vez por sesión."""

import pytest

from predictor.dataset import Dataset, load_dataset


@pytest.fixture(scope="session")
def dataset() -> Dataset:
    return load_dataset()


@pytest.fixture(scope="session")
def dataset_legacy() -> Dataset:
    """Dataset SIN saneamiento (clubes, fechas, filas imputadas) — reproduce el
    estado con el que se generó el golden del R. Solo para tests de fidelidad
    del port frente al R."""
    return load_dataset(legacy=True)
