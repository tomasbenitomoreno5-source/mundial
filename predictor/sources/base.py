"""Infra HTTP compartida por los clientes de fuente (ESPN, FotMob, xgscore...).

Sustituye al cliente único de SofaScore por una capa común y simple:
GET con User-Agent de navegador, reintentos con backoff, throttle educado entre
peticiones al mismo host y caché en disco opcional (inmutable para partidos ya
terminados: una vez bajados, sus stats no cambian → no se vuelven a pedir).

No usa dependencias externas (solo stdlib) para no añadir peso al venv.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.request
from pathlib import Path
from typing import Any

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / ".http_cache"
_THROTTLE_S = 0.6          # mínimo entre peticiones (educado, evita rate-limit)
_ultimo_get = 0.0

log = logging.getLogger("sources")


class FetchError(RuntimeError):
    """Fallo de red tras agotar reintentos (lo usan los clientes para exit 3/1)."""


def _throttle() -> None:
    global _ultimo_get
    espera = _THROTTLE_S - (time.monotonic() - _ultimo_get)
    if espera > 0:
        time.sleep(espera)
    _ultimo_get = time.monotonic()


def _cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    return CACHE_DIR / f"{h}.json"


def fetch(url: str, *, headers: dict | None = None, timeout: float = 30.0,
          retries: int = 3, backoff: float = 1.6) -> bytes:
    """GET crudo con reintentos. Lanza FetchError si agota los intentos."""
    h = {"User-Agent": UA, **(headers or {})}
    ultimo_err: Exception | None = None
    for intento in range(1, retries + 1):
        _throttle()
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status == 200:
                    return r.read()
                ultimo_err = FetchError(f"HTTP {r.status} en {url}")
        except Exception as e:  # noqa: BLE001
            ultimo_err = e
            log.warning("fetch %s intento %d/%d falló: %s", url, intento, retries, e)
        if intento < retries:  # no esperar tras el último intento
            time.sleep(backoff ** intento)
    raise FetchError(f"{url}: {ultimo_err}")


def get_json(url: str, *, headers: dict | None = None, cache: bool = False,
             cacheable=None, **kw: Any) -> Any:
    """GET que devuelve JSON. Si cache=True, lee/escribe en disco (inmutable).

    Usar cache=True SOLO para datos que no cambian (partidos terminados).
    `cacheable`: predicado sobre el JSON; si se pasa, la caché solo se usa y
    escribe cuando cacheable(obj) es True. Protege de cachear un partido EN
    VIVO (p.ej. el summary pedido a kickoff+1h dejaría las stats congeladas a
    mitad de partido para todos los consumidores posteriores).
    """
    if cache:
        cp = _cache_path(url)
        if cp.exists():
            obj = json.loads(cp.read_text(encoding="utf-8"))
            if cacheable is None or cacheable(obj):
                log.debug("cache hit %s", url)
                return obj
            log.info("cache invalidada (contenido no cacheable): %s", url)
            cp.unlink()
    data = fetch(url, headers=headers, **kw)
    obj = json.loads(data.decode("utf-8"))
    if cache and (cacheable is None or cacheable(obj)):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(url).write_text(json.dumps(obj), encoding="utf-8")
    return obj


def get_text(url: str, *, headers: dict | None = None, **kw: Any) -> str:
    """GET que devuelve texto (HTML)."""
    return fetch(url, headers=headers, **kw).decode("utf-8", "ignore")
