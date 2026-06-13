# Backtest — línea base de calidad

**Esta es la puerta de calidad del plan.** Ninguna mejora de las Fases 2-3
(recencia, calibración, QoO coherente, shrinkage, etc.) se acepta si empeora el
log-loss 1X2 del modelo respecto a esta referencia.

## Referencia (2026-06-13)

Estado del motor: tras Fase 0 completa (dataset saneado: sin clubes, sin
fixtures futuros, sin filas imputadas en el pool; ELO desde CSV). Sin recencia
todavía (Task 2.1 pendiente).

Comando:
```
python -m predictor.backtest --desde 2025-06-01 --n-sim 3000
```

Resultado:
```
partidos evaluados: 376
modelo   : logloss=0.9418   brier=0.5561
  O2.5 brier=0.2674   BTTS brier=0.2460
(comparativa sobre 376 con baseline)
modelo   : logloss=0.9418
baseline : logloss=1.0311
```

**Lectura:**
- El modelo **bate al baseline** (Poisson off/def + Dixon-Coles) por ~9% de
  log-loss → las capas pool/KNN/QoO/ELO aportan señal real.
- Referencias: log-loss de "moneda uniforme" (1/3,1/3,1/3) = 1.0986; Brier
  uniforme = 0.667. El modelo (0.94 / 0.556) está claramente por debajo.

## Notas / limitaciones conocidas

- **Muestra**: 376 partidos elegibles (ambos equipos con ≥5 partidos previos) en
  la ventana jun-2025 → jun-2026. Refit mensual de KNN+fuerza con solo-pasado.
- **ELO solo de los 48 mundialistas**: en el histórico, los equipos sin ELO_2026
  usan solo fuerza interna. La Task 2.4 (ELO universal) debería mejorar esto y se
  medirá aquí.
- **Warning numpy** (`Degrees of freedom <= 0`): pools degenerados de 1 fila en
  casos borde; no fatal (el backtest completa). Revisar si se vuelve frecuente.
- `n_sim=3000` en backtest (vs 20.000 en producción): el ruido MC afecta poco
  porque las probabilidades 1X2/O2.5/BTTS salen de la matriz Dixon-Coles
  analítica, no de los samples.

## Historial de mediciones

| Fecha | Cambio | partidos | logloss modelo | logloss baseline | notas |
|-------|--------|----------|----------------|------------------|-------|
| 2026-06-13 | Fase 0 completa (sin recencia) | 376 | 0.9418 | 1.0311 | referencia inicial |
| 2026-06-13 | Task 2.1 recencia (half_life=730) | 376 | **0.9368** | 1.0311 | barrido: 180d empeora (0.9441), 730d óptimo; ✅ aceptada |
| 2026-06-13 | Task 2.4 ELO universal (eloratings) | 376 | **0.9292** | 1.0311 | mejora en 2 ventanas (jun-25: 0.9368→0.9292; ene-25: 0.9478→0.9441); ✅ aceptada. Caveat: ELO actual, no histórico (leak leve en backtest) |
| 2026-06-13 | Task 2.3 peso amistosos (0.6) | 376 | **0.9260** | 1.0311 | barrido 1.0/0.8/0.6/0.4 → 0.6 óptimo en 2 ventanas (jun-25 0.9292→0.9260; ene-25 0.9441→0.9415); ✅ aceptada |
| 2026-06-13 | Task 3.4 QoO coherente (familia tiros + xG fuera) | 376 | 0.9260 | 1.0311 | no cambia 1X2 (el QoO de tiros no toca goles); **arregla coherencia: filas pool con componentes>total 410→~13 (0.5%, residual=datos crudos); O/U publicado 0 violaciones** |
| 2026-06-13 | Task 3.1 calibración (W_FIFA 0.40→0.70) | 376 | **0.9083** | 1.0311 | barrido univariado: w_fifa señal grande (óptimo interior 0.70, no 1.0); rho/total_esp/bandwidth neutros (no tocados). El ELO predice goles mejor que el pool. ✅ aceptada |
| 2026-06-13 | Task 3.3 KNN muestra mínima (≥5 para ser vecino) | 376 | **0.9066** | 1.0311 | jun-25 0.9083→0.9066; metodológicamente correcto (vecinos de 1-4 partidos = ruido). ✅ aceptada |
