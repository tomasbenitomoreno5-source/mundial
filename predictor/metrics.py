"""Métricas de calidad predictiva para el backtest.

Brier multiclase y log-loss sobre el mercado 1X2. Ambas son *proper scoring
rules*: premian probabilidades bien calibradas, no solo el acierto del signo.
Menor = mejor en las dos.
"""

from __future__ import annotations

import numpy as np

_IDX = {"1": 0, "X": 1, "2": 2}


def _onehot(resultados: list[str]) -> np.ndarray:
    y = np.zeros((len(resultados), 3))
    for i, r in enumerate(resultados):
        y[i, _IDX[r]] = 1.0
    return y


def brier_1x2(probs, resultados) -> float:
    """Brier multiclase medio: mean(Σ_k (p_k - y_k)²). 0 = perfecto."""
    p = np.asarray(probs, dtype=float)
    y = _onehot(list(resultados))
    return float(((p - y) ** 2).sum(axis=1).mean())


def logloss_1x2(probs, resultados, eps: float = 1e-12) -> float:
    """Log-loss medio: -mean(Σ_k y_k·log p_k). Clip para evitar log(0)=inf."""
    p = np.clip(np.asarray(probs, dtype=float), eps, 1.0)
    y = _onehot(list(resultados))
    return float(-(y * np.log(p)).sum(axis=1).mean())
