# Mejora general de modelo y datos — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sanear el dataset, montar un harness de backtest que sirva de puerta de calidad, y aplicar las mejoras de datos y modelo identificadas en la revisión del 2026-06-12 (filtro de clubes, fechas + recencia, ELO universal, calibración de constantes, torneo con cuadro real, árbitros→tarjetas, ajuste por bajas).

**Architecture:** El motor (`predictor/`) sigue leyendo CSVs de `data/`; los datos nuevos entran como **tablas join separadas** (`partido_fechas.csv`, `elo_mundo.csv`, …) sin reescribir `stats_final.csv`, lo que facilita la migración progresiva a SQL/Prisma. Todo cambio de modelo a partir de la Fase 2 se acepta **solo si no empeora el log-loss del backtest** (Fase 1).

**Tech Stack:** Python (pandas, numpy, scikit-learn, statsmodels, scipy), Playwright para scraping, pytest.

**⚠ Convenciones de este repo (override del flujo estándar):**
- **NO hacer `git commit` en ningún paso** — los cambios se dejan en el working tree y el usuario commitea él mismo.
- Los pasos de "Commit" del formato estándar se sustituyen por "verificar y dejar en working tree".
- Cuando se añadan columnas/tablas nuevas a `data/`, anotar en `data/README.md` (y tenerlas en cuenta para el seed de Prisma, dirección general del proyecto: migrar a SQL).

**Orden recomendado dado el calendario** (el Mundial empieza el 17-jun): Fase 0 entera → Task 4.3 (loop en vivo, lo necesitas desde la jornada 1) → Fase 1 → Fases 2-3 durante la fase de grupos → resto de Fase 4.

---

## Fase 0 — Saneamiento de datos

### Task 0.0: Capa de acceso a SofaScore con fallback API→HTML  ✅ HECHO (2026-06-13)

**Contexto (bloqueante descubierto el 2026-06-13):** SofaScore puso su API `/api/v1` detrás de un challenge anti-bot de **Cloudflare**. Verificado: 403 con `curl`, con Playwright headless (UA realista), y con `fetch` desde la propia página ya cargada; incluso el frontend de SofaScore recibe 403 en navegador automatizado (se ven llamadas a `challenges.cloudflare.com`). **Todos los scrapers del repo (`extraer*.py`, `actualizar_fixtures.py`, `resultados.py`) llaman a esa API → están rotos.** Pero los datos siguen embebidos en el HTML de cada página (Next.js, `<script id="__NEXT_DATA__">`): verificado extrayendo el evento completo (equipos, marcador, `startTimestamp`, torneo) de `/event/{id}`.

**Decisión (idea del usuario):** un cliente único que **intenta primero la API** (instantánea; si SofaScore la desbloquea algún día, sale gratis sin tocar código) y **cae al HTML** solo si la API falla. Una sola capa para todos los scrapers, en vez de lógica duplicada y rota.

**Files:**
- Create: `predictor/sofascore.py` — `try_api()`, `find_event()`, `SofaScoreClient` (async, navegador perezoso y reutilizado, contador `via={api,html,fail}`).
- Test: `tests/test_sofascore.py` — 6 tests puros (extracción de `__NEXT_DATA__`, fallback API→HTML con `urllib`/`next_data` mockeados; sin red, sin `pytest-asyncio` — usan `asyncio.run`).

**Resultado de la ejecución:** 6/6 tests verdes. Integración real: `Azerbaijan 0-2 Iceland` y `Iceland 2-2 France` extraídos vía HTML (`via={api:0, html:2, fail:0}`).

**Avisos para las tasks que scrapean:**
- El fallback es **por recurso**: `fetch_event` (fecha/marcador/torneo) está verificado. Para stats de partido, fixtures y lineups habrá que añadir métodos al cliente y **verificar que el dato existe en el HTML** cuando lleguemos a ellos (puede requerir parsear otra página, p. ej. `/event/{id}#tab:statistics` o la del torneo).
- Coste: el HTML tarda ~5-10 s/evento (vs API instantánea). Re-estimar tiempos de scrape al alza.
- Migrar `extraer*.py` a este cliente queda pendiente como sub-tareas dentro de cada Task que los use (2.x, 4.x, 5.x).

---

### Task 0.1: Filtrar clubes y no-selecciones del dataset  ✅ HECHO (2026-06-13)

**Contexto:** `stats_final.csv` contiene una liga amateur holandesa (ASWH y rivales), Udinese, Lecce y Basque Country.

**Impacto real medido (no exagerar):** son 58 filas (2.3% del dataset). Verificado empíricamente:
- **NO** aparecen como vecinos KNN de ningún mundialista (`debug_knn.csv` limpio) → no entran al pool de bootstrap de nadie.
- **NO** los referencia la web (`web/` sin menciones).
- Solo tocan las **medias globales** (prior de shrinkage + imputación) y el universo de estandarización del z-score (208→188 equipos). Efecto en medias globales: goles −1.1%, tarjetas +2.4%, resto ≈0%.
- Borrar el partido entero cuesta **2 filas de mundialistas** (Qatar vs Udinese, Uruguay vs Basque Country), partidos sin valor informativo.

Conclusión: es **higiene + blindaje** ante cambios futuros del KNN (Tasks 2.2/3.3), no un game-changer. No mueve las predicciones de forma visible. Se hace porque el coste es nulo.

**Resultado de la ejecución:** 208→188 equipos, 2348→2290 filas (−58), 48/48 mundialistas presentes. 10/10 tests de `test_dataset.py` en verde.

**Files:**
- Create: `data/equipos_excluidos.csv`
- Modify: `predictor/config.py` (ruta nueva)
- Modify: `predictor/dataset.py` (filtro + flag `legacy`)
- Test: `tests/test_dataset.py`

- [ ] **Step 1: Crear la lista de exclusión**

`data/equipos_excluidos.csv` (sep `;`, UTF-8):

```csv
equipo;motivo
ASWH;club amateur NL
Blauw Geel '38;club amateur NL
FC Lisse;club amateur NL
FC Rijnvogels;club amateur NL
RBC Roosendaal;club amateur NL
RKSV UDI '19;club amateur NL
SteDoCo;club amateur NL
SV Meerssen;club amateur NL
SV TOGB;club amateur NL
SVV Scheveningen;club amateur NL
VV Gemert;club amateur NL
VV Goes;club amateur NL
VV Kloetinge;club amateur NL
VV Noordwijk;club amateur NL
VV UNA;club amateur NL
VV Zwaluwen;club amateur NL
VVSB Noordwijkerhout;club amateur NL
Udinese;club Serie A (amistoso vs UAE)
Lecce;club Serie A (amistoso vs UAE)
Basque Country;seleccion no-FIFA
```

- [ ] **Step 2: Test que falla**

Añadir a `tests/test_dataset.py`:

```python
def test_sin_clubes_en_stats(dataset):
    equipos = set(dataset.stats["equipo_nombre"])
    for club in ("ASWH", "Udinese", "Lecce", "VV Goes", "Basque Country"):
        assert club not in equipos, f"{club} sigue en el dataset"

def test_partidos_de_clubes_eliminados_enteros(dataset):
    # El partido entero se elimina (también la fila del rival "bueno"):
    # Udinese vs Qatar era el evento 14265554.
    assert 14265554 not in set(dataset.stats["partido_id"].astype(int))
```

Run: `.venv/bin/python -m pytest tests/test_dataset.py -k sin_clubes -v` → FAIL.

- [ ] **Step 3: Implementar el filtro**

En `predictor/config.py` añadir junto a las otras rutas:

```python
EQUIPOS_EXCLUIDOS_CSV = DATA_DIR / "equipos_excluidos.csv"
```

En `predictor/dataset.py`, añadir helper y enganchar en `load_dataset` (después de la limpieza de nombres, antes de las verificaciones de encoding):

```python
def _load_excluidos() -> set[str]:
    if not config.EQUIPOS_EXCLUIDOS_CSV.exists():
        return set()
    df = pd.read_csv(config.EQUIPOS_EXCLUIDOS_CSV, sep=";", encoding="utf-8-sig")
    return set(df["equipo"].astype(str).str.strip())
```

En `load_dataset`, cambiar la firma a:

```python
def load_dataset(
    stats_path: Path | None = None,
    tel_path: Path | None = None,
    pred_path: Path | None = None,
    legacy: bool = False,   # True = comportamiento pre-saneamiento (golden del R)
) -> Dataset:
```

y tras limpiar `stats["equipo_nombre"]`:

```python
    if not legacy:
        excluidos = _load_excluidos()
        if excluidos:
            malos = stats.loc[
                stats["equipo_nombre"].isin(excluidos), "partido_id"
            ].unique()
            stats = stats[~stats["partido_id"].isin(malos)].reset_index(drop=True)
```

- [ ] **Step 4: Verificar**

Run: `.venv/bin/python -m pytest tests/test_dataset.py -v` → los dos tests nuevos PASS. Los tests de regresión contra el golden del R fallarán a partir de aquí — se arreglan en Task 0.5 (no antes; ejecutar solo `tests/test_dataset.py` mientras tanto).

---

### Task 0.2: Backfill de fecha y torneo por partido  ✅ HECHO (2026-06-13)

**Contexto:** `stats_final.csv` no tiene fecha → la mejora #8 (recencia) está bloqueada. `partido_id` ES el event id de SofaScore, así que se puede backfillear sin re-scrapear los partidos.

**Resultado de la ejecución:** `extraer_fechas.py` reescrito sobre `SofaScoreClient` (fallback API→HTML, resumable). 1.174/1.174 eventos, **0 fallos**, todos vía HTML (API bloqueada por Cloudflare). `data/partido_fechas.csv` generado; merge en `load_dataset` con **100% de cobertura** de fecha. Tests `test_stats_tiene_fecha`/`test_stats_tiene_torneo` en verde. El `torneo` además distingue amistosos (448) de competitivos → insumo directo para Task 2.3.

**Atajo descartado:** se midió la correlación `partido_id ↔ fecha` con muestra de 50 (Pearson 0.70, Spearman 0.67); por debajo del ≥0.90 que el R exigía, así que `partido_id` NO sirve de proxy temporal y el scrape real era necesario.

**⚠ Hallazgo (destapado por el backfill):** 34 de 1.145 partidos tienen **fecha futura** (Mundial 2026 jun, Nations League sept 2026) con marcadores espurios — fixtures que SofaScore lista y el scraper rellenó con un resultado inventado. Contaminaban pool/fuerza/KNN sin detección posible (sin fecha eran invisibles), y con la recencia pesarían MÁS que lo real. → ver Task 0.2b.

---

### Task 0.2b: Excluir partidos con fecha futura (marcadores espurios)  ✅ HECHO (2026-06-13)

**Contexto:** ver hallazgo de Task 0.2. 34 partidos (68 filas) con fecha > hoy y resultado inventado.

**Resultado de la ejecución:** `_excluir_fecha_futura()` en `dataset.py` (filtra `fecha > hoy` tras el merge, conserva NaN, configurable por corte; salta en `legacy`). Test `test_sin_partidos_con_fecha_futura` en verde. **Impacto medido al regenerar:** Δ medio 1X2 = 0.02 sobre los 72, con casos de hasta 0.17 (CUR_CIV: Côte d'Ivoire 39%→50%; Czechia, con n=9, muy afectada por fixtures Nations League sept-2026 espurios). Predicciones y torneo regenerados (favoritas: Spain 29%, Argentina 18%, France 12%). Confirmado como causa parcial de los "resultados raros" reportados.

**Files:**
- Create: `extraer_fechas.py`
- Create (output): `data/partido_fechas.csv` + `data/partido_fechas.jsonl` (resumable)
- Modify: `predictor/config.py`, `predictor/dataset.py`
- Test: `tests/test_dataset.py`
- Modify: `data/README.md` (documentar la tabla nueva)

- [ ] **Step 1: Script de backfill**

`extraer_fechas.py` (mismo patrón Playwright + JSONL resumable que el resto de extractores):

```python
"""Backfill de fecha/torneo por partido_id (event id de SofaScore).

Lee los partido_id únicos de stats_final.csv, consulta /api/v1/event/{id}
y escribe data/partido_fechas.csv. Resumable vía .jsonl.
"""
import asyncio
import json
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright

DATA = Path(__file__).parent / "data"
OUT_JSONL = DATA / "partido_fechas.jsonl"
OUT_CSV = DATA / "partido_fechas.csv"
API = "https://www.sofascore.com/api/v1/event/{}"


async def main() -> None:
    ids = (
        pd.read_csv(DATA / "stats_final.csv", sep=";", encoding="utf-8-sig",
                    usecols=["partido_id"])["partido_id"].astype(int).unique()
    )
    hechos: set[int] = set()
    if OUT_JSONL.exists():
        with OUT_JSONL.open(encoding="utf-8") as f:
            hechos = {json.loads(l)["partido_id"] for l in f if l.strip()}
    pendientes = [int(i) for i in ids if int(i) not in hechos]
    print(f"{len(pendientes)} eventos pendientes de {len(ids)}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        with OUT_JSONL.open("a", encoding="utf-8") as f:
            for n, eid in enumerate(pendientes, 1):
                try:
                    resp = await page.goto(API.format(eid))
                    ev = (await resp.json())["event"]
                except Exception as e:
                    print(f"  [WARN] {eid}: {e}")
                    continue
                row = {
                    "partido_id": eid,
                    "timestamp": ev["startTimestamp"],
                    "torneo": ev["tournament"]["name"],
                    "categoria": ev["tournament"]["category"]["name"],
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                if n % 50 == 0:
                    print(f"  {n}/{len(pendientes)}")
                await asyncio.sleep(1.0)  # rate limit suave
        await browser.close()

    rows = [json.loads(l) for l in OUT_JSONL.open(encoding="utf-8") if l.strip()]
    df = pd.DataFrame(rows).drop_duplicates("partido_id")
    df["fecha"] = pd.to_datetime(df["timestamp"], unit="s").dt.date.astype(str)
    df[["partido_id", "fecha", "timestamp", "torneo", "categoria"]].to_csv(
        OUT_CSV, sep=";", index=False, encoding="utf-8-sig"
    )
    print(f"OK: {len(df)} filas -> {OUT_CSV.name}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Ejecutarlo**

Run: `.venv/bin/python extraer_fechas.py` (~20-25 min para ~1.174 eventos a 1 req/s).
Expected: `OK: ~1174 filas -> partido_fechas.csv`. Si se corta, re-ejecutar (resumable).

- [ ] **Step 3: Test que falla**

```python
def test_stats_tiene_fecha(dataset):
    assert "fecha" in dataset.stats.columns
    cobertura = dataset.stats["fecha"].notna().mean()
    assert cobertura > 0.95, f"solo {cobertura:.0%} de filas con fecha"

def test_stats_tiene_torneo(dataset):
    assert "torneo" in dataset.stats.columns
```

Run: `pytest tests/test_dataset.py -k fecha -v` → FAIL.

- [ ] **Step 4: Merge en dataset.py**

`predictor/config.py`:

```python
PARTIDO_FECHAS_CSV = DATA_DIR / "partido_fechas.csv"
```

`predictor/dataset.py`, en `load_dataset` justo después del filtro de excluidos (saltarlo si `legacy`):

```python
    if not legacy and config.PARTIDO_FECHAS_CSV.exists():
        fechas = pd.read_csv(
            config.PARTIDO_FECHAS_CSV, sep=";", encoding="utf-8-sig",
            dtype={"partido_id": str},
        )[["partido_id", "fecha", "torneo", "categoria"]]
        stats = stats.merge(fechas, on="partido_id", how="left")
```

(Nota: `stats` se lee con `dtype=str`, así que `partido_id` es str en ambos lados.)

- [ ] **Step 5: Verificar y documentar**

Run: `pytest tests/test_dataset.py -v` → PASS. Añadir `partido_fechas.csv` a la sección "Inputs del modelo" de `data/README.md`.

---

### Task 0.3: Excluir del pool las filas sin estadísticas reales  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** flag `stats_completas` en `_clean_stats` (calculado antes de imputar, sobre posesión/tiros/pases/córners); `construir_pool` filtra las imputadas. 218 filas marcadas (9.5%; Cabo Verde 9, DR Congo 8, Egypt 6…). Ningún equipo se queda sin pool (Cabo Verde 14 filas reales, DR Congo 17, Egypt 38). Tests `test_flag_stats_completas` + `test_pool_sin_filas_imputadas` en verde. **Impacto:** Δ medio 1X2 = 0.005, localizado en los afectados (DR Congo vs Portugal 33%→19%; Cabo Verde vs España 9%→15%) — las medianas clonadas inflaban perfiles. Predicciones y torneo regenerados.

---

#### Detalle original de la tarea

**Contexto:** 266/2.348 filas no tienen ni posesión ni tiros ni pases; hoy se imputan con medianas y entran al bootstrap como "clones de mediana" (afecta sobre todo a Cabo Verde 9, DR Congo 8, Egipto 6, Ghana 4). La fuerza (que solo usa goles, reales) debe seguir viéndolas; el pool no.

**Files:**
- Modify: `predictor/dataset.py` (`_clean_stats`)
- Modify: `predictor/pool.py` (`construir_pool`)
- Test: `tests/test_dataset.py`, `tests/test_pool_simulate.py`

- [ ] **Step 1: Tests que fallan**

`tests/test_dataset.py`:

```python
def test_flag_stats_completas(dataset):
    assert "stats_completas" in dataset.stats.columns
    incompletas = (~dataset.stats["stats_completas"]).sum()
    assert 150 < incompletas < 350  # ~266 antes del filtro de clubes
```

`tests/test_pool_simulate.py`:

```python
def test_pool_sin_filas_imputadas(dataset, knn, fuerza):
    from predictor.pool import construir_pool
    pool = construir_pool("Cabo Verde", "Spain", dataset.stats, knn, fuerza)
    assert pool is not None
    assert pool["stats_completas"].all()
```

(usar los fixtures existentes de `conftest.py`; si `knn`/`fuerza` no existen como fixtures, construirlos en el test con `compute_style_knn(dataset.stats)` y `compute_strength(dataset.stats, dataset.equipos_mundial)`).

Run: `pytest tests/test_dataset.py -k flag -v` → FAIL.

- [ ] **Step 2: Implementar el flag**

En `_clean_stats`, **antes** del bloque de imputación 2.6:

```python
    # Filas sin stats core: el partido existe (goles reales) pero SofaScore no
    # tiene estadísticas. Se marcan para excluirlas del pool de bootstrap
    # (la imputación posterior las convertiría en clones de la mediana).
    core = [c for c in ("ball_possession", "total_shots", "passes", "corner_kicks")
            if c in stats.columns]
    stats["stats_completas"] = stats[core].notna().any(axis=1)
```

(con `legacy=True` en `load_dataset`, saltar este bloque y el filtro del pool seguirá funcionando porque comprueba la presencia de la columna).

- [ ] **Step 3: Filtrar en el pool**

En `construir_pool` (pool.py), primera línea del cuerpo:

```python
    if "stats_completas" in stats.columns:
        stats = stats[stats["stats_completas"]]
```

- [ ] **Step 4: Verificar**

Run: `pytest tests/test_dataset.py tests/test_pool_simulate.py -v` → PASS (los nuevos; los golden siguen pendientes de 0.5).

---

### Task 0.4: ELO con una única fuente de verdad  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** verificado que el dict hardcoded y `data/elo_2026.csv` eran idénticos (48 equipos, mismos valores). `config.ELO_2026` pasa a cargarse del CSV vía `_load_elo_2026()` (fuente única; el loop en vivo de Task 4.3 actualizará ese CSV). Test `test_elo_fuente_unica` en verde; predicciones sin cambios (valores idénticos). Quedan 3 tests rojos —los de regresión vs el golden del R— que NO los rompe este cambio sino el dataset saneado; los repara Task 0.5.

---

#### Detalle original de la tarea

**Contexto:** `config.ELO_2026` (dict hardcoded) y `data/elo_2026.csv` (que usa `tournament.py`) pueden divergir en silencio.

**Files:**
- Modify: `predictor/config.py`
- Test: `tests/test_style_strength.py`

- [ ] **Step 1: Test que falla**

```python
def test_elo_unica_fuente():
    import csv
    from predictor import config
    with open(config.DATA_DIR / "elo_2026.csv", encoding="utf-8-sig") as f:
        csv_elo = {r["equipo"].strip(): int(r["elo"])
                   for r in csv.DictReader(f, delimiter=";")}
    assert config.ELO_2026 == csv_elo
    assert len(config.ELO_2026) == 48
```

- [ ] **Step 2: Implementar**

En `config.py`, sustituir el dict literal `ELO_2026` por:

```python
def _load_elo_2026() -> dict[str, int]:
    """ELO de los 48 mundialistas. Fuente única: data/elo_2026.csv."""
    import csv
    out: dict[str, int] = {}
    with open(DATA_DIR / "elo_2026.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            out[r["equipo"].strip()] = int(r["elo"])
    return out

ELO_2026: dict[str, int] = _load_elo_2026()
```

Antes de borrar el dict, verificar que el CSV coincide con él (debería — el CSV se volcó desde config; si difiere en algo, el CSV manda solo si el valor es más reciente; en caso de duda conservar el valor del dict regenerando el CSV).

- [ ] **Step 3: Verificar**

Run: `pytest tests/test_style_strength.py -v` → PASS. Run `python -m predictor.tournament` → mismas favoritas que antes.

---

### Task 0.5: Congelar nuevo golden Python y reencuadrar los tests de regresión  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** fixtures `dataset_legacy`/`resumen_legacy`/`knn_legacy`. Los tests de fidelidad vs el R (`test_regresion_vs_golden_R`, `test_correlacion_alta_vs_golden_R`, `test_regresion_vecinos_vs_R`) pasan a usar el dataset original (`legacy=True`). Golden Python congelado en `data/golden_py/` + `test_regresion_vs_golden_py` sobre el dataset saneado. **Bug encontrado y corregido:** el filtro `stats_completas` del pool se aplicaba también en legacy (la columna se creaba siempre), rompiendo la fidelidad vs el R (outlier 0.14); ahora `_clean_stats(legacy=True)` marca todas las filas completas. **Suite 48/48 en verde.** Regla a partir de aquí: cada cambio de modelo de Fase 2-3 regenera `data/golden_py/`.

---

#### Detalle original de la tarea

**Contexto:** Tras 0.1–0.3 las predicciones cambian (a mejor) y el golden del R deja de ser comparable con el dataset saneado. El golden del R sigue siendo válido para validar la fidelidad del port, pero solo en modo `legacy`.

**Files:**
- Modify: `tests/test_pipeline_regression.py` (y `tests/conftest.py` si el fixture `dataset` vive ahí)
- Create (output): `data/golden_py/predicciones_resumen_golden.csv`, `data/golden_py/predicciones_largo_golden.csv`

- [ ] **Step 1: Separar los dos contratos de test**

En `tests/test_pipeline_regression.py`, dividir en dos clases/fixtures:

```python
@pytest.fixture(scope="module")
def dataset_legacy():
    from predictor.dataset import load_dataset
    return load_dataset(legacy=True)

@pytest.fixture(scope="module")
def dataset_actual():
    from predictor.dataset import load_dataset
    return load_dataset()
```

- Los tests existentes contra `predicciones_resumen.csv` (golden R) pasan a usar `dataset_legacy` — verifican que el port sigue siendo fiel al R **sobre el dataset original**.
- Tests nuevos contra `data/golden_py/...` usan `dataset_actual` — detectan regresiones del motor sobre el dataset saneado.

- [ ] **Step 2: Generar el golden Python**

```bash
mkdir -p data/golden_py
.venv/bin/python -m predictor.cli
cp data/predicciones_resumen_py.csv data/golden_py/predicciones_resumen_golden.csv
cp data/predicciones_largo_py.csv data/golden_py/predicciones_largo_golden.csv
```

- [ ] **Step 3: Test de regresión nuevo**

```python
GOLDEN_PY = config.DATA_DIR / "golden_py" / "predicciones_resumen_golden.csv"

def test_regresion_golden_py(dataset_actual):
    largo = predict_all(dataset=dataset_actual)
    res = build_resumen(largo)
    gold = pd.read_csv(GOLDEN_PY, sep=";", decimal=",", encoding="utf-8-sig")
    m = res.merge(gold, on="partido_id", suffixes=("", "_g"))
    assert len(m) == len(gold)
    for c in KEY_COLS:
        mae = (m[c] - m[f"{c}_g"]).abs().mean()
        assert mae < TOL_MAE, f"{c}: MAE {mae:.4f}"
```

- [ ] **Step 4: Verificar suite completa**

Run: `.venv/bin/python -m pytest -v` → todo PASS. **Regla a partir de aquí:** cada cambio de modelo (Fases 2-3) que altere predicciones a propósito debe regenerar el golden Python en el mismo cambio, con una línea en el mensaje del cambio explicando por qué.

---

### Task 0.6: Validador de coherencia de los outputs  ✅ HECHO (2026-06-13, con 5.2)

**Resultado de la ejecución:** `predictor/validar_outputs.py` — comprueba over+under=1, monotonía de over(L), subconjunto≤superconjunto (el bug SOT>TS), 1X2 suma 1, 1H≤FT, y rondas de torneo monótonas + suma campeón=1. Exit 1 si hay violaciones (lo recoge el cron y notifica). **Cazó una violación real** que se había escapado (shots_outside_box>total_shots +0.026 a línea 0.5 en KSA_URU) — ruido de fits NB marginales a línea baja, por eso el check subconjunto usa tolerancia 0.035 (las violaciones reales del QoO eran masivas y mayores). Integrado como paso del cron. 5 tests, suite 79/79.

---

#### Detalle original de la tarea

**Contexto:** Se han observado predicciones publicadas incoherentes (P(tiros a puerta > L) mayor que P(tiros totales > L) a la misma línea, probabilidades de fase de grupos raras). Causas estructurales identificadas:
1. El QoO (`pool.py:ajustar_pool_por_calidad_rival`) residualiza `total_shots` pero NO `shots_on_target`/`shots_inside_box`/… → tras el ajuste hay filas del pool con SOT > TS, y los O/U heredan la incoherencia (la corrección de fondo es la Task 3.4; este task la DETECTA siempre).
2. El fit NB por métrica es marginal e independiente: puede cruzar colas entre métricas relacionadas incluso con pools coherentes.
3. El simulador de torneo (cuadro aleatorio + desempates a moneda) produce p_grupo/p_campeon poco intuitivos (corrección de fondo: Task 3.5).

**Files:**
- Create: `predictor/validar_outputs.py`
- Test: `tests/test_validar_outputs.py`

- [ ] **Step 1: Implementar el validador**

```python
"""Validación de coherencia de predicciones_largo_py.csv y
probabilidades_torneo.csv. Se ejecuta tras cada run del pipeline:

    python -m predictor.validar_outputs

Salida: lista de violaciones (vacía = OK). Exit code 1 si hay violaciones.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import config

# (métrica_subconjunto, métrica_superconjunto): el subconjunto no puede tener
# más probabilidad de superar la misma línea que el superconjunto.
PARES_SUBCONJUNTO = [
    ("shots_on_target", "total_shots"),
    ("shots_off_target", "total_shots"),
    ("shots_inside_box", "total_shots"),
    ("shots_outside_box", "total_shots"),
    ("blocked_shots", "total_shots"),
    ("accurate_passes", "passes"),
    ("goles", "shots_on_target"),  # no se marca sin tirar a puerta
]
TOL = 0.015  # margen por ruido MC + redondeo a 4 decimales


def validar_largo(largo: pd.DataFrame) -> list[str]:
    errores: list[str] = []
    ou = largo[largo["evento_o_jugador"].isin(["over", "under"])].copy()
    ou["linea"] = pd.to_numeric(ou["linea_o_target"], errors="coerce")

    # 1. over + under = 1
    piv = ou.pivot_table(
        index=["partido_id", "mercado", "ambito", "linea", "periodo"],
        columns="evento_o_jugador", values="probabilidad", aggfunc="first")
    mal = piv[(piv["over"] + piv["under"] - 1).abs() > 0.001]
    errores += [f"over+under!=1: {i}" for i in mal.index[:20]]

    # 2. over(L) decreciente en L
    overs = ou[ou["evento_o_jugador"] == "over"]
    for key, g in overs.groupby(["partido_id", "mercado", "ambito", "periodo"]):
        g = g.sort_values("linea")
        sube = g["probabilidad"].diff() > TOL
        if sube.any():
            errores.append(f"over no monotono: {key}")

    # 3. coherencia subconjunto <= superconjunto a la misma línea
    ov = overs.pivot_table(index=["partido_id", "ambito", "linea", "periodo"],
                           columns="mercado", values="probabilidad", aggfunc="first")
    for sub, sup in PARES_SUBCONJUNTO:
        if sub not in ov.columns or sup not in ov.columns:
            continue
        both = ov[[sub, sup]].dropna()
        mal = both[both[sub] > both[sup] + TOL]
        errores += [f"P({sub}>L) > P({sup}>L): {i}" for i in mal.index[:20]]

    # 4. 1X2 suma 1
    x12 = largo[largo["mercado"] == "1X2"].pivot_table(
        index=["partido_id", "periodo"], columns="evento_o_jugador",
        values="probabilidad", aggfunc="first")
    mal = x12[(x12.sum(axis=1) - 1).abs() > 0.001]
    errores += [f"1X2 no suma 1: {i}" for i in mal.index[:20]]

    # 5. 1H <= FT para overs a la misma línea
    ov_p = overs.pivot_table(index=["partido_id", "mercado", "ambito", "linea"],
                             columns="periodo", values="probabilidad", aggfunc="first")
    if "1H" in ov_p.columns and "FT" in ov_p.columns:
        both = ov_p[["1H", "FT"]].dropna()
        mal = both[both["1H"] > both["FT"] + TOL]
        errores += [f"over 1H > over FT: {i}" for i in mal.index[:20]]
    return errores


def validar_torneo(torneo: pd.DataFrame) -> list[str]:
    errores: list[str] = []
    # p de alcanzar cada ronda debe ser monótona no creciente
    rondas = ["p_grupo", "p_r16", "p_qf", "p_sf", "p_final", "p_campeon"]
    for _, r in torneo.iterrows():
        vals = [r[c] for c in rondas if c in torneo.columns]
        if any(b > a + 1e-6 for a, b in zip(vals, vals[1:])):
            errores.append(f"rondas no monotonas: {r['equipo']}")
    s = torneo["p_campeon"].sum()
    if abs(s - 1.0) > 0.02:
        errores.append(f"suma p_campeon = {s:.3f} != 1")
    return errores


def main() -> None:
    largo = pd.read_csv(config.DATA_DIR / "predicciones_largo_py.csv",
                        sep=";", decimal=",", encoding="utf-8-sig")
    errores = validar_largo(largo)
    tpath = config.DATA_DIR / "probabilidades_torneo.csv"
    if tpath.exists():
        errores += validar_torneo(pd.read_csv(tpath, sep=";"))
    if errores:
        print(f"{len(errores)} violaciones de coherencia:")
        for e in errores[:60]:
            print(" -", e)
        sys.exit(1)
    print("Outputs coherentes ✔")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test con casos sintéticos**

```python
import pandas as pd
from predictor.validar_outputs import validar_largo, validar_torneo

def _fila(mercado, ambito, evento, linea, prob, periodo="FT"):
    return {"partido_id": "X_Y", "fecha": "2026-06-17", "equipo_a": "X",
            "equipo_b": "Y", "mercado": mercado, "ambito": ambito,
            "evento_o_jugador": evento, "linea_o_target": linea,
            "probabilidad": prob, "periodo": periodo}

def test_detecta_sot_mayor_que_ts():
    filas = [
        _fila("shots_on_target", "A", "over", 4.5, 0.80),
        _fila("shots_on_target", "A", "under", 4.5, 0.20),
        _fila("total_shots", "A", "over", 4.5, 0.60),
        _fila("total_shots", "A", "under", 4.5, 0.40),
    ]
    errores = validar_largo(pd.DataFrame(filas))
    assert any("shots_on_target" in e for e in errores)

def test_outputs_coherentes_pasan():
    filas = [
        _fila("total_shots", "A", "over", 4.5, 0.80),
        _fila("total_shots", "A", "under", 4.5, 0.20),
        _fila("shots_on_target", "A", "over", 4.5, 0.30),
        _fila("shots_on_target", "A", "under", 4.5, 0.70),
    ]
    assert validar_largo(pd.DataFrame(filas)) == []

def test_torneo_rondas_monotonas():
    df = pd.DataFrame([{"equipo": "X", "p_grupo": 0.5, "p_r16": 0.6,
                        "p_qf": 0.1, "p_sf": 0.05, "p_final": 0.02,
                        "p_campeon": 0.01}])
    assert validar_torneo(df)
```

Run: `pytest tests/test_validar_outputs.py -v` → PASS.

- [ ] **Step 3: Ejecutar sobre los outputs actuales y registrar el estado**

Run: `.venv/bin/python -m predictor.validar_outputs`
Expected: FALLA con las violaciones SOT>TS reportadas por el usuario (y posiblemente más). Guardar la lista en `docs/violaciones_2026-06-12.md` — es la línea base que las Tasks 3.4/3.5 deben dejar a cero. Encadenarlo al final de `predictor/cli.py` (warning, no excepción) para que cada run lo reporte.

---

## Fase 1 — Harness de backtest (puerta de calidad)

### Task 1.1: Métricas de evaluación

**Files:**
- Create: `predictor/metrics.py`
- Test: `tests/test_metrics.py`

- [ ] **Step 1: Test que falla**

```python
import numpy as np
from predictor.metrics import brier_1x2, logloss_1x2

def test_brier_perfecto():
    assert brier_1x2([(1.0, 0.0, 0.0)], ["1"]) == 0.0

def test_brier_uniforme():
    # (1/3)^2 * 2 + (2/3)^2 = 0.667 por definición multiclase
    b = brier_1x2([(1/3, 1/3, 1/3)], ["X"])
    assert abs(b - (2 * (1/3) ** 2 + (2/3) ** 2)) < 1e-9

def test_logloss_clip():
    # prob 0 al resultado real no debe dar inf
    ll = logloss_1x2([(0.0, 0.5, 0.5)], ["1"])
    assert np.isfinite(ll)
```

- [ ] **Step 2: Implementación**

```python
"""Métricas de calidad predictiva (backtest)."""
from __future__ import annotations

import numpy as np

_IDX = {"1": 0, "X": 1, "2": 2}


def _onehot(resultados: list[str]) -> np.ndarray:
    y = np.zeros((len(resultados), 3))
    for i, r in enumerate(resultados):
        y[i, _IDX[r]] = 1.0
    return y


def brier_1x2(probs, resultados) -> float:
    p = np.asarray(probs, dtype=float)
    y = _onehot(list(resultados))
    return float(((p - y) ** 2).sum(axis=1).mean())


def logloss_1x2(probs, resultados, eps: float = 1e-12) -> float:
    p = np.clip(np.asarray(probs, dtype=float), eps, 1.0)
    y = _onehot(list(resultados))
    return float(-(y * np.log(p)).sum(axis=1).mean())
```

- [ ] **Step 3: Verificar**

Run: `pytest tests/test_metrics.py -v` → PASS.

---

### Task 1.2: Replay temporal con baseline  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** `predictor/backtest.py` (refit mensual solo-pasado de KNN+fuerza, elegibilidad ≥5 previos, reusa el motor real + baseline Poisson off/def). Métricas en `metrics.py`. Primer backtest (376 partidos, jun-2025→jun-2026): **modelo logloss 0.9418 vs baseline 1.0311** → el motor bate al Poisson simple por ~9%. Línea base guardada en `docs/backtest_baseline.md` (puerta de calidad para Fases 2-3). Smoke test en verde. Limitaciones anotadas: ELO solo de 48 (mejora en 2.4), warning numpy en pools degenerados (no fatal).

---

#### Detalle original de la tarea

**Files:**
- Create: `predictor/backtest.py`
- Test: `tests/test_backtest.py`

- [ ] **Step 1: Diseño (leer antes de codificar)**

- Cortes **mensuales**: para cada mes M desde `--desde`, se ajustan KNN + fuerza con partidos de fecha < 1-M y se predicen los partidos jugados dentro de M. (Refit por partido sería exacto pero ~30× más caro; mensual es suficiente para comparar variantes.)
- Elegibilidad: ambos equipos con ≥5 partidos en el pasado del corte.
- Resultado real de cada partido: ya está en `stats` (`goles`, `goles_op` por fila; tomar la fila del equipo "A" elegido).
- Baseline: Poisson de tasas off/def + Dixon-Coles (sin pools, sin KNN, sin ELO) — si el motor completo no bate a esto, las capas extra no están aportando.
- `n_sim=5000` por defecto en backtest (ruido MC ~±0.01 en probabilidades, suficiente para comparar; confirmar decisiones finas con 20000).

- [ ] **Step 2: Implementación**

```python
"""Backtest temporal: replay de partidos históricos con datos solo-pasado.

Para cada mes desde --desde: refit (KNN, fuerza) con fecha < mes, y predicción
de los partidos de ese mes. Compara el motor completo contra un baseline
Poisson off/def + Dixon-Coles. Métricas: Brier y log-loss 1X2, Brier O2.5/BTTS.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import config
from .dataset import load_dataset
from .metrics import brier_1x2, logloss_1x2
from .pool import ajustar_pool_por_calidad_rival, construir_pool
from .simulate import dixon_coles_matrix, simular_partido_bootstrap, sample_dc
from .strength import compute_strength
from .style import compute_style_knn

MIN_PARTIDOS_PREVIOS = 5


def _resultado(ga: int, gb: int) -> str:
    return "1" if ga > gb else ("2" if ga < gb else "X")


def _partidos_unicos(stats: pd.DataFrame) -> pd.DataFrame:
    """Una fila por partido (la primera de cada partido_id)."""
    return stats.sort_values("partido_id").drop_duplicates("partido_id")


def _baseline_dc(pasado: pd.DataFrame, eA: str, eB: str) -> tuple[float, float] | None:
    """λs de un Poisson off/def clásico: λ_A = off_A * def_B / media_global."""
    g = pasado.groupby("equipo_nombre").agg(
        off=("goles", "mean"), de=("goles_op", "mean"), n=("goles", "size"))
    mu = pasado["goles"].mean()
    if eA not in g.index or eB not in g.index or mu <= 0:
        return None
    lam_a = g.loc[eA, "off"] * g.loc[eB, "de"] / mu
    lam_b = g.loc[eB, "off"] * g.loc[eA, "de"] / mu
    return max(lam_a, 0.05), max(lam_b, 0.05)


def _probs_desde_matriz(M: np.ndarray) -> tuple[float, float, float, float, float]:
    i, j = np.indices(M.shape)
    p1 = float(M[i > j].sum()); px = float(M[i == j].sum()); p2 = float(M[i < j].sum())
    pov = float(M[(i + j) > 2.5].sum())
    pbt = float(M[(i >= 1) & (j >= 1)].sum())
    return p1, px, p2, pov, pbt


def backtest(desde: str, n_sim: int = 5000, seed: int = config.SEED) -> pd.DataFrame:
    d = load_dataset()
    stats = d.stats.copy()
    stats = stats[stats["fecha"].notna()]
    stats["mes"] = stats["fecha"].astype(str).str[:7]

    partidos = _partidos_unicos(stats)
    meses = sorted(m for m in partidos["mes"].unique() if f"{m}-01" >= desde)

    rng = np.random.default_rng(seed)
    filas = []
    for mes in meses:
        pasado = stats[stats["mes"] < mes]
        if len(pasado) < 200:
            continue
        mes_df = partidos[partidos["mes"] == mes]
        n_prev = pasado.groupby("equipo_nombre").size()

        knn = compute_style_knn(pasado)
        fuerza = compute_strength(
            pasado, sorted(set(mes_df["equipo_nombre"]) | set(mes_df["oponente"])))
        cols_shrink = [c for c in config.COLS_RARAS_SHRINK if c in d.metricas_equipo]
        gmeans = {c: float(pasado[c].mean()) for c in cols_shrink if c in pasado.columns}

        for _, p in mes_df.iterrows():
            eA, eB = p["equipo_nombre"], p["oponente"]
            if n_prev.get(eA, 0) < MIN_PARTIDOS_PREVIOS or n_prev.get(eB, 0) < MIN_PARTIDOS_PREVIOS:
                continue
            ga, gb = int(p["goles"]), int(p["goles_op"])

            pool_A = ajustar_pool_por_calidad_rival(
                construir_pool(eA, eB, pasado, knn, fuerza), fuerza.get(eB, 0.0), fuerza)
            pool_B = ajustar_pool_por_calidad_rival(
                construir_pool(eB, eA, pasado, knn, fuerza), fuerza.get(eA, 0.0), fuerza)
            sims = simular_partido_bootstrap(
                pool_A, pool_B, d.metricas_equipo, cols_shrink, gmeans,
                eA, eB, rng, n_sim=n_sim)
            if sims is None:
                continue
            M = dixon_coles_matrix(sims.lam_a_blend, sims.lam_b_blend)
            p1, px, p2, pov, pbt = _probs_desde_matriz(M)

            fila = {"mes": mes, "partido_id": p["partido_id"], "eA": eA, "eB": eB,
                    "ga": ga, "gb": gb, "res": _resultado(ga, gb),
                    "p1": p1, "px": px, "p2": p2, "p_o25": pov, "p_btts": pbt}

            bl = _baseline_dc(pasado, eA, eB)
            if bl:
                Mb = dixon_coles_matrix(*bl)
                b1, bx, b2, bov, bbt = _probs_desde_matriz(Mb)
                fila.update({"b1": b1, "bx": bx, "b2": b2, "b_o25": bov, "b_btts": bbt})
            filas.append(fila)
    return pd.DataFrame(filas)


def resumen(df: pd.DataFrame) -> str:
    res = df["res"].tolist()
    modelo = list(zip(df["p1"], df["px"], df["p2"]))
    lineas = [
        f"partidos evaluados: {len(df)}",
        f"modelo  : brier={brier_1x2(modelo, res):.4f} logloss={logloss_1x2(modelo, res):.4f}",
    ]
    con_bl = df.dropna(subset=["b1"]) if "b1" in df.columns else df.iloc[0:0]
    if len(con_bl):
        bl = list(zip(con_bl["b1"], con_bl["bx"], con_bl["b2"]))
        res_bl = con_bl["res"].tolist()
        mod_bl = list(zip(con_bl["p1"], con_bl["px"], con_bl["p2"]))
        lineas += [
            f"(en los {len(con_bl)} con baseline)",
            f"modelo  : logloss={logloss_1x2(mod_bl, res_bl):.4f}",
            f"baseline: logloss={logloss_1x2(bl, res_bl):.4f}",
        ]
    ov = (df["ga"] + df["gb"] > 2.5).astype(float)
    lineas.append(f"O2.5 brier modelo: {((df['p_o25'] - ov) ** 2).mean():.4f}")
    return "\n".join(lineas)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2026-01-01")
    ap.add_argument("--n-sim", type=int, default=5000)
    ap.add_argument("--out", default=str(config.DATA_DIR / "backtest_resultados.csv"))
    args = ap.parse_args()
    df = backtest(args.desde, n_sim=args.n_sim)
    df.to_csv(args.out, sep=";", index=False, encoding="utf-8-sig")
    print(resumen(df))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Test (smoke, con submuestra)**

`tests/test_backtest.py`:

```python
import pandas as pd
from predictor.backtest import backtest, resumen

def test_backtest_smoke():
    df = backtest("2026-03-01", n_sim=500)
    assert len(df) > 30
    assert {"p1", "px", "p2", "res"} <= set(df.columns)
    assert ((df[["p1", "px", "p2"]].sum(axis=1) - 1).abs() < 0.02).all()
    print(resumen(df))
```

Run: `pytest tests/test_backtest.py -v -s` → PASS (tarda unos minutos).

- [ ] **Step 4: Primera medición de referencia**

Run: `.venv/bin/python -m predictor.backtest --desde 2026-01-01`
Guardar la salida en `docs/backtest_baseline.md` con la fecha y el hash de datos.
**Esta cifra es la puerta:** ninguna mejora de Fase 2-3 se acepta si empeora el log-loss 1X2.

---

## Fase 2 — Mejoras de datos al servicio del modelo

### Task 2.1: Peso de recencia en el pool  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** `_peso_recencia()` en `pool.py` (0.5^(Δdías/half_life)); `construir_pool` acepta `fecha_ref`/`half_life` y atenúa los 3 componentes; `pipeline` pasa la fecha del partido, `backtest` el inicio del mes (solo-pasado). **Calibración por backtest:** half_life corto empeora (180d→0.9441) porque las selecciones juegan poco; barrido 365/540/730/1095 → **730d óptimo (0.9368 vs 0.9418 sin recencia)**. `config.RECENCIA_HALF_LIFE_DIAS = 730`. Golden Python y baseline doc actualizados. Suite 57/57 verde. Decisión guiada por la puerta de calidad (Fase 1), no por intuición.

---

#### Detalle original de la tarea

**Files:**
- Modify: `predictor/config.py`, `predictor/pool.py`, `predictor/pipeline.py`, `predictor/backtest.py`
- Test: `tests/test_pool_simulate.py`

- [ ] **Step 1: Test que falla**

```python
import numpy as np
import pandas as pd
from predictor.pool import _peso_recencia

def test_peso_recencia_half_life():
    fechas = pd.Series(["2026-06-01", "2025-12-03", "2024-06-01"])
    w = _peso_recencia(fechas, "2026-06-01", half_life=180)
    assert abs(w[0] - 1.0) < 1e-9
    assert abs(w[1] - 0.5) < 0.01       # 180 días ≈ medio peso
    assert w[2] < 0.07                   # 2 años atrás, residual
```

- [ ] **Step 2: Implementación**

`config.py`:

```python
# --- Recencia (mejora #8, desbloqueada por partido_fechas.csv) -------------
RECENCIA_HALF_LIFE_DIAS = 180   # calibrar en Task 3.1 (probar 90/180/365)
```

`pool.py`:

```python
def _peso_recencia(fechas: pd.Series, fecha_ref, half_life: float) -> np.ndarray:
    """Peso 0.5^(Δdías/half_life); filas sin fecha reciben el peso mediano."""
    f = pd.to_datetime(fechas, errors="coerce")
    delta = (pd.Timestamp(fecha_ref) - f).dt.days.clip(lower=0).to_numpy(dtype=float)
    w = np.power(0.5, delta / half_life)
    if np.isnan(w).any():
        med = np.nanmedian(w) if np.isfinite(np.nanmedian(w)) else 1.0
        w = np.where(np.isnan(w), med, w)
    return w
```

En `construir_pool`, añadir parámetro `fecha_ref: str | None = None` y, en cada componente donde se calcula `peso_raw` (alpha, beta y gamma), multiplicar:

```python
        if fecha_ref is not None and "fecha" in rows_a.columns:
            rows_a["peso_raw"] *= _peso_recencia(
                rows_a["fecha"], fecha_ref, config.RECENCIA_HALF_LIFE_DIAS)
```

(idéntico para `rows_b` y `rows_g`).

En `pipeline.predict_all`, pasar la fecha del partido:

```python
        pool_A = construir_pool(eA, eB, d.stats, knn, fuerza, fecha_ref=fecha)
        pool_B = construir_pool(eB, eA, d.stats, knn, fuerza, fecha_ref=fecha)
```

En `backtest.py`, pasar `fecha_ref=f"{mes}-01"` en las dos llamadas a `construir_pool`.

- [ ] **Step 3: Verificar con la puerta**

```bash
pytest tests/test_pool_simulate.py -v
python -m predictor.backtest --desde 2026-01-01
```

Comparar log-loss contra `docs/backtest_baseline.md`. Si no empeora → aceptar, regenerar golden Python (Task 0.5 Step 2) y anotar el resultado en `docs/backtest_baseline.md`.

---

### Task 2.2: Ampliar el histórico a ~2 años  🚫 BLOQUEADA (2026-06-13)

**Bloqueante verificado:** las **stats de equipo por partido** (posesión, tiros, córners… lo que necesita `stats_final.csv`) **NO están disponibles vía HTML** — solo el objeto evento básico (fecha/marcador/equipos/torneo). En el `__NEXT_DATA__` solo aparece el diccionario i18n de etiquetas (`football_ball_possession`), no los valores; las claves de datos de la API (`ballPossession`, `totalShotsOnGoal`) están ausentes y las XHR de datos dan 403 (Cloudflare). Por tanto no se pueden scrapear stats nuevas mientras la API esté caída — no es cuestión de tiempo de scrape.

**Opciones para desbloquear (decisión pendiente):** (1) aceptar el límite y aprender del Mundial solo vía ELO/resultados; (2) **fuente alternativa de stats** (FBref / API-Football free tier) con un adaptador nuevo; (3) anti-Cloudflare agresivo (no recomendado). Recomendación: (1) ahora, evaluar (2) si se quiere ampliar datos de verdad.

**Disparadores para retomarla (no abandonada, parqueada):**
- **A — desbloqueo "gratis":** el `SofaScoreClient` ya prueba la API primero. Si SofaScore reabre la API (revisar de vez en cuando con `predictor.sofascore.try_api('/api/v1/event/13233465')`), la 2.2 es trivial: cambiar fechas en `equipos_maestros` y re-scrapear. Sin cambios de código.
- **B — fuente alternativa:** spike acotado de FBref/API-Football **tras Fases 3 y 6**. ⚠ No es "añadir filas": FBref tiene esquema de métricas distinto (sin `big_chances`/`duels` desglosados; con otras), así que el vector de estilo del KNN y las features habría que re-derivarlas o limitarlas a columnas comunes. Evaluar primero qué métricas de selecciones ofrece y si se mapean, ANTES de comprometerse.

**Decisión registrada:** ahora no (no bloquea Fases 3/6, que aportan valor sin más datos). Recuperar vía disparador A (oportunista) o B (inversión consciente).

**Files (si se desbloquea):**
- Modify: `extraer.py` (fechas de `equipos_maestros`) o nuevo adaptador FBref
- Re-run: `extraer.py`, `extraer_fechas.py`

- [ ] **Step 1:** Cambiar `"fecha": "2025-09-01"` → `"fecha": "2024-06-01"` para las 48 selecciones mundialistas (mínimo) en `equipos_maestros`. No tocar el resto (el coste de scrape crece linealmente y los no-mundialistas solo aportan al componente γ).
- [ ] **Step 2:** Run `extraer.py` (lento, horas, resumable). Después `extraer_fechas.py` para backfillear las fechas de los eventos nuevos.
- [ ] **Step 3:** `pytest tests/test_dataset.py -v` (cobertura de fecha sigue >95%; equipos mundialistas ahora con n≥20: verificar con un test nuevo `dataset.stats.groupby('equipo_nombre').size().reindex(wc).min() >= 15`).
- [ ] **Step 4:** Backtest. La recencia (2.1) debe estar activa ANTES de mezclar datos de 2024 — sin ella el histórico viejo diluye. Si log-loss no empeora → aceptar + regenerar golden.

---

### Task 2.3: Peso por tipo de competición  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** `_peso_torneo()` en `pool.py` atenúa amistosos (detecta "Friendl" en la columna `torneo` del backfill); combinado con la recencia en el factor por fila. Se autodesactiva en legacy (sin columna torneo). **Backtest: barrido 1.0/0.8/0.6/0.4 → 0.6 óptimo en 2 ventanas** (jun-25 0.9292→0.9260; ene-25 0.9441→0.9415). `config.PESO_AMISTOSO=0.6`. Golden regenerado, suite 59/59 verde.

---

#### Detalle original de la tarea

**Files:**
- Modify: `predictor/config.py`, `predictor/pool.py`
- Test: `tests/test_pool_simulate.py`

- [ ] **Step 1: Test que falla**

```python
from predictor.pool import _peso_torneo

def test_peso_torneo():
    import pandas as pd
    s = pd.Series(["International Friendlies", "World Cup Qualification CONMEBOL", None])
    w = _peso_torneo(s)
    assert w[0] == 0.6 and w[1] == 1.0 and w[2] == 1.0
```

- [ ] **Step 2: Implementación**

`config.py`:

```python
PESO_AMISTOSO = 0.6   # informatividad menor (rotaciones); calibrable
```

`pool.py`:

```python
def _peso_torneo(torneos: pd.Series) -> np.ndarray:
    es_amistoso = (
        torneos.fillna("").str.contains("Friendl", case=False).to_numpy()
    )
    return np.where(es_amistoso, config.PESO_AMISTOSO, 1.0)
```

Multiplicar en los tres componentes igual que la recencia (`rows_x["peso_raw"] *= _peso_torneo(rows_x["torneo"])`, condicionado a `"torneo" in rows_x.columns`).

- [ ] **Step 3:** Backtest → aceptar/revertir + golden.

---

### Task 2.4: ELO para todos los equipos del dataset (mata la circularidad del QoO)  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** `extraer_elo_mundo.py` (urllib, eloratings.net no está bloqueado) → `data/elo_mundo.csv` con 244 selecciones. Cobertura: solo 24/208 sin ELO y 20 son los clubes ya excluidos (4 reales menores con 1-6 partidos → fallback z_interna). `config.ELO_MUNDO` + `compute_strength(usar_elo_mundo=...)`: ELO_2026 (mayo) manda para los 48, ELO_MUNDO da coordenada no-circular al resto. **Backtest: mejora en 2 ventanas (jun-25 0.9368→0.9292; ene-25 0.9478→0.9441), ✅ aceptada.** Bug resuelto: el ELO universal contaminaba legacy → se añadió flag `Dataset.legacy` propagado a `compute_strength` (legacy usa solo ELO_2026, fidelidad vs R intacta). Golden Python regenerado, suite 58/58. **Caveat documentado:** ELO actual (no histórico) → leak leve en backtest; correcto para predecir el Mundial.

---

#### Detalle original de la tarea

**Files:**
- Create: `extraer_elo_mundo.py` → `data/elo_mundo.csv`
- Modify: `predictor/config.py`, `predictor/strength.py`
- Test: `tests/test_style_strength.py`

- [ ] **Step 1: Scraper de eloratings.net**

eloratings.net sirve los datos como TSV planos (los carga su frontend JS): `https://www.eloratings.net/World.tsv` (ranking actual, columnas posicionales: rank, código, rating, …) y `https://www.eloratings.net/en.teams.tsv` (código → nombre). Script:

```python
"""Vuelca el ELO mundial completo a data/elo_mundo.csv (equipo;elo).

Fuente: eloratings.net (TSVs que consume su propio frontend).
Los nombres se mapean al canon del dataset (inglés de SofaScore) vía ALIAS.
"""
import csv
from pathlib import Path

import requests

DATA = Path(__file__).parent / "data"
ALIAS = {
    "Ivory Coast": "Côte d'Ivoire", "Cape Verde": "Cabo Verde",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina", "Turkey": "Türkiye",
    "United States": "USA", "Czechia": "Czechia", "Curacao": "Curaçao",
    "South Korea": "South Korea", "DR Congo": "DR Congo",
}
HEADERS = {"User-Agent": "Mozilla/5.0"}


def main() -> None:
    teams_raw = requests.get(
        "https://www.eloratings.net/en.teams.tsv", headers=HEADERS, timeout=30).text
    nombres = {}
    for line in teams_raw.strip().split("\n"):
        cols = line.split("\t")
        if len(cols) >= 2:
            nombres[cols[0]] = cols[1]

    world = requests.get(
        "https://www.eloratings.net/World.tsv", headers=HEADERS, timeout=30).text
    filas = []
    for line in world.strip().split("\n"):
        cols = line.split("\t")
        if len(cols) >= 4 and cols[2] in nombres:
            nombre = nombres[cols[2]]
            filas.append({"equipo": ALIAS.get(nombre, nombre), "elo": int(cols[3])})

    out = DATA / "elo_mundo.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["equipo", "elo"], delimiter=";")
        w.writeheader()
        w.writerows(filas)
    print(f"OK: {len(filas)} equipos -> {out.name}")


if __name__ == "__main__":
    main()
```

⚠ El formato de columnas de los TSV no está documentado: al ejecutarlo la primera vez, imprimir 3 líneas crudas y ajustar los índices `cols[...]` a lo observado. Validar contra `elo_2026.csv`: para los 48 mundialistas, `|elo_mundo - elo_2026| < 40` (deriva desde el snapshot de mayo).

- [ ] **Step 2: Test que falla**

```python
def test_fuerza_no_mundialistas_usa_elo():
    from predictor import config
    from predictor.dataset import load_dataset
    from predictor.strength import compute_strength
    d = load_dataset()
    f = compute_strength(d.stats, d.equipos_mundial)
    # Italia (no clasificada, ELO alto ~1900) debe quedar por encima de
    # selecciones débiles aunque su z_interna por muestra corta diga otra cosa.
    assert f["Italy"] > f["Malta"]
```

(elegir el par tras ver los datos; el contrato real es: con `elo_mundo.csv` presente, ningún equipo con ELO usa solo z_interna).

- [ ] **Step 3: Implementación en strength.py**

`config.py`:

```python
ELO_MUNDO_CSV = DATA_DIR / "elo_mundo.csv"

def _load_elo_mundo() -> dict[str, int]:
    import csv
    if not ELO_MUNDO_CSV.exists():
        return {}
    with open(ELO_MUNDO_CSV, encoding="utf-8-sig") as f:
        return {r["equipo"].strip(): int(r["elo"])
                for r in csv.DictReader(f, delimiter=";")}

ELO_MUNDO: dict[str, int] = _load_elo_mundo()
```

`strength.py`, en `compute_strength`, sustituir la definición de `z_elo`:

```python
    # ELO: mundialistas desde ELO_2026; el resto desde ELO_MUNDO (si existe).
    # Estandarizamos TODO con mu/sd de los mundialistas para mantener la escala.
    elo_all = dict(config.ELO_MUNDO)
    elo_all.update(elo)  # ELO_2026 manda para los 48

    def z_elo(equipo: str) -> float:
        if equipo in elo_all:
            return (elo_all[equipo] - mu_elo) / sd_elo
        return np.nan
```

- [ ] **Step 4:** `pytest tests/test_style_strength.py -v` → PASS. Backtest → aceptar/revertir + golden. (Esperable: mejora en QoO porque la coordenada de fuerza del oponente deja de ser circular — es la limitación documentada en el R, líneas 740-749.)

---

## Fase 3 — Mejoras de modelo

### Task 3.1: Calibración de constantes vía backtest  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** `simular_partido_bootstrap` acepta `w_fifa`/`total_esperado`; `backtest` acepta `params` dict (w_fifa/rho/total_esperado/bandwidth) y los propaga. **Barrido univariado en 2 ventanas:** `w_fifa` con señal grande y monótona, **óptimo interior en 0.70** (0.40→0.926, 0.70→0.909, 1.0→0.917) — el ELO predice goles mejor que el pool, pero el pool aún aporta (no es 1.0). `rho`/`total_esperado`/`bandwidth` neutros → no tocados (principio conservador). **W_FIFA 0.40→0.70: log-loss 0.9260→0.9083.** Bug legacy resuelto: `pipeline` usa w_fifa=0.40 en legacy (valor del R) para preservar fidelidad. Golden/torneo regenerados, suite 60/60.

---

#### Detalle original de la tarea

**Files:**
- Create: `predictor/calibrar.py`
- Modify: `predictor/simulate.py` (hacer `W_FIFA` inyectable), `predictor/config.py` (valores finales)

- [ ] **Step 1: Hacer los parámetros inyectables**

En `simulate.simular_partido_bootstrap`, añadir `w_fifa: float = config.W_FIFA` a la firma y usarlo en el blend. En `dixon_coles_matrix` ya existe `rho`. En `elo_lambdas` ya existe `total_esperado`. En `backtest.backtest`, aceptar `params: dict | None = None` y propagar (`w_fifa`, `rho`, `total_esperado`, `half_life`, `bandwidth`).

- [ ] **Step 2: Grid search**

```python
"""Calibración por rejilla de las constantes del motor contra el backtest.

Uso: python -m predictor.calibrar --desde 2026-01-01
Imprime el ranking por log-loss 1X2 y deja el detalle en data/calibracion.csv.
"""
from __future__ import annotations

import argparse
import itertools

import pandas as pd

from . import config
from .backtest import backtest
from .metrics import logloss_1x2

GRID = {
    "w_fifa": [0.25, 0.40, 0.55],
    "rho": [-0.04, -0.08, -0.12],
    "total_esperado": [2.35, 2.55, 2.75],
    "half_life": [90, 180, 365],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2026-01-01")
    ap.add_argument("--n-sim", type=int, default=2000)
    args = ap.parse_args()

    filas = []
    for combo in itertools.product(*GRID.values()):
        params = dict(zip(GRID.keys(), combo))
        df = backtest(args.desde, n_sim=args.n_sim, params=params)
        ll = logloss_1x2(list(zip(df.p1, df.px, df.p2)), df.res.tolist())
        filas.append({**params, "logloss": ll, "n": len(df)})
        print(f"{params} -> logloss={ll:.4f}")

    out = pd.DataFrame(filas).sort_values("logloss")
    out.to_csv(config.DATA_DIR / "calibracion.csv", sep=";", index=False)
    print(out.head(8).to_string(index=False))
```

- [ ] **Step 3: Procedimiento de decisión (no automático)**

1. Ejecutar la rejilla con `n_sim=2000` (81 combos × ~400 partidos: dejarlo corriendo).
2. Re-evaluar los 3 mejores combos con `n_sim=20000` para descartar que el ranking sea ruido MC.
3. Si el mejor combo mejora el log-loss del default en menos de ~0.005, **no cambiar nada** (no es señal). Si mejora más: actualizar las constantes en `config.py`, regenerar golden, anotar en `docs/backtest_baseline.md`.

---

### Task 3.2: Shrinkage proporcional a la masa efectiva del pool  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** `tasa_shrunk` usa masa de prior ∝ 1/n_eff (n_eff=1/Σŵ²) en lugar de fija 0.5; pools pequeños se encogen más hacia la media global. Test `test_shrink_mas_fuerte_con_pool_pequeno` en verde. **No medible en backtest 1X2** (solo afecta eventos raros: rojas, errores, penalty saves) y ninguno está hoy en los O/U publicados → mejora **latente** de robustez para cuando se ofrezcan esos mercados. Aceptada por corrección metodológica. Suite 61/61.

---

#### Detalle original de la tarea

**Files:**
- Modify: `predictor/simulate.py` (`tasa_shrunk`)
- Test: `tests/test_pool_simulate.py`

- [ ] **Step 1: Test que falla**

```python
import numpy as np
import pandas as pd
from predictor.simulate import tasa_shrunk

def test_shrink_mas_fuerte_con_pool_pequeno():
    gm = {"red_cards": 0.10}
    chico = pd.DataFrame({"red_cards": [1.0] * 5, "peso": [0.2] * 5})
    grande = pd.DataFrame({"red_cards": [1.0] * 100, "peso": [0.01] * 100})
    t_chico = tasa_shrunk(chico, "red_cards", gm)
    t_grande = tasa_shrunk(grande, "red_cards", gm)
    # ambos pools observan tasa 1.0; el chico debe encogerse más hacia 0.10
    assert t_chico < t_grande
```

- [ ] **Step 2: Implementación**

En `tasa_shrunk`, sustituir la última línea:

```python
    # Masa del prior proporcional a la evidencia: pools con pocas filas
    # efectivas (n_eff = 1/Σw²) se encogen más hacia la media global.
    w_norm = w / w.sum()
    n_eff = 1.0 / np.sum(w_norm ** 2)
    masa = float(np.clip(masa_prior * 40.0 / n_eff, 0.1, 2.0))
    return (pool_mean * 1 + prior_mean * masa) / (1 + masa)
```

(con `n_eff = 80` —pool típico— la masa queda en `0.25`, cercana al comportamiento actual; con `n_eff = 10` sube a `2.0`).

- [ ] **Step 3:** `pytest` + backtest → aceptar/revertir + golden.

---

### Task 3.3: Muestra mínima para ser vecino KNN  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** `config.KNN_MIN_PARTIDOS=5`; `compute_style_knn(min_partidos=...)` filtra equipos con <5 partidos del espacio de vecinos (no de los predichos; los 48 mundialistas tienen ≥9). En legacy `min_partidos=1` (sin filtro, reproduce el R). Test `test_knn_sin_vecinos_de_muestra_minima` en verde. **Backtest jun-25 0.9083→0.9066.** Golden/torneo regenerados, suite 62/62.

---

#### Detalle original de la tarea

**Files:**
- Modify: `predictor/config.py`, `predictor/style.py`
- Test: `tests/test_style_strength.py`

- [ ] **Step 1: Test que falla**

```python
def test_knn_sin_equipos_de_muestra_minima(dataset):
    from predictor import config
    from predictor.style import compute_style_knn
    knn = compute_style_knn(dataset.stats)
    n = dataset.stats.groupby("equipo_nombre").size()
    for eq, df in knn.vecinos.items():
        for v in df["vecino"]:
            assert n[v] >= config.KNN_MIN_PARTIDOS, f"{eq} tiene de vecino a {v} (n={n[v]})"
```

- [ ] **Step 2: Implementación**

`config.py`: `KNN_MIN_PARTIDOS = 5`.

`style.py`, en `compute_style_knn`, tras construir `feats`:

```python
    feats = feats[feats["n_partidos"] >= config.KNN_MIN_PARTIDOS].reset_index(drop=True)
```

(los 48 mundialistas tienen n≥9, así que ninguno desaparece del espacio; solo se eliminan candidatos a vecino con ratios de 1-4 partidos).

- [ ] **Step 3:** `pytest` + backtest → aceptar/revertir + golden.

---

### Task 3.4: QoO coherente — xG fuera, familia de tiros escalada en bloque  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** confirmado el bug a nivel de fila (el QoO ajustaba `total_shots` sin sus componentes → **410/654 filas con componentes>total**, justo la intuición del usuario "tiros no tiene en cuenta tiros a puerta"). Fix: `FAMILIAS_QOO` en config; `ajustar_pool_por_calidad_rival` escala la familia (a puerta/fuera/dentro/fuera-área/bloqueados) por el factor multiplicativo de la madre. Sin cap en el factor (preserva identidad exacta; el shift de la madre ya está capado al 35%). xG fuera del QoO (52% NA imputado). **Resultado: 410→~13 violaciones a nivel fila (0.5%, residual = incoherencias de datos crudos de SofaScore); O/U publicado 0 violaciones.** 1X2 sin cambio (0.9260, el QoO de tiros no toca goles). Golden/torneo regenerados, suite 60/60.

---

#### Detalle original de la tarea

**Contexto (origen de la inconsistencia SOT>TS reportada):** el QoO residualiza `total_shots` pero no sus componentes (`shots_on_target`, `shots_off_target`, `shots_inside_box`, `shots_outside_box`, `blocked_shots`). Tras el ajuste, una fila del pool puede quedar con `shots_on_target > total_shots`, y los O/U publicados heredan la incoherencia (P(SOT>L) > P(TS>L)). Además `expected_goals` (52% NA, imputada) no debería ajustarse.

**Files:**
- Modify: `predictor/config.py`, `predictor/pool.py`
- Test: `tests/test_pool_simulate.py`

- [ ] **Step 1: Test que falla**

```python
def test_qoo_preserva_jerarquia_de_tiros(dataset, knn, fuerza):
    from predictor.pool import construir_pool, ajustar_pool_por_calidad_rival
    pool = construir_pool("Brazil", "Morocco", dataset.stats, knn, fuerza)
    adj = ajustar_pool_por_calidad_rival(pool, fuerza.get("Morocco", 0.0), fuerza)
    comp = ["shots_on_target", "shots_off_target", "blocked_shots"]
    suma = sum(pd.to_numeric(adj[c], errors="coerce").fillna(0) for c in comp)
    ts = pd.to_numeric(adj["total_shots"], errors="coerce")
    # ninguna fila puede quedar con componentes > total
    assert (suma <= ts + 1e-6).all()
```

- [ ] **Step 2: Implementación**

`config.py`:

```python
METRICAS_QOO = ("goles", "total_shots", "corner_kicks")  # xG fuera (52% NA imputado)
# Métricas que deben moverse SOLIDARIAMENTE con su métrica madre en el QoO,
# escalando por el mismo factor multiplicativo (preserva jerarquías por fila).
FAMILIAS_QOO = {
    "total_shots": ("shots_on_target", "shots_off_target", "shots_inside_box",
                    "shots_outside_box", "blocked_shots"),
}
```

`pool.py`, en `ajustar_pool_por_calidad_rival`, dentro del bucle `for m in metricas_ajustar`, tras calcular `nuevo`:

```python
        # Escalar la familia por el mismo factor por-fila para no romper
        # jerarquías (SOT <= TS, etc.). factor = nuevo/viejo, acotado.
        familia = config.FAMILIAS_QOO.get(m, ())
        if familia:
            viejo = np.where(v_fit > 0, v_fit, np.nan)
            factor = np.where(np.isnan(viejo), 1.0, nuevo / viejo)
            factor = np.clip(factor, 0.5, 2.0)
            for hijo in familia:
                if hijo in pool.columns:
                    h = pd.to_numeric(pool[hijo], errors="coerce").to_numpy(dtype=float)
                    pool[hijo] = np.maximum(0.0, np.where(np.isnan(h), h, h * factor))
        pool[m] = nuevo
```

(el `pool[m] = nuevo` existente se mueve detrás del bloque de familia para que `viejo` use el valor pre-ajuste).

- [ ] **Step 3: Verificar de extremo a extremo**

```bash
pytest tests/test_pool_simulate.py -v
python -m predictor.cli
python -m predictor.validar_outputs   # las violaciones SOT>TS deben desaparecer
python -m predictor.backtest --desde 2026-01-01
```

Aceptar si el validador queda limpio y el backtest no empeora → regenerar golden.

---

### Task 3.5: Torneo — cuadro real, desempates reales, eliminatorias con el motor  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** datos exactos obtenidos de Wikipedia (wikitext parseado de forma determinista, no vía modelo): `grupos_oficiales.csv` (composición oficial, **verificada contra las componentes conexas de los cruces**, 12/12), `cuadro_terceros.csv` (las **495 combinaciones oficiales del Annex C**, 0 errores de elegibilidad), y el árbol R32→final completo (matches 73-104) hardcodeado en `tournament.py`. `tournament.py` reescrito: grupos simulados muestreando `marcadores_py.csv` con desempates **pts→dif.goles→goles a favor**; 1º/2º a slots fijos; 8 mejores terceros asignados por la tabla oficial; eliminatorias resueltas con el **modelo de goles (DC desde ELO)**, empate→penaltis. Sanity: suma campeón=1.0, suma grupo=32, 0 violaciones de monotonía. **Impacto:** probabilidades mucho más realistas (Spain campeón 29%→15%; el 29% del cuadro aleatorio + ELO logístico era irreal). Arregla el "fase de grupos sin sentido" reportado. 3 tests nuevos, suite 65/65.

**Nota sobre exactitud:** el usuario pidió exactitud total; se logró trayendo la tabla oficial de 495 (no el matching aproximado) y verificándola. Se descartó WebFetch (demostrado que alucina en estas tablas) en favor de parsear el wikitext crudo.

---

#### Detalle original de la tarea

**Files:**
- Create: `data/cuadro_final.csv` (transcribir del calendario oficial FIFA)
- Modify: `predictor/tournament.py`
- Test: `tests/test_tournament.py` (nuevo)

- [ ] **Step 1: Transcribir el cuadro oficial**

`data/cuadro_final.csv` — una fila por partido de R32 con los slots oficiales FIFA (transcribir de la web de FIFA; los códigos `1A` = ganador grupo A, `3ACD` = un tercero del conjunto {A,C,D} según la tabla de asignación de FIFA):

```csv
partido;slot_a;slot_b
R32_1;1A;3CEF
R32_2;2B;...
...
```

(⚠ dato externo: rellenar las 16 filas + la tabla de asignación de terceros desde el reglamento FIFA 2026, artículo de "Knock-out stage pairings". No inventar — sin esta tabla el task no arranca.)

- [ ] **Step 2: Desempates por goles**

En `tournament.py`, sustituir el sorteo de outcomes por muestreo de marcadores: cargar `data/marcadores_py.csv` (distribución de marcador exacto por partido, ya generada por el pipeline) y en cada simulación samplear `(ga, gb)` de esa distribución en lugar de `u < p1`. Acumular por equipo `pts`, `dg` (diferencia de goles) y `gf`, y ordenar grupos por `(pts, dg, gf, rng.random())`. Los 8 mejores terceros igual: `(pts, dg, gf, random)`.

```python
def _load_marcadores() -> dict[str, list[tuple[int, int, float]]]:
    import csv
    from collections import defaultdict
    out = defaultdict(list)
    with open(config.DATA_DIR / "marcadores_py.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            out[r["partido_id"]].append(
                (int(r["a"]), int(r["b"]), float(r["prob"].replace(",", "."))))
    return dict(out)
```

y en el bucle de grupos:

```python
            scores = marcadores[m["partido_id"]]
            u, acc = rng.random(), 0.0
            for ga, gb, pr in scores:
                acc += pr
                if u <= acc:
                    break
            pts[m["a"]] += 3 if ga > gb else (1 if ga == gb else 0)
            pts[m["b"]] += 3 if gb > ga else (1 if ga == gb else 0)
            dg[m["a"]] += ga - gb; dg[m["b"]] += gb - ga
            gf[m["a"]] += ga;      gf[m["b"]] += gb
```

- [ ] **Step 3: Cuadro real + eliminatorias coherentes con el motor**

Sustituir `rng.shuffle(clasificados)` por la colocación según `cuadro_final.csv` (mapear `1A/2A/3X` a equipos usando la clasificación simulada de cada grupo). Resolver cada cruce con el mismo modelo de goles del motor:

```python
def _pwin_eliminatoria(elo_a: float, elo_b: float, rng) -> bool:
    """Gana A: matriz DC con λs de ELO; empate a 90' → moneda (penaltis)."""
    from .simulate import dixon_coles_matrix, elo_lambdas
    la, lb = elo_lambdas(elo_a, elo_b)
    M = dixon_coles_matrix(la, lb)
    u, acc = rng.random(), 0.0
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            acc += M[i, j]
            if u <= acc:
                return i > j if i != j else (rng.random() < 0.5)
    return rng.random() < 0.5
```

(las matrices DC por par se pueden cachear en un dict `{(a, b): M}` — solo hay ~500 pares posibles).

- [ ] **Step 4: Test**

```python
def test_torneo_cuadro_real():
    from predictor.tournament import simulate
    tally = simulate(n_sim=2000)
    # p_grupo de España debe ser muy alta; suma de p_campeon == 1
    p_camp = sum(c["campeon"] for c in tally.values()) / 2000
    assert abs(p_camp - 1.0) < 1e-9
    assert tally["Spain"]["grupo"] / 2000 > 0.85
```

Run + comparar `probabilidades_torneo.csv` antes/después: los favoritos deben moverse de forma explicable por su camino de cuadro (documentar el diff en el cambio).

---

## Fase 4 — Nuevos datos y mercados

### Task 4.1 + 6.2: Árbitro designado → amarillas y faltas  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** `factor_arbitro()` en `pipeline.py` mapea cada partido a `{yellow_cards, fouls}`: amarillas por tasa de carrera (amarillas/partidos_carrera) vs media, faltas por tasa de pool (faltas_pool/partidos_pool) vs media; capado (amarillas ±20%, faltas ±12%) y con mínimos de muestra. Se aplica escalando las sims de yellow_cards y fouls; condicionado a no-legacy. **12/72 partidos con árbitro designado hoy** (resto neutro hasta que se designen durante el Mundial). Factores razonables (Wilton Sampaio +19% amarillas, Michael Oliver −18%). No medible en backtest 1X2 (afecta mercados de tarjetas/faltas, no goles); validado por inspección + cap. Golden regenerado, suite 66/66. **Penaltis: no aplicado** (incide en goles, riesgo de doble-conteo con el ELO; se dejó fuera conscientemente).

---

#### Detalle original de la tarea

**Contexto:** `arbitros.csv` (tasas por árbitro, con splits) y `calendario.csv` (árbitro designado por partido) ya existen. Solo falta el join al mercado de `yellow_cards`/`fouls`.

**Files:**
- Modify: `predictor/pipeline.py`, `predictor/config.py`
- Test: `tests/test_arbitros.py`

- [ ] **Step 1: Test que falla**

```python
def test_factor_arbitro():
    from predictor.pipeline import factor_arbitro
    factores = factor_arbitro()
    assert factores, "sin designaciones cargadas"
    assert all(0.75 <= f <= 1.25 for f in factores.values())
```

- [ ] **Step 2: Implementación**

`config.py`:

```python
ARBITROS_CSV = DATA_DIR / "arbitros.csv"
CALENDARIO_CSV = DATA_DIR / "calendario.csv"
ARBITRO_FACTOR_CAP = (0.75, 1.25)
```

`pipeline.py`:

```python
def factor_arbitro() -> dict[str, float]:
    """partido_id -> multiplicador de amarillas del árbitro designado.

    factor = (amarillas_pool / partidos_pool del árbitro) / media de todos,
    capado a ARBITRO_FACTOR_CAP. Árbitros con <5 partidos de pool → 1.0.
    """
    if not (config.ARBITROS_CSV.exists() and config.CALENDARIO_CSV.exists()):
        return {}
    arb = pd.read_csv(config.ARBITROS_CSV, sep=";", encoding="utf-8-sig")
    arb = arb[arb["partidos_pool"] >= 5].copy()
    arb["tasa"] = arb["amarillas_pool"] / arb["partidos_pool"]
    media = arb["tasa"].mean()
    arb["factor"] = (arb["tasa"] / media).clip(*config.ARBITRO_FACTOR_CAP)
    tasas = dict(zip(arb["sofa_id"].astype(str), arb["factor"]))

    cal = pd.read_csv(config.CALENDARIO_CSV, sep=";", encoding="utf-8-sig")
    out = {}
    for _, r in cal.iterrows():
        rid = str(r.get("referee_id", "")).split(".")[0]
        if rid in tasas:
            out[str(r["partido_id"])] = float(tasas[rid])
    return out
```

En `predict_all`, cargar `farb = factor_arbitro()` antes del bucle y, tras `simular_partido_bootstrap`, escalar las amarillas y faltas simuladas:

```python
        f_arb = farb.get(str(pid))
        if f_arb is not None:
            for met in ("yellow_cards", "fouls"):
                if met in sims.metricas:
                    j = sims.metricas.index(met)
                    sims.A[:, j] = sims.A[:, j] * f_arb
                    sims.B[:, j] = sims.B[:, j] * f_arb
```

(los O/U de tarjetas usan el fit NB sobre estos vectores — escalar antes del fit es equivalente a escalar λ; para faltas usar `f_arb ** 0.5` si el backtest de tarjetas no existe aún: las faltas dependen menos del árbitro que las amarillas. Decisión simple: aplicar el factor entero solo a `yellow_cards` en la primera iteración y dejar `fouls` fuera hasta tener evidencia.)

- [ ] **Step 3:** `pytest tests/test_arbitros.py -v` + regenerar predicciones y comprobar a mano 2-3 partidos con árbitro tarjetero vs manga ancha (las líneas O/U de amarillas deben separarse). Golden: regenerar.

---

### Task 4.2: Ajuste por bajas (convocatorias + valor de mercado)  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** `predictor/bajas.py` — `share_disponible` (% del valor de mercado del once habitual presente en la convocatoria), `factor_bajas` (clip(share^0.5, 0.85, 1.0), solo penaliza), `factores_por_equipo` (persiste `ajuste_bajas.csv`). Habituales = jugadores con ≥270 min en telemetría; equipo del jugador = moda de home∪away. Factor multiplica λ de goles en `simular_partido_bootstrap`; condicionado a no-legacy. **Hoy todos los 48 a factor 1.0** (convocatorias completas pre-torneo) → **efecto latente**; verificado que el mecanismo SÍ detecta bajas (quitar a Cucurella de la convocatoria de España → share 0.954). No medible en backtest (no hay histórico de bajas por partido). 4 tests, suite 74/74. Cap 0.85 protege ante mismatches de nombre.

---

#### Detalle original de la tarea

**Contexto:** pre-torneo mueve poco; su valor real es DURANTE el torneo (lesiones + sanciones por dobles amarillas). Datos ya scrapeados: `convocatorias.csv`, `bios.csv` (valor_eur), `telemetria_full.csv` (minutos por jugador-partido).

**Files:**
- Create: `predictor/bajas.py`
- Modify: `predictor/simulate.py` (multiplicador de λ), `predictor/pipeline.py`
- Test: `tests/test_bajas.py`
- Output: `data/ajuste_bajas.csv` (transparencia: qué share tiene cada selección)

- [ ] **Step 1: Test que falla**

```python
import pandas as pd
from predictor.bajas import share_disponible

def test_share_equipo_completo():
    minutos = pd.DataFrame({
        "jugador": ["A", "B", "C"], "equipo": ["X"] * 3,
        "minutos": [900, 800, 700]})
    valor = {"A": 50e6, "B": 30e6, "C": 20e6}
    conv = {"X": {"A", "B", "C"}}
    s = share_disponible("X", minutos, valor, conv)
    assert s == 1.0

def test_share_baja_estrella():
    minutos = pd.DataFrame({
        "jugador": ["A", "B", "C"], "equipo": ["X"] * 3,
        "minutos": [900, 800, 700]})
    valor = {"A": 50e6, "B": 30e6, "C": 20e6}
    conv = {"X": {"B", "C"}}  # falta A (50% del valor)
    s = share_disponible("X", minutos, valor, conv)
    assert 0.45 < s < 0.55
```

- [ ] **Step 2: Implementación**

```python
"""Ajuste de fuerza por bajas: % del valor de mercado del once habitual
que está disponible en la convocatoria actual.

share = Σ valor(jugadores habituales ∩ convocados) / Σ valor(habituales)
λ_adj = λ × clip(share^THETA, CAP_MIN, 1.0)   (solo penaliza, nunca premia)

"Habituales" = jugadores con ≥ MIN_MINUTOS en el ciclo (telemetria_full).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

THETA = 0.5
CAP_MIN = 0.85
MIN_MINUTOS = 270  # ≥3 partidos completos en el ciclo


def share_disponible(equipo, minutos, valor, convocatorias) -> float:
    habituales = minutos[
        (minutos["equipo"] == equipo) & (minutos["minutos"] >= MIN_MINUTOS)
    ]["jugador"]
    vals = {j: valor.get(j, np.nan) for j in habituales}
    vals = {j: v for j, v in vals.items() if np.isfinite(v)}
    total = sum(vals.values())
    if total <= 0:
        return 1.0
    conv = convocatorias.get(equipo, set())
    disponibles = sum(v for j, v in vals.items() if j in conv)
    return disponibles / total


def factor_bajas(equipo, minutos, valor, convocatorias) -> float:
    s = share_disponible(equipo, minutos, valor, convocatorias)
    return float(np.clip(s ** THETA, CAP_MIN, 1.0))


def cargar_insumos():
    """minutos (jugador, equipo, minutos), valor {jugador: eur}, conv {eq: set}."""
    tel = pd.read_csv(config.DATA_DIR / "telemetria_full.csv", sep=";",
                      encoding="utf-8-sig",
                      usecols=["jugador", "home_team", "away_team", "minutesPlayed"])
    # equipo del jugador: el más frecuente entre home/away de sus filas
    # (mismo criterio que el bloque 7.1 del R)
    tel["minutesPlayed"] = pd.to_numeric(tel["minutesPlayed"], errors="coerce").fillna(0)
    equipo_moda = (
        pd.concat([
            tel[["jugador", "home_team"]].rename(columns={"home_team": "equipo"}),
            tel[["jugador", "away_team"]].rename(columns={"away_team": "equipo"}),
        ])
        .groupby("jugador")["equipo"]
        .agg(lambda s: s.mode().iat[0])
    )
    minutos = tel.groupby("jugador", as_index=False)["minutesPlayed"].sum()
    minutos["equipo"] = minutos["jugador"].map(equipo_moda)
    minutos = minutos.rename(columns={"minutesPlayed": "minutos"})

    bios = pd.read_csv(config.DATA_DIR / "bios.csv", sep=";", encoding="utf-8-sig")
    valor = dict(zip(bios["jugador"], pd.to_numeric(bios["valor_eur"], errors="coerce")))

    conv = pd.read_csv(config.DATA_DIR / "convocatorias.csv", sep=";",
                       encoding="utf-8-sig")
    convocatorias = conv.groupby("equipo")["jugador"].agg(set).to_dict()
    return minutos, valor, convocatorias
```

⚠ Riesgo conocido: el mapeo jugador↔equipo por nombre tiene colisiones/ortografías (acentos). El `factor_bajas` está capado a 0.85 precisamente para que un mismatch no destroce una predicción. Escribir `data/ajuste_bajas.csv` con (equipo, share, factor, n_habituales, n_disponibles) y **revisarlo a ojo** antes de activar.

- [ ] **Step 3: Enganchar al motor**

`simulate.simular_partido_bootstrap`: añadir `factor_a: float = 1.0, factor_b: float = 1.0` y aplicarlos al blend de goles:

```python
    lam_a_blend = ((1 - config.W_FIFA) * lam_a_pool + config.W_FIFA * el_a) * factor_a
    lam_b_blend = ((1 - config.W_FIFA) * lam_b_pool + config.W_FIFA * el_b) * factor_b
```

`pipeline.predict_all`: calcular los factores una vez (`cargar_insumos` + `factor_bajas` por equipo, persistir `data/ajuste_bajas.csv`) y pasarlos por partido.

- [ ] **Step 4:** `pytest tests/test_bajas.py -v` → PASS. Revisar `data/ajuste_bajas.csv` a mano (equipos con convocatoria completa → factor 1.0). Golden: regenerar. (No es backtesteable sin histórico de bajas: la defensa es el cap + revisión manual.)

---

### Task 4.3: Loop en vivo del torneo (alta prioridad — necesario desde la jornada 1)  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** `actualizar_torneo.py` — `elo_update()` (K=60 + multiplicador de margen de eloratings) + main idempotente (`elo_aplicados.txt`): lee `resultados.csv`, actualiza `elo_2026.csv`, re-predice (cli+tournament). Flag `--solo-elo` para el cron (evita doble re-predicción). `extraer_resultados.py` **migrado al `SofaScoreClient`** (el marcador y `status.type` viajan en el HTML, verificado) → ahora funciona pese a Cloudflare. Enganchado a `actualizar.sh` (paso 1b). 4 tests de `elo_update` verdes; **ensayo en seco end-to-end OK** (ARG 3-0 ALG → Argentina 2113→2124, idempotente, re-predice, restaurado). Suite 70/70.

**Alcance:** funciona la actualización de **ELO/resultados** (lo que más pesa en 1X2). Incorporar **stats** del Mundial al pool sigue bloqueado (Cloudflare, Task 2.2/5.1) — el modelo aprende del torneo vía ELO, no vía patrones de juego.

---

#### Detalle original de la tarea

**Contexto:** `resultados.csv` existe (vacío) y hay crons de scraping. Falta el eslabón: incorporar los partidos del Mundial ya jugados al dataset, actualizar ELO y re-predecir los partidos restantes.

**Files:**
- Create: `actualizar_torneo.py`
- Modify: `predictor/config.py` (parámetros ELO de actualización)
- Test: `tests/test_actualizar_torneo.py` (la parte pura: update de ELO)

- [ ] **Step 1: Test del update de ELO (puro, sin IO)**

```python
from actualizar_torneo import elo_update

def test_elo_update_victoria_favorito():
    # España (2165) gana 2-0 a Curaçao (1436): cambio pequeño
    da, db = elo_update(2165, 1436, 2, 0)
    assert 0 < da < 8 and db == -da

def test_elo_update_sorpresa():
    # Curaçao gana 1-0 a España: cambio grande
    da, db = elo_update(1436, 2165, 1, 0)
    assert da > 45
```

- [ ] **Step 2: Implementación**

```python
"""Loop en vivo del Mundial: incorpora resultados jugados, actualiza ELO y
re-predice los partidos restantes.

Uso (tras cada jornada, o en cron diario):
    python actualizar_torneo.py

Pasos:
  1. Lee data/resultados.csv (partido_id del Mundial; score_a; score_b; finished).
  2. Para los terminados: actualiza data/elo_2026.csv (K=60, multiplicador de
     margen de eloratings) — idempotente vía data/elo_aplicados.txt.
  3. (Los stats por partido del Mundial entran por el scraper normal con los
     sofa_event_id de calendario.csv — extraer.py ya los recoge si se añaden
     los 48 equipos con fecha 2026-06-01; este script no scrapea.)
  4. Re-ejecuta el pipeline y la simulación de torneo.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

DATA = Path(__file__).parent / "data"
K_MUNDIAL = 60
APLICADOS = DATA / "elo_aplicados.txt"


def _margen(diff_goles: int) -> float:
    """Multiplicador de margen de eloratings.net."""
    d = abs(diff_goles)
    if d <= 1:
        return 1.0
    if d == 2:
        return 1.5
    return (11 + d) / 8


def elo_update(elo_a: float, elo_b: float, ga: int, gb: int,
               k: float = K_MUNDIAL) -> tuple[float, float]:
    we = 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))
    w = 1.0 if ga > gb else (0.5 if ga == gb else 0.0)
    delta = k * _margen(ga - gb) * (w - we)
    return delta, -delta


def main() -> None:
    # 1. resultados terminados aún no aplicados
    aplicados = set(APLICADOS.read_text().split()) if APLICADOS.exists() else set()
    resultados = []
    with (DATA / "resultados.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r.get("finished") in ("1", "True", "true") and r["partido_id"] not in aplicados:
                resultados.append(r)
    if not resultados:
        print("Sin resultados nuevos.")
        return

    # 2. equipos de cada partido (partidos_a_predecir) y ELO actual
    cruces = {}
    with (DATA / "partidos_a_predecir.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            cruces[r["partido_id"]] = (r["equipo_a"], r["equipo_b"])
    elo = {}
    with (DATA / "elo_2026.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            elo[r["equipo"]] = float(r["elo"])

    for r in resultados:
        a, b = cruces[r["partido_id"]]
        da, db = elo_update(elo[a], elo[b], int(r["score_a"]), int(r["score_b"]))
        elo[a] += da
        elo[b] += db
        print(f"{r['partido_id']}: {a} {r['score_a']}-{r['score_b']} {b} "
              f"(ELO {a} {da:+.1f}, {b} {db:+.1f})")
        aplicados.add(r["partido_id"])

    with (DATA / "elo_2026.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["equipo", "elo"], delimiter=";")
        w.writeheader()
        w.writerows({"equipo": e, "elo": round(v)} for e, v in
                    sorted(elo.items(), key=lambda kv: -kv[1]))
    APLICADOS.write_text("\n".join(sorted(aplicados)))

    # 3. re-predicción completa + torneo
    subprocess.run([sys.executable, "-m", "predictor.cli"], check=True)
    subprocess.run([sys.executable, "-m", "predictor.tournament"], check=True)
    print("Re-predicción OK. Recuerda: cd web && npm run db:seed")


if __name__ == "__main__":
    main()
```

Notas de integración:
- `config.ELO_2026` se carga del CSV (Task 0.4), así que la re-predicción usa el ELO actualizado sin tocar código.
- Los partidos del Mundial ya jugados entran a `stats_final.csv` por el scraper normal (añadir los 48 mundialistas con `fecha: 2026-06-01` a `equipos_maestros` cuando empiece el torneo) y con la recencia (Task 2.1) pesan mucho — el modelo "aprende" del propio Mundial.
- Para partidos ya jugados, el pipeline los sigue prediciendo (inofensivo); la web decide qué mostrar.

- [ ] **Step 3:** `pytest tests/test_actualizar_torneo.py -v` → PASS. Ensayo en seco: meter un resultado ficticio en `resultados.csv`, ejecutar, verificar ELO movido y predicciones regeneradas, **revertir el ficticio** (y `elo_aplicados.txt` + `elo_2026.csv`).
- [ ] **Step 4:** Añadir al cron existente (`generar_cron.py` / `deploy/generar_crontab.py`): `actualizar_torneo.py` diario a las 06:00 tras los scrapers de resultados.

---

## Fase 5 — Operación autónoma (que se gobierne solo durante el Mundial)

**Objetivo de la fase:** que el sistema no solo se actualice solo (eso ya lo hace `actualizar.sh` + cron), sino que (a) **aprenda** de los partidos del propio Mundial incorporándolos al histórico, y (b) **avise** cuando algo se rompa, en vez de fallar en silencio. Sin esto, el motor se queda congelado en el snapshot de mayo y un fallo de scraping pasa desapercibido durante días.

### Task 5.1: Incorporación incremental de los stats del Mundial al histórico  ⚠️ PARCIALMENTE BLOQUEADA (2026-06-13)

**Aviso:** mismo bloqueo que Task 2.2 — las stats de equipo por partido NO se obtienen vía HTML (solo por la API, caída por Cloudflare). Implicación durante el Mundial:
- ✅ **ELO/resultados en vivo (Task 4.3) funcionan** — el marcador SÍ está en el HTML.
- ❌ **Incorporar stats de partido al pool** queda bloqueado hasta resolver la fuente de stats (ver opciones en Task 2.2).
El `incorporar_stats_mundial.py` de abajo asume la API; reescribir cuando se decida la fuente.

**Contexto:** `actualizar.sh` baja el *marcador* de los partidos jugados (`extraer_resultados.py` → `resultados.csv`) pero **nunca añade sus estadísticas de equipo a `stats_final.csv`**. Por eso el pool de bootstrap sigue siendo 100% pre-Mundial: el modelo no "ve" cómo está jugando cada selección en el torneo. `extraer.py` re-scrapea el histórico completo por equipo (lento, horas) — no sirve para el cron. Hace falta un scraper **incremental por evento**: solo los partidos del Mundial ya jugados que aún no estén en `stats_final.csv`.

**Files:**
- Create: `incorporar_stats_mundial.py`
- Modify: `actualizar.sh` (añadir el paso antes de re-predecir)
- Test: `tests/test_incorporar_stats.py` (parte pura: parseo + dedup)

- [ ] **Step 1: Test de la lógica pura (sin red)**

```python
import pandas as pd
from incorporar_stats_mundial import filas_nuevas, parse_event_stats

def test_dedup_no_reescribe_existentes():
    existentes = pd.DataFrame({"partido_id": ["15186710"], "equipo_nombre": ["Mexico"]})
    candidatos = [
        {"partido_id": "15186710", "equipo_nombre": "Mexico"},   # ya está
        {"partido_id": "15186711", "equipo_nombre": "Spain"},    # nuevo
    ]
    nuevas = filas_nuevas(candidatos, existentes)
    assert len(nuevas) == 1 and nuevas[0]["partido_id"] == "15186711"

def test_parse_event_stats_extrae_metricas():
    # estructura SofaScore /event/{id}/statistics (grupos -> items)
    payload = {"statistics": [{"period": "ALL", "groups": [
        {"statisticsItems": [
            {"name": "Ball possession", "home": "55%", "away": "45%"},
            {"name": "Total shots", "home": "12", "away": "9"},
        ]}]}]}
    home, away = parse_event_stats(payload)
    assert home["ball_possession"] == 55.0 and home["total_shots"] == 12.0
    assert away["total_shots"] == 9.0
```

- [ ] **Step 2: Implementación**

```python
"""Incorpora INCREMENTALMENTE los stats de equipo de los partidos del Mundial
ya jugados a data/stats_final.csv (para que el pool de bootstrap los vea).

A diferencia de extraer.py (re-scrapea histórico por equipo, lento), este lee
data/calendario.csv, filtra a partidos ya jugados que NO estén en stats_final.csv
y baja /event/{id}/statistics de SofaScore para cada uno. Idempotente.

Uso: python incorporar_stats_mundial.py
"""
from __future__ import annotations

import asyncio
import csv
import json
import time
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STATS = DATA / "stats_final.csv"

# Mapeo nombre-de-stat SofaScore -> columna canónica de stats_final.csv.
MAP = {
    "Ball possession": "ball_possession", "Total shots": "total_shots",
    "Shots on target": "shots_on_target", "Corner kicks": "corner_kicks",
    "Fouls": "fouls", "Yellow cards": "yellow_cards", "Passes": "passes",
    "Offsides": "offsides", "Goalkeeper saves": "goalkeeper_saves",
    # … completar con el resto de METRICAS_EQUIPO al ver un payload real.
}


def _num(v: str) -> float | None:
    if v is None:
        return None
    s = str(v).replace("%", "").split("/")[0].split("(")[0].strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_event_stats(payload: dict) -> tuple[dict, dict]:
    """Devuelve (stats_home, stats_away) del periodo ALL."""
    home, away = {}, {}
    for blk in payload.get("statistics", []):
        if blk.get("period") != "ALL":
            continue
        for grupo in blk.get("groups", []):
            for it in grupo.get("statisticsItems", []):
                col = MAP.get(it.get("name"))
                if not col:
                    continue
                home[col] = _num(it.get("home"))
                away[col] = _num(it.get("away"))
    return home, away


def filas_nuevas(candidatos: list[dict], existentes: pd.DataFrame) -> list[dict]:
    ya = set(existentes["partido_id"].astype(str))
    return [c for c in candidatos if str(c["partido_id"]) not in ya]


def _calendario_jugados() -> list[dict]:
    ahora = time.time()
    out = []
    with open(DATA / "calendario.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            ko = int(r["kickoff"]) if r.get("kickoff") else 0
            if ko and ko + 2 * 3600 <= ahora:  # acabado (kickoff + 2h)
                out.append(r)
    return out


async def main() -> None:
    existentes = pd.read_csv(STATS, sep=";", encoding="utf-8-sig",
                             dtype=str, usecols=["partido_id"])
    jugados = _calendario_jugados()
    pendientes = [r for r in jugados
                  if str(r["sofa_event_id"]) not in set(existentes["partido_id"])]
    if not pendientes:
        print("Sin partidos nuevos del Mundial que incorporar.")
        return
    print(f"{len(pendientes)} partidos del Mundial a incorporar.")

    nuevas: list[dict] = []
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        pg = await (await b.new_context()).new_page()
        for r in pendientes:
            eid = r["sofa_event_id"]
            home, away = r["sofa"].split(" vs ") if " vs " in r.get("sofa", "") else ("", "")
            try:
                await pg.goto(f"https://api.sofascore.com/api/v1/event/{eid}/statistics",
                              wait_until="domcontentloaded")
                payload = json.loads(await pg.evaluate(
                    "()=>document.querySelector('pre')?.innerText ?? document.body.innerText"))
            except Exception as e:
                print(f"  [WARN] {eid}: {e}")
                continue
            sh, sa = parse_event_stats(payload)
            sh.update({"partido_id": eid, "equipo_nombre": home, "tipo_equipo": "home"})
            sa.update({"partido_id": eid, "equipo_nombre": away, "tipo_equipo": "away"})
            nuevas += [sh, sa]
            await asyncio.sleep(1.0)
        await b.close()

    nuevas = filas_nuevas(nuevas, existentes)
    if not nuevas:
        print("Nada nuevo tras dedup.")
        return
    df_full = pd.read_csv(STATS, sep=";", decimal=",", encoding="utf-8-sig", dtype=str)
    df_full = pd.concat([df_full, pd.DataFrame(nuevas)], ignore_index=True)
    df_full.to_csv(STATS, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    print(f"OK: +{len(nuevas)} filas en stats_final.csv")


if __name__ == "__main__":
    asyncio.run(main())
```

⚠ Entrada externa: el `MAP` está incompleto a propósito. Al ejecutarlo la primera vez sobre un partido real, volcar un payload de `/event/{id}/statistics` y completar el mapeo con las ~34 métricas de `config.METRICAS_EQUIPO`. Sin esto las columnas que falten quedarán NaN y se imputarán (degradado, pero no rompe).

- [ ] **Step 3: Enganchar a `actualizar.sh`**

Insertar como paso nuevo **antes** de "re-predecir":

```bash
echo "[$(date '+%Y-%m-%d %H:%M')] X/N incorporar stats del Mundial al histórico…"
.venv/bin/python incorporar_stats_mundial.py || echo "  (incorporar stats falló, se continúa)"
.venv/bin/python actualizar_torneo.py || echo "  (actualizar ELO falló, se continúa)"
```

(con la recencia de Task 2.1 activa, estos partidos recién incorporados —fecha de hoy— pesan mucho más que los amistosos de 2025; así el modelo "aprende" del torneo).

- [ ] **Step 4:** `pytest tests/test_incorporar_stats.py -v` → PASS. Ensayo en seco con un `sofa_event_id` real ya jugado (de una edición anterior si el Mundial no ha empezado), verificar que añade 2 filas con métricas pobladas, y **revertir** el cambio en `stats_final.csv`.

---

### Task 5.2: Observabilidad y alertas (que avise cuando se rompa)  ✅ HECHO (2026-06-13)

**Resultado de la ejecución:** decisión del usuario — canal **Telegram**, **una notificación por ejecución del cron** (con resumen). `notificar.py` (envío a Telegram vía env vars `MUNDIAL_TG_TOKEN`/`MUNDIAL_TG_CHAT`; sin credenciales imprime y no rompe). `run_actualizacion.py` orquesta los 9 pasos del cron, captura OK/fallo + última línea de cada uno (incluye vía API/HTML de `extraer_resultados`, que ahora la reporta), y manda el resumen (✅/⚠️). `actualizar.sh` reducido a wrapper que lo lanza. Validador de coherencia (0.6) integrado como paso. Setup de Telegram + aviso de IP-datacenter documentados en `deploy/DEPLOY.md`. Tests de formateo + validador, suite 79/79.

---

#### Detalle original de la tarea

**Contexto:** todo el auto-update depende de scrapear SofaScore con Playwright, y los pasos de `actualizar.sh` tragan errores (`|| echo "…falló, se continúa"`). Si SofaScore cambia la API, mete captcha o rate-limit, el pipeline se cae **en silencio** y la web sirve datos viejos sin que nadie se entere. Para "sin estar pendiente" hace falta un latido + alerta.

**Files:**
- Create: `monitor_salud.py`
- Modify: `actualizar.sh` (llamada final), `predictor/cli.py` (encadenar validador)
- Create: `data/salud.json` (estado del último run)
- Test: `tests/test_monitor_salud.py`

- [ ] **Step 1: Test de las reglas de salud (puras)**

```python
from monitor_salud import evaluar_salud

def test_alerta_si_resultados_viejos():
    estado = {"ultimo_resultado_epoch": 0, "ahora": 10 * 3600,
              "partidos_pendientes_hoy": 2, "validador_ok": True,
              "stats_incorporados": 0}
    alertas = evaluar_salud(estado)
    assert any("sin resultados" in a.lower() for a in alertas)

def test_alerta_si_validador_falla():
    estado = {"ultimo_resultado_epoch": 9 * 3600, "ahora": 10 * 3600,
              "partidos_pendientes_hoy": 0, "validador_ok": False,
              "stats_incorporados": 4}
    alertas = evaluar_salud(estado)
    assert any("coherencia" in a.lower() for a in alertas)

def test_todo_ok_sin_alertas():
    estado = {"ultimo_resultado_epoch": 9 * 3600, "ahora": 10 * 3600,
              "partidos_pendientes_hoy": 0, "validador_ok": True,
              "stats_incorporados": 4}
    assert evaluar_salud(estado) == []
```

- [ ] **Step 2: Implementación**

```python
"""Latido de salud del pipeline de auto-update. Lo llama actualizar.sh al final.

Evalúa señales (resultados frescos, validador de coherencia, incorporación de
stats) y, si algo está mal, manda UNA alerta (webhook configurable por env var
MUNDIAL_ALERT_WEBHOOK — Telegram/Slack/Discord). Sin webhook: solo imprime y
escribe data/salud.json (para que un uptime-check externo lo lea).
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
HORAS_SIN_RESULTADO_ALERTA = 6


def evaluar_salud(estado: dict) -> list[str]:
    alertas = []
    horas = (estado["ahora"] - estado["ultimo_resultado_epoch"]) / 3600
    if estado.get("partidos_pendientes_hoy", 0) > 0 and horas > HORAS_SIN_RESULTADO_ALERTA:
        alertas.append(
            f"Hay partidos hoy pero llevamos {horas:.0f}h sin resultados nuevos "
            "(¿scraper de SofaScore caído?).")
    if not estado.get("validador_ok", True):
        alertas.append("El validador de coherencia detectó predicciones rotas "
                       "(ver docs/violaciones). Revisar antes de confiar en la web.")
    return alertas


def _enviar(msg: str) -> None:
    url = os.environ.get("MUNDIAL_ALERT_WEBHOOK")
    if not url:
        print("[ALERTA, sin webhook]", msg)
        return
    try:
        data = json.dumps({"text": msg}).encode()
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[ALERTA no enviada: {e}]", msg)


def main() -> None:
    # Recoger señales del estado actual del repo
    import csv
    ultimo = 0
    rpath = DATA / "resultados.csv"
    if rpath.exists():
        # epoch del kickoff más reciente de un partido 'finished'
        cal = {}
        with open(DATA / "calendario.csv", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                cal[r["partido_id"]] = int(r["kickoff"]) if r.get("kickoff") else 0
        with open(rpath, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r.get("finished") in ("1", "True", "true"):
                    ultimo = max(ultimo, cal.get(r["partido_id"], 0))

    ahora = int(time.time())
    pendientes_hoy = 0
    with open(DATA / "calendario.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            ko = int(r["kickoff"]) if r.get("kickoff") else 0
            if 0 < ko - ahora < 86400:  # arranca en las próximas 24h
                pendientes_hoy += 1

    # validador de coherencia (Task 0.6)
    validador_ok = True
    try:
        import subprocess, sys
        r = subprocess.run([sys.executable, "-m", "predictor.validar_outputs"],
                           capture_output=True)
        validador_ok = r.returncode == 0
    except Exception:
        validador_ok = True  # no bloquear por el propio monitor

    estado = {"ultimo_resultado_epoch": ultimo, "ahora": ahora,
              "partidos_pendientes_hoy": pendientes_hoy,
              "validador_ok": validador_ok, "stats_incorporados": 0}
    alertas = evaluar_salud(estado)

    (DATA / "salud.json").write_text(json.dumps(
        {"ts": ahora, "ok": not alertas, "alertas": alertas, **estado}, indent=2))
    if alertas:
        _enviar("⚠️ Mundial predictor:\n" + "\n".join(f"• {a}" for a in alertas))
        print("\n".join(alertas))
    else:
        print("Salud OK ✔")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Enganchar**

- En `predictor/cli.py`, tras escribir las predicciones, llamar a `predictor.validar_outputs` (warning, no excepción) — ya previsto en Task 0.6.
- En `actualizar.sh`, como último paso: `.venv/bin/python monitor_salud.py || true`.
- Documentar en `deploy/DEPLOY.md` cómo configurar `MUNDIAL_ALERT_WEBHOOK` (un bot de Telegram es lo más simple: crear bot con @BotFather, usar la URL `https://api.telegram.org/bot<token>/sendMessage?chat_id=<id>&text=`… o un webhook de Slack/Discord).

- [ ] **Step 4:** `pytest tests/test_monitor_salud.py -v` → PASS. Ensayo: ejecutar `monitor_salud.py` sin webhook (imprime estado + escribe `salud.json`); luego con un webhook de prueba, forzar `validador_ok=False` y verificar que llega el mensaje.

---

## Fase 6 — Feedback de producto (añadido 2026-06-13)

Mejoras pedidas por el usuario tras revisar la web. Cada una se detallará a nivel de código al ejecutarla (flujo punto-por-punto).

### Task 6.1: Mercados de jugador con el motor real (port del bloque 7 del R)  ✅ HECHO (2026-06-13)

**Web conectada (2026-06-13):** `players.py` reescrito para generar los **35 mercados con los keys de `web/lib/player-markets.ts`** (anytime_scorer, assist, shots, passes, tackles…) desde el bootstrap, + columna `team`. `seed.ts` ahora **lee `predicciones_jugador_py.csv`** (motor real) en vez del Poisson naíf que calculaba; código muerto eliminado, tsc verde. `db:seed` carga **328.518 mercados de jugador**; spot-check DB OK (Amoura 0.37, Mahrez 0.24, Lautaro 0.18 — orden correcto). Pendientes parqueados: marca de confianza `n_apariciones` en la web, y mejoras-por-datos (xG vía FBref). Ver [[mundial-fuente-datos-alternativa]].

---

#### (resumen del motor)  ✅ MOTOR HECHO (2026-06-13)

**Hecho:** `predictor/players.py` — port del bloque 7 (pool 50% propio + 50% vs estilo-rival, bootstrap, split Bernoulli/round, ~14 mercados + primer goleador). **Mejora propia clave: minutos esperados** = minutos totales / partidos de su selección, **ponderados por tipo de partido** (amistoso 0.6) → distingue titular/suplente y evita asumir 80' para todos. Cap 0.90. 1.156 jugadores, 0 espurios, orden correcto (delanteros arriba). Integrado en `cli` (genera `predicciones_jugador_py.csv`); `predict_all` expone los lambdas. Columna `n_apariciones` de confianza.

**Mejoras probadas y DESCARTADAS (no viables, verificado):**
- xG/xA: 97% de datos faltantes en telemetría → hunde el promedio. Imputar es circular.
- Recencia + fuerza-del-rival: concentran un pool pequeño (10-30 filas) → ruido (rompían el orden). Desactivadas (flag `_DEBUG_PONDERAR=False`). Las técnicas del motor de equipo no trasladan a jugador.

**Parqueado (necesita datos):** las mejoras reales de jugador requieren una fuente alternativa con xG de selecciones (FBref) — mismo bloqueo que 2.2/5.1. Ver [[mundial-fuente-datos-alternativa]]. El modelo actual es lo mejor con los datos de hoy.

**Pendiente (independiente de datos):** conectar `web/prisma/seed.ts` al CSV del motor (en vez del Poisson naíf actual) — da valor ya.

---

#### Detalle original de la tarea

**Contexto (problema confirmado):** las probabilidades de jugador NO salen del motor. Las calcula `web/prisma/seed.ts` con un **Poisson naíf** sobre la media bruta del jugador (`1−e^−media` para binarios; Poisson PMF/CDF para O/U), **sin ajuste por rival, sin minutos esperados, sin bootstrap**. El bloque 7 del R (bootstrap por jugador: 50% sus partidos + 50% vs estilo-rival, escalado a minutos) **nunca se portó a Python**. Por eso "las probabilidades de jugador no están bien" y "faltan jugadores" (mapeo nombre↔selección + filtro de convocatoria).

**Enfoque:**
- Nuevo `predictor/players.py`: port del bloque 7 (pool por jugador, bootstrap, escala a 80', ajuste por rival vía estilo-KNN del rival del Mundial).
- Salida a `data/predicciones_jugador_py.csv` (mismo formato largo: jugador, mercado, evento, línea, prob).
- `web/prisma/seed.ts` deja de calcular Poisson y **consume el CSV**.
- Mapeo jugador↔selección robusto (acentos, alias) + cobertura de convocatorias (reportar jugadores sin datos).
- Mercados: anytime scorer, asistencia, gol+asist, tiros/SOT, pases clave, tackles, tarjeta, etc.

**Files:** Create `predictor/players.py`, `tests/test_players.py`; Modify `predictor/pipeline.py`/`cli.py` (generar el CSV), `web/prisma/seed.ts` (consumir en vez de calcular).

### Task 6.2: Árbitro → faltas y penaltis (ampliación de Task 4.1)  ✅ HECHO con 4.1 (2026-06-13)

**Contexto:** Task 4.1 solo contemplaba tarjetas. Los datos de `arbitros.csv` ya incluyen `poolFouls`, `poolPenalties`, `poolGoals`. El usuario quiere el efecto árbitro también en faltas (y, donde tenga sentido, penaltis).

**Enfoque:** extender `factor_arbitro()` para devolver factores por métrica (`yellow_cards`, `fouls`) y aplicarlos al escalar las sims correspondientes. Penaltis: incide en goles, con efecto pequeño y cap; evaluar con cuidado (no doble-contar). Cap por métrica.

### Task 6.3: Integración de cuotas de mercado (origen del feedback "bet365")

**Contexto:** no hay ninguna cuota en el sistema. Scrapear bet365 directo es inviable (anti-bot). Lo viable es una **API de odds** (The Odds API tiene free tier e incluye bet365 entre las casas).

**Doble valor:**
1. Mostrar la cuota junto a la probabilidad del modelo en la web.
2. **Comparar modelo vs mercado** → detectar value y, sobre todo, predicciones rotas (si el modelo discrepa 30 pts del mercado, bandera). Conecta con backtest (Fase 1) y validador (0.6).

**Enfoque:** `extraer_odds.py` (API de odds → `data/odds.csv`), tabla `Odds` en Prisma, seed la carga, la web muestra cuota+prob, y un check de divergencia modelo-mercado. **Además sirve para auditar el catálogo de mercados** (qué ofrece la casa que nosotros no) → alimenta Task 6.4.

### Task 6.4: Catálogo de líneas y mercados (feedback "que aparezcan todas las líneas")  🔶 PARCIAL (2026-06-13)

**Hecho (líneas O/U):** motor — `generar_lineas` amplía el rango (offsets −6..+8, antes −3..+5) y `markets` corta las líneas triviales (prob over fuera de [0.03, 0.97]) con `push_ou`; cada mercado tiene ahora ~15 líneas no triviales en vez de 9 (tiros MEX_RSA: 18.5→32.5). Web — `MarketOU.tsx` colapsable: por defecto **5 líneas centradas en la principal** (over≈50%, resaltada), botón **"Ver todas las líneas (N)"** que despliega el rango completo. Diseño elegido por el usuario. tsc OK, suite 66/66, golden regenerado.

**Pendiente (mercados nuevos):** hándicap (asiático/europeo), HT/FT combinado, margen de victoria, par/impar, intervalos de goles — depende de Task 6.3 (cuotas) para calcar el catálogo real de la casa antes de decidir cuáles añadir.

---

#### Detalle original de la tarea

**Contexto:** la web NO filtra líneas (muestra todas las del CSV). El límite está en `markets.generar_lineas()`: solo **9 líneas** (−2.5..+5.5 alrededor de la media), que se queda corto en mercados de media alta (tiros, pases). Mercados que probablemente faltan vs una casa: **hándicap (asiático/europeo), HT/FT combinado, margen de victoria, par/impar, intervalos de goles**.

**Enfoque (data-driven, idea del usuario):** primero Task 6.3 (cuotas) para ver el **catálogo real** que ofrece bet365; luego (a) ampliar el rango de `generar_lineas()` para cubrir lo que la casa ofrece sin inflar la BD de líneas inútiles, y (b) añadir los mercados que falten de la cola larga (Fase 2 original del R). Decidir el alcance con el catálogo delante, no a ciegas.

### Task 6.5: Enriquecer la pestaña de rendimiento

**Contexto:** la página `web/app/rendimiento/page.tsx` **funciona pero está vacía** (`resultados.csv` vacío porque el Mundial no ha empezado; y los scrapers de resultados estaban rotos por Cloudflare → Task 0.0 da la solución, falta migrarlos). Hoy solo muestra acierto 1X2/BTTS/O2.5 + Brier.

**Enfoque:** (a) el "se actualiza solo" lo resuelve el loop en vivo (Task 4.3) + migrar `extraer_resultados.py` al `SofaScoreClient`; (b) enriquecer la página: más mercados, calibración (reliability), tendencia temporal, y **modelo vs cuota de cierre** (con Task 6.3). 

### Task 6.7: Mejora general del portal/web (alcance por concretar)

**Contexto:** el usuario quiere una mejora general de la web, sin detallar todavía. Marcador consciente para no perder la intención; el alcance se define al llegar.

**Enfoque (a concretar con el usuario antes de ejecutar):** auditoría del portal cubriendo las dimensiones habituales — **diseño/UX** (jerarquía visual, consistencia, navegación), **claridad de datos** (cómo se presentan probabilidades, líneas, mercados; tooltips/metodología), **responsive/móvil**, **rendimiento** (carga, ISR, tamaño de payload), y **coherencia** entre páginas (predicciones, selecciones, jugadores, árbitros, grupos, rendimiento). Empezar con una pasada de revisión que liste hallazgos concretos y priorice, luego ejecutar por lotes. Depende en parte de las otras tasks de Fase 6 (jugadores 6.1, cuotas 6.3, rendimiento 6.5) que ya tocan contenido de la web.

**Files:** todo `web/` (a determinar tras la auditoría).

### Task 6.6: Subir N_SIM (ajuste final, no tarea propia)

**Contexto:** `N_SIM=20.000`. Subirlo reduce ruido MC (ayuda a marcador exacto y líneas extremas), coste lineal. Para 1X2 el efecto es marginal.

**Enfoque:** **solo tras calibrar (Fase 3) y con el backtest**, subir a ~50.000 midiendo coste y confirmando que reduce varianza sin mover el sesgo. Es cambiar una constante en `config.py`, no una tarea de desarrollo.

---

## Fuera de alcance (decidido el 2026-06-12)

- HFA/venue/altitud/clima (punto 8 de la revisión) — descartado por el usuario.
- Descanso y viajes (punto 9) — descartado.
- xG de fuente alternativa (punto 10) — descartado.
- Mercados de jugador (Fase 2 original del proyecto) — no entra en este plan.
- Cuotas de bookmaker — opcional, no bloqueante; si se quiere, The Odds API (tier gratuito) como monitor de desviaciones, en un task aparte.

## Self-review

- Cobertura: los 5 puntos priorizados de la revisión (purga, fecha+recencia, backtest, torneo, árbitros) tienen task propio (0.1, 0.2+2.1, 1.x, 3.5, 4.1). El punto 7 (bajas) es 4.2. ELO universal 2.4, calibración 3.1, shrinkage 3.2, KNN min 3.3, xG/QoO 3.4, en vivo 4.3.
- Dependencias: 2.1 requiere 0.2; 2.2 requiere 2.1; 3.1 requiere 1.2; 3.5 requiere `marcadores_py.csv` (ya se genera) y `cuadro_final.csv` (entrada manual); 4.3 requiere 0.4.
- Datos externos requeridos: cuadro FIFA (Task 3.5 Step 1) y verificación del formato TSV de eloratings (Task 2.4 Step 1) — ambos marcados explícitamente como entrada externa, no como TODO de código.
- Operación autónoma (Fase 5): cierra el eslabón que faltaba para que el modelo APRENDA del Mundial (5.1, stats del torneo → histórico) y para que AVISE cuando se rompa en vez de fallar en silencio (5.2, monitor + alertas). La fontanería de cron/scraping/seed/deploy ya existía (`actualizar.sh`, `generar_cron.py`, `deploy/`).
