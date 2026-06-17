# Plan de migración: SofaScore → fuentes múltiples

> Estado: PLAN (sin implementar). SofaScore está bloqueado (403 Cloudflare).
> Objetivo: recuperar todos los datos que el modelo usa desde fuentes gratuitas
> y fiables, con **dato real o vacío — nunca inventado**.

## Decisiones cerradas

- **xG**: xgscore.io. ESPN **NO** da xG de equipo (su `expectedGoals` es de portería:
  0.79/0.28 en un 3-1, verificado 2026-06-16). FotMob da xG por jugador/equipo como
  cross-check. xgscore verificado: 17 partidos, coherente (France 1.90 en un 3-1, Spain
  2.26 en un 0-0). No se paga.
- **big_chances**: FUERA de la migración inicial (el proxy por umbral de xG no es fiel a
  la definición de Opta). Se cae su mercado O/U. Reañadible después como mercado
  explícitamente etiquetado "(estimado, no Opta)".
- **Árbitros**: worldreferee.com (stats de carrera) + Wikipedia MediaWiki (designaciones)
  + reconstrucción de splits (casa/fuera, 1ª/2ª) desde eventos de ESPN.
- **Jugador (telemetría rica)**: FotMob `/api/data/matchDetails?matchId=` (verificado
  2026-06-16: HTTP 200 SIN token; da rating, pases, duelos, tackles, aéreos, despejes,
  recuperaciones, toques, pérdidas, balones largos, xG y shotmap por jugador — TODO lo de
  SofaScore y más). API-Football Free NO sirve para 2026 (solo 2022-2024). **Bios/valor**:
  Transfermarkt. Backup gratis: Flashscore (`flashscore.ninja`). Fallback de pago: BALLDONTLIE FIFA API.
  ⚠️ FRAGILIDAD: FotMob ya amuralló el endpoint hermano `/api/matchDetails` con `x-fm-req`;
  pueden hacer lo mismo a `/api/data/...`. Mitigación: IP residencial + fallback de token
  `x-fm-req` generado localmente (ver `@max-xoo/fotmob`). Riesgo acotado: el modelo de jugador
  está parqueado, si cae no rompe el pipeline de equipo.
- **Valor de mercado + pie**: Transfermarkt (self-host felipeall / `.us` / dump Kaggle).
- **CSV de salida sin cambios** → `dataset.py`, `pipeline.py`, modelo y seed Prisma intactos.
- **No borrar** `predictor/sofascore.py` ni la caché histórica: archivar como legacy.

## Fuentes vs datos

| Cliente nuevo (`predictor/sources/`) | Fuente | Acceso | Aporta |
|---|---|---|---|
| `espn.py` ✅ | site.api.espn.com `.../fifa.world/` | sin key, sin bloqueo | fixtures, resultados, stats equipo (18 métricas), eventos (tarjetas/goles con minuto+mitad), alineaciones, árbitro. NO xG de equipo |
| `fotmob.py` ✅ | fotmob.com `/api/data/matchDetails` | sin token (hoy); IP residencial recomendable | **telemetría rica de jugador** (rating, pases, duelos, tackles, aéreos, despejes, recuperaciones, toques, xG) + fixtures liga 77 (matchId) |
| ~~`apifootball.py`~~ | api-sports.io | ❌ Free no da season 2026 | DESCARTADO para 2026 (solo histórico ≤2024) |
| `worldreferee.py` | worldreferee.com | scraping (`searchReferees?q=` + URL guion_bajo) | stats carrera árbitro |
| `wikipedia_refs.py` | Wikipedia MediaWiki | API pública | designaciones del Mundial |
| `transfermarkt.py` | Transfermarkt | IP residencial / `.us` / dump Kaggle | valor de mercado + pie |
| `xgscore.py` ✅ | xgscore.io | scraping HTML | **fuente de xG de equipo por partido** (ESPN no lo da) |

## Datos que quedan VACÍOS (no inventados)

- **Sin impacto** (el modelo no los usa, "—" en inventario): free_kicks, throw-ins,
  goal_kicks, aerial_duels, ground_duels, dribbles, duels, dispossessed, recoveries,
  through_balls, touches_in_penalty_area, fouled_in_final_third; (jugador) touches,
  aerialWon/Lost, ballRecovery, totalClearance, wonTackle, possessionLostCtrl,
  conducciones/distancia, totalLongBalls.
- **Marginal** (features "raro con shrinkage", el modelo los lee pero pesan casi cero):
  goals_prevented, errors_lead_to_a_goal, errors_lead_to_a_shot, hit_woodwork,
  big_chances_scored, big_chances_missed.
- **Con consecuencia real**: big_chances → mercado eliminado.

## Reglas de consistencia (críticas)

1. **Una fuente por métrica, fija para todos los partidos** (no mezclar tiros de ESPN y
   de API-Football entre partidos).
2. **Capa de identidad robusta** (Fase 2): join por tablas de mapeo; fallar ruidosamente
   ante cualquier equipo/jugador/árbitro no mapeado (nunca join silencioso).
3. **xG en una sola escala**: adelante todo ESPN; el histórico de SofaScore o se re-baja
   de ESPN (si hay cobertura) o se **recalibra** a la escala de ESPN con un ajuste lineal
   sobre partidos presentes en ambas fuentes. No mezclar escalas en crudo.

## Observabilidad (transversal — IMPLEMENTADO en parte, 2026-06-16)

El cron reportaba ✅ aunque SofaScore estuviera bloqueado (los extractores tragaban
el bloqueo y salían con código 0). Arreglado:
- `notificar.py`: 3 estados — ✅ todo OK · ⚠️ degradado (fuente bloqueada / 0 datos
  nuevos) · ❌ fallo duro. El encabezado refleja el peor estado.
- `run_actualizacion.py`: clasifica cada paso por código de salida + patrones de bloqueo
  en la salida (red de seguridad); guarda log completo por ejecución en `logs/cron_<ts>.log`;
  alerta a Telegram aunque el orquestador reviente.

**Pendiente (durante la migración):** cada extractor NUEVO debe emitir la convención de
códigos de salida **0 = ok · 3 = degradado/bloqueo · otro = fallo duro** y loguear vía
`logging`. Cuando ESPN/FotMob/worldreferee fallen o devuelvan vacío, `sys.exit(3)` → el cron
lo marca ⚠️ sin depender de la heurística de patrones.

## Fases

### Fase 0 — Verificación (gates)
- 0.1 ✅ HECHO (2026-06-16): `APIFOOTBALL_KEY` válida, plan Free activo (100 req/día).
- 0.2 ❌ HECHO (2026-06-16): el plan Free NO accede a season 2026 (solo 2022-2024).
  API-Football Free queda DESCARTADO para datos del Mundial 2026. Resolver decisión de jugador.
- 0.3 `expectedGoals` de ESPN presente en todos los partidos del Mundial probados.
- 0.4 Vía de acceso a Transfermarkt operativa.
- 0.5 Medir cobertura histórica de xG en ESPN → decide re-bajar vs recalibrar (regla 3).

### Fase 1 — Clientes de fuente (`predictor/sources/`)
`base.py` (sesión, caché inmutable de partidos finalizados, throttle, retry) + los clientes.
- ✅ HECHO y probado con datos reales (2026-06-16): `base.py`, `espn.py` (France 3-1 Senegal),
  `fotmob.py` (telemetría Pedri + 104 fixtures liga 77), `xgscore.py` (17 partidos con xG).
- PENDIENTE: `worldreferee.py`, `wikipedia_refs.py`, `transfermarkt.py`.

### Fase 2 — Capa de identidad
- ✅ EQUIPOS (2026-06-16): `predictor/sources/identity.py` — `canonical(name)` mapea
  ESPN/xgscore/FotMob al canónico de `grupos_oficiales.csv` (48). Normaliza diacríticos +
  alias (Cape Verde→Cabo Verde, Czech→Czechia, Saudi A.→Saudi Arabia, Ivory Coast→Côte
  d'Ivoire, United States→USA, Turkey→Türkiye, etc.). Placeholders ("Group A Winner", "1A")
  → None. Resultado: el cruce de stats+xG pasó de 12/17 a **17/17**. Test: `test_sources_identity.py`.
- PENDIENTE: identidad de JUGADORES (FotMob id ↔ convocatorias) y ÁRBITROS (Wikipedia ↔ worldreferee).

### Fase 3 — Reescritura de extractores (mismo esquema CSV)
- ✅ STATS DE EQUIPO (2026-06-16): `extraer_stats_espn.py` (ESPN + xgscore + identity)
  produce filas con el esquema EXACTO de `stats_final.csv` (54 cols, sep ';', decimales
  coma, NA, exit 0/3/1). Validado: 17 partidos, 34 filas, 34/34 con xG, valores correctos
  (France 1.90/3-1). De momento escribe a `data/stats_espn_nuevos.csv` (scratch) — el append
  al pool histórico (cutover) es paso aparte. PENDIENTE: ventana incremental para el cron,
  esquema de `partido_id` (event-id ESPN) y dedup vs histórico.
- ✅ RESULTADOS (2026-06-17): `extraer_resultados_espn.py` + `fuente_partidos.py`
  (emparejado partido_id↔evento ESPN por par canónico, marcador orientado a equipo_a/b).
  Esquema idéntico (`partido_id;score_a;score_b;finished`), solo partidos iniciados, exit 0/3/1.
  Validado: 18 con marcador, 17 finalizados; cruce con el resultados.csv viejo = 6/6 marcadores
  idénticos (la única "diferencia" es ESPN más fresco en finished). Escribe a scratch
  `data/resultados_espn.csv`; cutover = cambiar OUT a `resultados.csv`.
- NOTA: `extraer_reparto_mitades` y `extraer_tarjetas` NO están en el cron (son builders
  OFFLINE del pool histórico). `reparto_mitades.csv` es un agregado global histórico que se
  reutiliza; desde ESPN solo se podrían repartir goles/tarjetas por mitad (no córners/faltas/tiros).
- 🟡 DESIGNACIONES (2026-06-17, parcial): cliente `predictor/sources/wikipedia_refs.py`
  (API MediaWiki, solo sección árbitros principales + columna "Matches assigned") +
  `extraer_designaciones_wiki.py` → calendario_wiki.csv (scratch). Validado: 11/12 coinciden
  con calendario actual. HALLAZGO: **ESPN `gameInfo.officials` es ground-truth del árbitro en
  partidos jugados** (CIV_ECU: ESPN="François Letexier" = correcto; el calendario actual tenía
  "Michael Oliver" MAL, y el parser wiki falló a "Stuart Burt"). DISEÑO REVISADO: designaciones =
  ESPN primario (jugados, con normalización de nombre vía arbitro_ids) + Wikipedia respaldo (futuros).
  ✅ IMPLEMENTADO en `extraer_designaciones_espn.py` (ESPN primario + Wikipedia respaldo, nombre
  normalizado vía arbitro_ids). Validado: CIV_ECU→"François Letexier"; 29/72 (18 ESPN + 11 wiki).
- ✅ ÁRBITROS carrera (2026-06-17): cliente `worldreferee.py` + `extraer_arbitros_wr.py` →
  arbitros_wr.csv (carrera worldreferee + *_pool del arbitro_pool.jsonl existente + sofa_id por nombre).
  ⚠️ LIMITACIONES a revisar: (a) cobertura ~37/51 (worldreferee no tiene 14 árbitros AFC/CAF/CONCACAF);
  (b) ESCALA: amarillas/partido más bajas que SofaScore (Marciniak 3.07 vs 4.27) → recalcular la media
  de referencia del modelo desde worldreferee para que el multiplicador ±20% sea consistente.
- PENDIENTE: cutover (escribir ficheros reales + actualizar PASOS del cron + exit-codes en extractores),
  reconstrucción del pool de árbitro desde eventos ESPN para 2026, offline `extraer_plantillas` (FotMob),
  `extraer_bios`.
Primero sin key (ESPN/worldreferee/Wikipedia/xgscore): `extraer_fechas`, `actualizar_fixtures`,
`extraer_resultados`, `extraer` (stats+xG), `extraer_reparto_mitades`, `extraer_tarjetas`,
`extraer_designaciones`, `extraer_arbitros` (carrera + pool reconstruido).
Luego con key (API-Football): `extraer_plantillas`, `extraer_bios`, `extraer_convocatorias`.

### Fase 4 — Scheduler / cron (revisar `generar_cron.py` + `actualizar.sh`)
- **General cada 6h**: fixtures, designaciones, árbitros-carrera, bios + red de seguridad.
- **Relativas a partido** (2.5h antes / 1h antes / 1h después / 2.5h después del kickoff)
  implementadas como **escalera de reintentos condicionada a `status==finished`**
  (resuelve prórrogas/penaltis y datos tardíos; no quema cuota de API-Football).
- Encadenar tras cada update: extractores → `pipeline.py` (modelo) → seed Prisma, para que
  **las predicciones se refresquen** en cada ciclo (confirmar que el cron actual lo hace).

### Fase 5 — Validación contra SofaScore (única, inicial)
`validar_migracion.py`: diff de valores (tiros, córners, tarjetas, posesión, xG) entre la
caché histórica de SofaScore y las fuentes nuevas. Garantía de "valores correctos". Tras el
cutover no hay más datos de SofaScore (bloqueado); la validación continua pasa a ESPN vs xgscore.

### Fase 6 — Cutover
Pipeline a datos nuevos; archivar `sofascore.py` como legacy (NO borrar); actualizar README/docs.

## Notas del repo
- Cuotas ya integradas: `predictor/odds_theoddsapi.py` + `theoddsapi.env` (The Odds API gratis,
  1X2 + O/U goles). Fuera del alcance de esta migración.
- `APIFOOTBALL_KEY` ya existe en `apifootball.env` pero ningún `.py` la usa aún.

## Revisión de correctitud (2026-06-17)

Revisión con revisor externo + verificación contra el loader real. Correcciones aplicadas y hallazgos:

**Corregido:**
- `extraer_stats_espn.py`: el CSV se escribía con comillas en números/NA y decimales con coma
  entrecomillados → el loader (`dataset._read_csv` dtype=str + `_to_numeric`) NO lo parseaba.
  Reescrito a formato byte-compatible con stats_final.csv (escritor manual: NA y números sin
  comillas, solo 3 columnas de texto entrecomilladas).
- `ball_possession`: ESPN la da decimal ("60,5") y `_to_numeric` no parsea coma → quedaba NaN.
  Ahora se REDONDEA a entero (como el histórico) → parsea 100%. (Regresión corregida.)
- `espn._num`: quita coma de millares (formato US) además del '%'.
- `base.fetch`: no duerme tras el último reintento.
- `fotmob`: `aerialLost` con `max(0, ...)`.
- `extraer_designaciones_espn`: exit 3 si no resolvió NINGUNA designación nueva (antes contaba
  las preexistentes del calendario de entrada).

**HALLAZGO PRE-EXISTENTE (decisión del usuario) — xG no se usa de verdad:**
`dataset._to_numeric` usa `pd.to_numeric` plano, que NO parsea decimales con coma. El xG histórico
("3,06") queda NaN (solo ~1% parsea) y luego se IMPUTA a la mediana. Es decir, **el pipeline actual
nunca usa el xG real, lo imputa**. Mi xG de xgscore (coma) se comporta igual (consistente, pero
también imputado). Para USAR el xG real habría que arreglar `_to_numeric` (1 línea:
`.str.replace(",", ".")` antes de `to_numeric`).
✅ APLICADO (2026-06-17, autorizado): `dataset._to_numeric` ahora normaliza coma→punto. Radio de
impacto medido = SOLO `expected_goals` (resto enteros, ya parseaban). Verificado por el loader
completo: xG real con 371 valores únicos (antes ~1 constante imputada), rango 0–8.1, present 48%
histórico/100% nuevo; los huecos genuinos se siguen imputando. **Cambia las salidas del modelo**
(ahora usa xG real). Tests 87/87.

**Verificado OK (no son bugs):**
- `partido_id` de stats = event-id ESPN: consistente con el histórico (que usa event-ids) y con el
  self-join de `_clean_stats`. Requisito: el futuro `extraer_fechas` debe usar el MISMO event-id ESPN.
- Orientación home/away de stats: el modelo keya por `equipo_nombre` (no equipo_a/b); `tipo_equipo`
  home/away coincide con el histórico.
- Esquemas de resultados/calendario/arbitros: coinciden con los reales.

**Robustez aceptada (documentada, no crítica):**
- `xgscore` regex y `wikipedia_refs` celdas[-2] son frágiles ante cambios de layout (fallarían a
  lista vacía / designación errónea). Mitigado: xgscore es secundaria; designaciones usa ESPN primario.
- Periodos de prórroga (period 3+) no se mapean a 1ª/2ª parte (solo afecta KO).

## xG: se mantiene la extracción, pero NON-CRÍTICA (2026-06-17)

El modelo NO usa `expected_goals` hoy (verificado: cero impacto en predicciones; no aparece en
strength/pool/markets/simulate; el motor usa goles+ELO y el pool de goles/córners/tarjetas/faltas/tiros).
Aun así SE MANTIENE la extracción de xG (xgscore) en la migración porque:
 - el modelo DEBERÍA usarlo (mejora futura validada por backtest; ataca la infra-dispersión);
 - para esa mejora el dato debe estar fluyendo ya (serie continua histórico+2026);
 - ya está construido y validado.
Tratamiento: **best-effort**. `extraer_stats_espn` NO degrada (exit 3) por falta de xG — solo por
equipo sin canónico (pérdida real). Cuando el modelo incorpore xG, re-escalar `sin_xg` a exit 3.
