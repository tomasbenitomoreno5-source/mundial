"""Smoke test del backtest temporal (submuestra rápida)."""

from predictor.backtest import backtest, resumen


def test_backtest_smoke():
    df = backtest("2026-04-01", n_sim=400)
    assert len(df) >= 5
    assert {"p1", "px", "p2", "res", "ga", "gb"} <= set(df.columns)
    # 1X2 del modelo suma 1
    s = (df["p1"] + df["px"] + df["p2"])
    assert ((s - 1).abs() < 0.02).all()
    # resultado real coherente
    assert set(df["res"]) <= {"1", "X", "2"}
    print("\n" + resumen(df))
