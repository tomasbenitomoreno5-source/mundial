"""Tests de la capa de identidad de equipos (ESPN/xgscore/FotMob -> canónico)."""

from predictor.sources import identity


def test_alias_de_fuentes_mapean_a_canonico():
    casos = {
        "Cape Verde": "Cabo Verde",
        "Congo DR": "DR Congo",
        "Ivory Coast": "Côte d'Ivoire",
        "United States": "USA",
        "Bosnia and Herzegovina": "Bosnia & Herzegovina",
        "Bosnia and Herz.": "Bosnia & Herzegovina",
        "Bosnia-Herzegovina": "Bosnia & Herzegovina",
        "Czech": "Czechia",
        "Saudi A.": "Saudi Arabia",
        "Turkey": "Türkiye",
        "Korea Republic": "South Korea",
    }
    for fuente, canon in casos.items():
        assert identity.canonical(fuente) == canon, fuente


def test_nombres_ya_canonicos_se_respetan():
    for n in ("France", "Spain", "Senegal", "Türkiye", "USA"):
        assert identity.canonical(n) == n


def test_placeholders_y_basura_devuelven_none():
    for n in ("Group A Winner", "Round of 32 1 Winner", "1A", "Winner QF 1", "", None):
        assert identity.canonical(n) is None
