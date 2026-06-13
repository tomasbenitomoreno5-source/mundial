"""Cliente único de acceso a SofaScore con fallback API → HTML.

SofaScore puso su API ``/api/v1`` detrás de un challenge anti-bot de Cloudflare
(403 a cualquier scraping: curl, Playwright, fetch desde la propia página). Pero
los datos siguen viajando embebidos en el HTML de cada página (Next.js, dentro
del ``<script id="__NEXT_DATA__">``).

Estrategia: intentar primero la API (instantánea; si SofaScore la desbloquea
algún día, sale gratis y sin tocar código) y caer al HTML solo cuando la API
falla. Una sola capa para todos los scrapers, en vez de la lógica duplicada y
hoy rota de ``extraer*.py``.

Uso típico::

    async with SofaScoreClient() as cli:
        ev = await cli.fetch_event(13233465)
        print(ev["startTimestamp"], ev["tournament"]["name"])
    print(cli.via)  # {"api": 0, "html": 1, "fail": 0}
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

API = "https://api.sofascore.com"
WEB = "https://www.sofascore.com"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def try_api(path: str, timeout: float = 10.0) -> dict | None:
    """GET a la API. Devuelve el JSON si 200; None si 403/error (→ usar HTML)."""
    req = urllib.request.Request(
        API + path, headers={"User-Agent": UA, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 200:
                return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    return None


def find_event(node: Any) -> dict | None:
    """Localiza el primer dict que parece un evento dentro de ``__NEXT_DATA__``."""
    if isinstance(node, dict):
        if "homeTeam" in node and "awayTeam" in node and "startTimestamp" in node:
            return node
        for v in node.values():
            r = find_event(v)
            if r:
                return r
    elif isinstance(node, list):
        for v in node:
            r = find_event(v)
            if r:
                return r
    return None


class SofaScoreClient:
    """Cliente async con fallback API→HTML. El navegador se abre perezosamente
    (solo si hace falta el HTML) y se reutiliza entre llamadas."""

    def __init__(self, rate_limit_s: float = 1.0, prefer_api: bool = True):
        self.rate_limit_s = rate_limit_s
        self.prefer_api = prefer_api
        self._pw = None
        self._browser = None
        self._page = None
        self.via = {"api": 0, "html": 0, "fail": 0}

    async def __aenter__(self) -> "SofaScoreClient":
        return self

    async def __aexit__(self, *exc) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._pw is not None:
            await self._pw.stop()

    async def _ensure_page(self):
        if self._page is None:
            from playwright.async_api import async_playwright

            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            ctx = await self._browser.new_context(user_agent=UA, locale="en-US")
            self._page = await ctx.new_page()
        return self._page

    async def next_data(self, web_path: str) -> dict | None:
        """Carga ``WEB + web_path`` y devuelve el JSON de ``__NEXT_DATA__``."""
        page = await self._ensure_page()
        try:
            await page.goto(WEB + web_path, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(int(self.rate_limit_s * 1000))
            nd = await page.evaluate(
                "()=>document.getElementById('__NEXT_DATA__')?.textContent"
            )
            return json.loads(nd) if nd else None
        except Exception:
            return None

    async def fetch_event(self, event_id: int | str) -> dict | None:
        """Datos de un evento (fecha, marcador, torneo). API→HTML."""
        if self.prefer_api:
            d = try_api(f"/api/v1/event/{event_id}")
            if d and "event" in d:
                self.via["api"] += 1
                return d["event"]
        nd = await self.next_data(f"/event/{event_id}")
        ev = find_event(nd) if nd else None
        self.via["html" if ev else "fail"] += 1
        return ev
