"""get_json(cacheable=...): la caché no debe persistir un partido EN VIVO.

Regresión del bug (jul-2026): designaciones cacheaba el summary de ESPN a
kickoff+1h (partido en juego) y stats/pool_arbitro leían esa foto del minuto
~55 para siempre (42 partidos con 0 amarillas, todas las métricas a ~60%).
"""

import json

from predictor.sources import base


def _fake_fetch(respuestas: list[dict]):
    llamadas = []

    def fetch(url, **kw):
        llamadas.append(url)
        return json.dumps(respuestas[min(len(llamadas), len(respuestas)) - 1]).encode()

    return fetch, llamadas


def test_no_cachea_contenido_no_cacheable(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "CACHE_DIR", tmp_path)
    fetch, llamadas = _fake_fetch([{"done": False}, {"done": True}, {"done": True}])
    monkeypatch.setattr(base, "fetch", fetch)
    pred = lambda o: o["done"]  # noqa: E731

    o1 = base.get_json("http://x/e?1", cache=True, cacheable=pred)
    assert o1["done"] is False
    assert not list(tmp_path.iterdir()), "un partido en vivo no debe cachearse"

    o2 = base.get_json("http://x/e?1", cache=True, cacheable=pred)
    assert o2["done"] is True
    assert len(list(tmp_path.iterdir())) == 1, "terminado -> sí se cachea"

    base.get_json("http://x/e?1", cache=True, cacheable=pred)
    assert len(llamadas) == 2, "la tercera debe salir de caché"


def test_invalida_cache_envenenada_preexistente(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "CACHE_DIR", tmp_path)
    url = "http://x/e?2"
    cp = base._cache_path(url)
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"done": False}), encoding="utf-8")

    fetch, llamadas = _fake_fetch([{"done": True}])
    monkeypatch.setattr(base, "fetch", fetch)
    o = base.get_json(url, cache=True, cacheable=lambda o: o["done"])
    assert o["done"] is True and len(llamadas) == 1
    assert json.loads(cp.read_text(encoding="utf-8"))["done"] is True


def test_sin_predicado_comportamiento_previo(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "CACHE_DIR", tmp_path)
    fetch, llamadas = _fake_fetch([{"v": 1}])
    monkeypatch.setattr(base, "fetch", fetch)
    assert base.get_json("http://x/e?3", cache=True)["v"] == 1
    assert base.get_json("http://x/e?3", cache=True)["v"] == 1
    assert len(llamadas) == 1
