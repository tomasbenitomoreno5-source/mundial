"""Tests de la capa de acceso a SofaScore (cliente con fallback API→HTML).

La parte de red real (Playwright) no se testea aquí; se verifica a mano contra
un evento real. Aquí cubrimos la lógica pura: extracción de __NEXT_DATA__ y la
decisión API→fallback con urllib mockeado.
"""

import asyncio
import json

from predictor import sofascore


def test_find_event_en_arbol_anidado():
    nd = {"props": {"pageProps": {"event": {
        "homeTeam": {"name": "Iceland"}, "awayTeam": {"name": "Azerbaijan"},
        "startTimestamp": 1763053200, "tournament": {"name": "WCQ"},
    }}}}
    ev = sofascore.find_event(nd)
    assert ev and ev["startTimestamp"] == 1763053200
    assert ev["homeTeam"]["name"] == "Iceland"


def test_find_event_devuelve_none_si_no_hay():
    assert sofascore.find_event({"props": {"pageProps": {"foo": 1}}}) is None


def test_try_api_devuelve_none_en_403(monkeypatch):
    def fake_urlopen(*a, **k):
        raise urllib_error()
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert sofascore.try_api("/api/v1/event/1") is None


def test_try_api_parsea_json_en_200(monkeypatch):
    payload = {"event": {"startTimestamp": 123}}

    class FakeResp:
        status = 200
        def read(self): return json.dumps(payload).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResp())
    assert sofascore.try_api("/api/v1/event/1") == payload


def urllib_error():
    import urllib.error
    return urllib.error.HTTPError("u", 403, "Forbidden", {}, None)


def test_fetch_event_usa_api_si_disponible(monkeypatch):
    monkeypatch.setattr(sofascore, "try_api",
                        lambda path, timeout=10.0: {"event": {"startTimestamp": 9}})
    cli = sofascore.SofaScoreClient()
    ev = asyncio.run(cli.fetch_event(1))
    assert ev["startTimestamp"] == 9
    assert cli.via == {"api": 1, "html": 0, "fail": 0}


def test_fetch_event_cae_a_html_si_api_falla(monkeypatch):
    monkeypatch.setattr(sofascore, "try_api", lambda path, timeout=10.0: None)

    async def fake_next_data(self, web_path):
        return {"props": {"event": {
            "homeTeam": {"name": "A"}, "awayTeam": {"name": "B"},
            "startTimestamp": 42}}}

    monkeypatch.setattr(sofascore.SofaScoreClient, "next_data", fake_next_data)
    cli = sofascore.SofaScoreClient()
    ev = asyncio.run(cli.fetch_event(1))
    assert ev["startTimestamp"] == 42
    assert cli.via == {"api": 0, "html": 1, "fail": 0}
