"""Tests del update de ELO en vivo (parte pura, sin IO)."""

from actualizar_torneo import elo_update


def test_elo_update_victoria_esperada_favorito():
    # España (2165) gana 2-0 a Curaçao (1436): resultado esperado, cambio pequeño.
    da, db = elo_update(2165, 1436, 2, 0)
    assert 0 < da < 10
    assert db == -da


def test_elo_update_sorpresa_da_cambio_grande():
    # Curaçao (1436) gana 1-0 a España (2165): sorpresa enorme, cambio grande.
    da, db = elo_update(1436, 2165, 1, 0)
    assert da > 40
    assert db == -da


def test_elo_update_empate_favorito_pierde_puntos():
    # El favorito empata: pierde ELO (rindió por debajo de lo esperado).
    da, _ = elo_update(2000, 1600, 1, 1)
    assert da < 0


def test_margen_amplia_el_cambio():
    da1, _ = elo_update(1800, 1800, 1, 0)   # 1-0
    da3, _ = elo_update(1800, 1800, 4, 0)   # 4-0 (mayor margen)
    assert da3 > da1
