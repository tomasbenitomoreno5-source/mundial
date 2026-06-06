"""Fixtures compartidos: el dataset se carga una sola vez por sesión."""

import pytest

from predictor.dataset import Dataset, load_dataset


@pytest.fixture(scope="session")
def dataset() -> Dataset:
    return load_dataset()
