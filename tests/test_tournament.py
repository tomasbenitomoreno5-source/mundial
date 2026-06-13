"""Tests de la simulación del torneo con cuadro real (3.5)."""

from predictor.tournament import simulate


def test_torneo_coherente():
    tally = simulate(n_sim=2000)
    n = 2000
    assert len(tally) == 48
    # Suma de campeón = 1 (un solo campeón por simulación)
    p_camp = sum(c["campeon"] for c in tally.values()) / n
    assert abs(p_camp - 1.0) < 1e-9
    # 32 clasificados de grupo por simulación
    p_grupo = sum(c["grupo"] for c in tally.values()) / n
    assert abs(p_grupo - 32.0) < 1e-9


def test_rondas_monotonas():
    tally = simulate(n_sim=2000)
    rondas = ["grupo", "r16", "qf", "sf", "final", "campeon"]
    for t, c in tally.items():
        vals = [c[r] for r in rondas]
        assert all(b <= a + 1e-9 for a, b in zip(vals, vals[1:])), t


def test_favorito_pasa_de_grupo():
    tally = simulate(n_sim=2000)
    # España (grupo H, favorita) debe pasar de grupo casi siempre
    assert tally["Spain"]["grupo"] / 2000 > 0.85
