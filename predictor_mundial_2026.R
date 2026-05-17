###############################################################################
# Predictor probabilístico - Copa Mundial FIFA 2026 (USA/Canadá/México)
#
# Diseño:
#   - Venue neutral en todos los partidos (sin ventaja de campo / HFA).
#   - Las columnas tipo_equipo "home"/"away" se IGNORAN para predecir.
#   - xG fuera del vector de estilo del KNN (alta tasa de NaN); se mantiene
#     como métrica predicha donde existe.
#   - 58 jugadores tratados como titulares a 80' por defecto.
#
# Entrada (mismo directorio que el script):
#   - stats_final.csv         (equipo-partido, ;-separado, ,-decimal)
#   - telemetria_final.csv    (jugador-partido,  ; / ,)
#   - partidos_a_predecir.csv (lista de 72 partidos del Mundial, BOM UTF-8)
#
# Salida (mismo directorio):
#   - predicciones_largo.csv      formato largo, 1 fila por evento predicho
#   - predicciones_resumen.csv    formato ancho con los mercados clave
#   - debug_perfiles.csv          estadísticos por equipo y métrica
#   - debug_knn.csv               top-8 vecinos KNN por equipo del Mundial
#
# Ejecutar:
#   Rscript predictor_mundial_2026.R
###############################################################################

# ------------------------------- 0. Setup -----------------------------------
options(scipen = 999, stringsAsFactors = FALSE, warn = 1)

# Forzar locale UTF-8 si está disponible (Linux/macOS).
# En Windows R >= 4.2 ya usa UTF-8 nativo; el try() evita que falle.
invisible(try(Sys.setlocale("LC_ALL", "C.UTF-8"), silent = TRUE))
invisible(try(Sys.setlocale("LC_CTYPE", "C.UTF-8"), silent = TRUE))

# Auto-instalación de paquetes (silenciosa) si faltan
pkgs_necesarios <- c("data.table", "MASS", "FNN", "dplyr", "digest")
pkgs_faltan <- setdiff(pkgs_necesarios, rownames(installed.packages()))
if (length(pkgs_faltan) > 0) {
  message("Instalando paquetes faltantes: ", paste(pkgs_faltan, collapse = ", "))
  install.packages(pkgs_faltan,
                   repos = "https://cloud.r-project.org",
                   quiet = TRUE)
}
suppressPackageStartupMessages({
  library(data.table)
  library(MASS)
  library(FNN)
  library(dplyr)
  library(digest)
})

# Cronómetro global (para bloque de logging de regresión al final)
T0_GLOBAL <- Sys.time()

# Directorio de trabajo: donde está el script (o el CWD si no se detecta)
args <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("--file=", "", grep("--file=", args, value = TRUE))
if (length(file_arg) > 0 && nzchar(file_arg)) {
  WD <- normalizePath(dirname(file_arg), winslash = "/")
} else {
  WD <- normalizePath(getwd(), winslash = "/")
}
setwd(WD)
cat("Directorio de trabajo:", WD, "\n")

# Semilla reproducible (para Monte Carlo)
set.seed(20260611)

# Parámetros globales
# NOTA: los pesos α/β/γ del pool viven SOLO en la firma de `construir_pool()`
#       (defaults: alpha=0.30, beta=0.25, gamma=0.45). Esos son los valores
#       autoritativos. No definir constantes globales aquí — el script ya tuvo
#       en versiones previas ALPHA/BETA/GAMMA muertas que NO se pasaban a la
#       función y solo confundían al mantenedor.
K_KNN <- 8     # vecinos por equipo
N_SIM <- 20000 # simulaciones Monte Carlo por partido
MIN_TITULAR <- 80    # minutos asumidos para titulares (decisión: todos titulares)
SHRINK_PRIOR <- 0.05  # prior para shrinkage en tasas raras
SHRINK_N     <- 3     # equivalencia muestral del prior

# ------------------------ 1. Carga de datos --------------------------------
cat("\n[1] Cargando datos...\n")

stats <- fread("stats_final.csv", sep = ";", dec = ",", encoding = "UTF-8")
tel   <- fread("telemetria_final.csv", sep = ";", dec = ",", encoding = "UTF-8")
pred  <- fread("partidos_a_predecir.csv", sep = ";",
               encoding = "UTF-8")  # BOM-tolerant en data.table

# Limpiar nombre de la primera columna si quedó BOM
setnames(pred, names(pred)[1], "partido_id")

# Limpieza de nombres de equipo: quita BOM pegado, normaliza UTF-8, trim.
# Crítico: sin esto, "Curaçao", "Türkiye" y "Côte d'Ivoire" no matchean
# entre `pred` (con BOM) y `stats` (sin BOM) y rompen el KNN.
limpia_nombre <- function(x) {
  x <- as.character(x)
  x <- sub("^\xef\xbb\xbf", "", x, useBytes = TRUE)  # quita BOM al inicio
  x <- enc2utf8(x)                                    # normaliza encoding
  trimws(x)
}
for (col in c("equipo_a", "equipo_b")) {
  if (col %in% names(pred)) pred[, (col) := limpia_nombre(get(col))]
}
if ("equipo_nombre" %in% names(stats))
  stats[, equipo_nombre := limpia_nombre(equipo_nombre)]
for (col in c("home_team", "away_team")) {
  if (col %in% names(tel)) tel[, (col) := limpia_nombre(get(col))]
}

# Verificación crítica de encoding (escapes Unicode para robustez de locale)
stopifnot("Cura\u00e7ao"           %in% unique(stats$equipo_nombre))   # Curaçao
stopifnot("T\u00fcrkiye"           %in% unique(stats$equipo_nombre))   # Türkiye
stopifnot("C\u00f4te d\u0027Ivoire" %in% unique(stats$equipo_nombre))  # Côte d'Ivoire
cat("  Encoding OK: Curacao, Turkiye, Cote d'Ivoire reconocidos en stats.\n")

cat("  stats:        ", nrow(stats), "filas,", ncol(stats), "cols,",
    uniqueN(stats$equipo_nombre), "equipos,", uniqueN(stats$partido_id),
    "partidos\n")
cat("  telemetria:   ", nrow(tel), "filas,", ncol(tel), "cols,",
    uniqueN(tel$jugador), "jugadores\n")
cat("  partidos pred:", nrow(pred), "partidos a predecir\n")

# ----------------------- 2. Limpieza y derivaciones ------------------------
cat("\n[2] Limpieza y derivaciones...\n")

# 2.1 Imputar NA->0 en columnas de eventos raros (NA = "no ocurrió")
cols_raras <- c("red_cards", "penalty_saves", "goals_prevented",
                "errors_lead_to_a_goal", "errors_lead_to_a_shot",
                "big_chances_scored", "big_chances_missed", "through_balls",
                "punches", "big_saves", "high_claims", "hit_woodwork",
                "big_chances")
for (c in intersect(cols_raras, names(stats))) {
  stats[is.na(get(c)), (c) := 0]
}

# 2.2 Derivar oponente y goles_op mediante self-join por partido_id
op_dt <- stats[, .(partido_id, equipo_nombre, goles)]
setnames(op_dt, c("equipo_nombre", "goles"), c("oponente", "goles_op"))
stats <- merge(stats, op_dt, by = "partido_id", allow.cartesian = TRUE)
stats <- stats[equipo_nombre != oponente]  # cada equipo con el rival, no consigo

# 2.3 En telemetria: rellenar home/away faltantes desde stats (por partido_id)
home_away_map <- unique(stats[, .(partido_id,
                                  home = equipo_nombre[tipo_equipo == "home"][1],
                                  away = equipo_nombre[tipo_equipo == "away"][1]),
                              by = partido_id])
home_away_map <- unique(stats[tipo_equipo == "home",
                              .(partido_id, home_team_st = equipo_nombre)])
away_map      <- unique(stats[tipo_equipo == "away",
                              .(partido_id, away_team_st = equipo_nombre)])
tel <- merge(tel, home_away_map, by = "partido_id", all.x = TRUE)
tel <- merge(tel, away_map,      by = "partido_id", all.x = TRUE)
tel[is.na(home_team) | home_team == "", home_team := home_team_st]
tel[is.na(away_team) | away_team == "", away_team := away_team_st]
tel[, c("home_team_st", "away_team_st") := NULL]

# 2.4 NA->0 en telemetria para columnas raras (rojas, penaltis, errores)
cols_raras_tel <- c("penaltySave", "penaltyMiss", "penaltyConceded",
                    "penaltyWon", "penaltyFaced", "errorLeadToAGoal",
                    "errorLeadToAShot", "ownGoals", "goalsPrevented",
                    "penaltyShootoutGoal", "penaltyShootoutMiss",
                    "penaltyShootoutSave", "hitWoodwork",
                    "clearanceOffLine", "lastManTackle",
                    "crossNotClaimed", "bigChanceCreated",
                    "bigChanceMissed", "expectedGoals",
                    "expectedGoalsOnTarget", "expectedAssists")
for (c in intersect(cols_raras_tel, names(tel))) {
  tel[is.na(get(c)), (c) := 0]
}

# 2.5 Lista canónica de métricas de equipo a predecir
metricas_equipo <- c(
  # Goles y disparos
  "goles", "expected_goals", "total_shots", "shots_on_target",
  "shots_off_target", "shots_inside_box", "shots_outside_box",
  "blocked_shots",
  # Set pieces y reanudaciones
  "corner_kicks", "free_kicks", "throw-ins", "goal_kicks",
  # Disciplina
  "yellow_cards", "red_cards", "fouls", "offsides",
  # Defensa / posesión
  "tackles", "total_tackles", "interceptions", "passes",
  "accurate_passes", "ball_possession", "big_chances",
  "goalkeeper_saves", "aerial_duels", "ground_duels", "dribbles",
  "duels", "dispossessed", "recoveries", "clearances", "long_balls",
  "crosses"
)
metricas_equipo <- intersect(metricas_equipo, names(stats))

# Asegurar tipo numérico
for (c in metricas_equipo) {
  if (!is.numeric(stats[[c]])) stats[, (c) := as.numeric(get(c))]
}

cat("  Métricas de equipo a modelar:", length(metricas_equipo), "\n")

# 2.5b Forzar todas las métricas a numeric (algunas vienen como integer y
#      luego median() devuelve double, rompiendo group ops en data.table).
for (m in metricas_equipo) {
  if (!is.double(stats[[m]])) stats[, (m) := as.numeric(get(m))]
}

# 2.6 Imputar NAs en métricas con mediana DEL PROPIO EQUIPO (fallback global).
#     Necesario porque el bootstrap multivariado no tolera NAs en la matriz
#     simulada: si una fila tiene NA en una métrica, propagaría a sim.
cat("  Imputando NAs por mediana-de-equipo (fallback: mediana global)...\n")
mediana_global <- sapply(metricas_equipo,
                         function(c) median(stats[[c]], na.rm = TRUE))
for (m in metricas_equipo) {
  med_eq <- stats[, .(med = median(get(m), na.rm = TRUE)),
                  by = equipo_nombre]
  med_eq[is.na(med) | is.nan(med), med := mediana_global[m]]
  stats[med_eq, on = "equipo_nombre", med_temp := i.med]
  stats[is.na(get(m)), (m) := med_temp]
  stats[, med_temp := NULL]
}
nas_restantes <- sum(sapply(metricas_equipo,
                            function(c) sum(is.na(stats[[c]]))))
cat("  NAs restantes en métricas tras imputación:", nas_restantes, "\n")

# ------------------------ 3. Perfiles empíricos ----------------------------
cat("\n[3] Calculando perfiles empíricos por equipo (208 equipos)...\n")

moda_robusta <- function(x) {
  x <- x[!is.na(x)]
  if (length(x) == 0) return(NA_real_)
  ux <- unique(round(x, 4))
  ux[which.max(tabulate(match(x, ux)))]
}

# Distribución empírica por (equipo, métrica) en una lista anidada
distrib <- list()
for (eq in unique(stats$equipo_nombre)) {
  distrib[[eq]] <- list()
  sub <- stats[equipo_nombre == eq]
  for (m in metricas_equipo) {
    v <- sub[[m]]
    v <- v[!is.na(v)]
    distrib[[eq]][[m]] <- v
  }
}

# Tabla resumen (debug_perfiles)
resumen_rows <- list()
for (eq in unique(stats$equipo_nombre)) {
  for (m in metricas_equipo) {
    v <- distrib[[eq]][[m]]
    if (length(v) == 0) next
    resumen_rows[[length(resumen_rows) + 1L]] <- data.table(
      equipo = eq, metrica = m, n = length(v),
      media = mean(v), mediana = median(v),
      moda = moda_robusta(v),
      sd = if (length(v) > 1) sd(v) else 0,
      min = min(v), max = max(v)
    )
  }
}
debug_perfiles <- rbindlist(resumen_rows)

# ⚠ MEJORA FASE 4 (mercado de penalty): tasa histórica de penalty por
# equipo, agregada desde telemetría. penaltyWon = lanzador del equipo
# consiguió un penalty; penaltyConceded = jugador del equipo concedió
# uno al rival. Suma de ambos = "penalties involucrando al equipo".
# Auditoría: ~2% jugador-partidos con penaltyWon, ~0.3% con conceded.
# Tasa por partido típica: 5-15% dependiendo del equipo.
penalty_eq <- tel[, .(
  pen_won  = sum(penaltyWon, na.rm = TRUE),
  pen_conc = sum(penaltyConceded, na.rm = TRUE)
), by = .(equipo = ifelse(home_team == away_team, home_team,
                          ifelse(jugador %in% jugador,  # placeholder
                                 home_team, away_team)),
          partido_id)]
# Mejor: mapeo directo por equipo del jugador (ya en perfiles)
perf_map <- setNames(debug_perfiles$equipo, debug_perfiles$jugador)
tel[, equipo := perf_map[jugador]]
penalty_eq <- tel[!is.na(equipo), .(
  pen_won  = sum(penaltyWon, na.rm = TRUE),
  pen_conc = sum(penaltyConceded, na.rm = TRUE)
), by = .(equipo, partido_id)]
penalty_eq[, pen_total := pen_won + pen_conc]
penalty_rate_eq <- penalty_eq[, .(
  n_partidos = uniqueN(partido_id),
  tasa_pen   = mean(pen_total > 0)
), by = equipo]
penalty_rate_map <- setNames(penalty_rate_eq$tasa_pen, penalty_rate_eq$equipo)
cat(sprintf("  Tasa media penalty por partido (sobre %d equipos): %.3f\n",
            nrow(penalty_rate_eq), mean(penalty_rate_eq$tasa_pen)))

# ------------------------ 4. Vector de estilo y KNN ------------------------
cat("\n[4] Construyendo vector de estilo y KNN (K=", K_KNN, ")...\n", sep = "")

# Vector de estilo basado en RATIOS Y PROPORCIONES, no volúmenes absolutos.
# Justificación (refactor post-PCA): el vector previo mezclaba volúmenes
# (goles, shots, passes, tackles) con ratios. Los volúmenes dominaban la
# distancia euclidea, haciendo que el KNN agrupara por nivel de juego/
# cantidad de eventos en lugar de por estilo táctico. Síntoma: Brasil tenía
# de vecino a Ecuador, y KSA a Trinidad — semejantes en VOLUMEN pero no en
# ESTILO (Brasil es posesión-vertical-presión alta; Ecuador es bloque medio).
#
# Solución: solo ratios. La calidad/nivel ya se modela explícitamente por
# fuerza/ELO en otras partes del pipeline; aquí queremos identificar
# equipos con TENDENCIAS tácticas similares para nutrir el componente γ
# del pool (filas de "equipos estilo-X vs equipos estilo-Y").
estilo_agg <- stats[, .(
  n_partidos      = .N,
  # --- Producción ofensiva (proporciones, no volúmenes) ---
  shots_on_ratio  = sum(shots_on_target, na.rm = TRUE) /
                    pmax(1, sum(total_shots, na.rm = TRUE)),
  shots_box_ratio = sum(shots_inside_box, na.rm = TRUE) /
                    pmax(1, sum(total_shots, na.rm = TRUE)),
  shots_blocked_r = sum(blocked_shots, na.rm = TRUE) /
                    pmax(1, sum(total_shots, na.rm = TRUE)),
  conv_ratio      = sum(goles, na.rm = TRUE) /
                    pmax(1, sum(total_shots, na.rm = TRUE)),
  # --- Estilo de juego ---
  possession      = mean(ball_possession, na.rm = TRUE),
  pass_acc_ratio  = sum(accurate_passes, na.rm = TRUE) /
                    pmax(1, sum(passes, na.rm = TRUE)),
  long_balls_r    = sum(long_balls, na.rm = TRUE) /
                    pmax(1, sum(passes, na.rm = TRUE)),
  crosses_r       = sum(crosses, na.rm = TRUE) /
                    pmax(1, sum(passes, na.rm = TRUE)),
  through_r       = sum(through_balls, na.rm = TRUE) /
                    pmax(1, sum(passes, na.rm = TRUE)),
  final_third_r   = sum(final_third_entries, na.rm = TRUE) /
                    pmax(1, sum(passes, na.rm = TRUE)),
  # --- Duelos (ya eran ratios bien planteados) ---
  aerial_won_rat  = sum(aerial_duels, na.rm = TRUE) /
                    pmax(1, sum(duels, na.rm = TRUE)),
  ground_won_rat  = sum(ground_duels, na.rm = TRUE) /
                    pmax(1, sum(duels, na.rm = TRUE)),
  tackles_won_r   = sum(tackles_won, na.rm = TRUE) /
                    pmax(1, sum(total_tackles, na.rm = TRUE)),
  # --- Intensidad defensiva (ratios sobre touches/duels) ---
  # Fouls per duel ≈ propensión a faltas por contacto, no por cantidad de partido
  fouls_per_duel  = sum(fouls, na.rm = TRUE) /
                    pmax(1, sum(duels, na.rm = TRUE)),
  yellows_per_foul= sum(yellow_cards, na.rm = TRUE) /
                    pmax(1, sum(fouls, na.rm = TRUE)),
  # --- Productividad ofensiva (por remate, no en absoluto) ---
  corners_per_shot= sum(corner_kicks, na.rm = TRUE) /
                    pmax(1, sum(total_shots, na.rm = TRUE)),
  bigchance_ratio = sum(big_chances, na.rm = TRUE) /
                    pmax(1, sum(total_shots, na.rm = TRUE))
), by = equipo_nombre]

# Filas con NaN (equipos con un solo partido y todo NA) → imputar con la media global
features_estilo <- setdiff(names(estilo_agg),
                           c("equipo_nombre", "n_partidos"))
for (f in features_estilo) {
  m <- mean(estilo_agg[[f]], na.rm = TRUE)
  estilo_agg[is.na(get(f)) | is.nan(get(f)), (f) := m]
}

# Estandarizar (z-score)
mat <- as.matrix(estilo_agg[, ..features_estilo])
rownames(mat) <- estilo_agg$equipo_nombre
mat_z <- scale(mat)
mat_z[is.na(mat_z)] <- 0

# ⚠ MEJORA #9 (REVISION_CRITICA, Fase 3): PCA sobre el vector de estilo.
# Justificación: las features de estilo tienen alta colinealidad
# (`passes`↔`accurate_passes`↔`ball_possession`↔`final_third_entries`...).
# En un espacio de ~30 dimensiones con correlaciones 0.7-0.95 entre pares,
# la distancia euclidea da peso excesivo a "factores latentes" replicados.
# Reducir a 5 componentes (o el N que retenga ≥90% varianza) elimina la
# redundancia y debería producir KNN más coherentes: Brasil debería tener
# vecinos top-tier (Argentina, France, England), KSA debería tener vecinos
# asiáticos (Iraq, Jordan, Uzbekistan, Iran).
pca <- prcomp(mat_z, center = FALSE, scale. = FALSE)
var_exp <- cumsum(pca$sdev^2) / sum(pca$sdev^2)
k_pca <- max(5L, which(var_exp >= 0.90)[1])
cat(sprintf("  PCA: %d componentes retienen %.1f%% de varianza\n",
            k_pca, 100 * var_exp[k_pca]))
mat_z <- pca$x[, 1:k_pca, drop = FALSE]
rownames(mat_z) <- estilo_agg$equipo_nombre

# KNN: para cada equipo, vecinos más parecidos (excluyéndose a sí mismo)
knn_res <- get.knn(mat_z, k = K_KNN + 1)  # +1 porque el primero será él mismo
equipos_all <- rownames(mat_z)

equipos_mundial <- sort(unique(c(pred$equipo_a, pred$equipo_b)))
debug_knn_rows <- list()
vecinos_por_eq <- list()  # nombre_equipo -> data.table(vecino, dist, peso)

for (i in seq_along(equipos_all)) {
  eq <- equipos_all[i]
  idx <- knn_res$nn.index[i, ]
  dst <- knn_res$nn.dist[i, ]
  # Quitar self-match si aparece
  self_pos <- which(equipos_all[idx] == eq)
  if (length(self_pos) > 0) {
    idx <- idx[-self_pos]; dst <- dst[-self_pos]
  }
  idx <- head(idx, K_KNN); dst <- head(dst, K_KNN)
  vecinos <- equipos_all[idx]
  # Peso de similitud: exp(-dist) normalizado a suma 1
  pesos <- exp(-dst); pesos <- pesos / sum(pesos)
  vecinos_por_eq[[eq]] <- data.table(vecino = vecinos, dist = dst, peso = pesos)

  if (eq %in% equipos_mundial) {
    for (j in seq_along(vecinos)) {
      debug_knn_rows[[length(debug_knn_rows) + 1L]] <- data.table(
        equipo = eq, rank = j, vecino = vecinos[j],
        distancia = round(dst[j], 4), peso = round(pesos[j], 4)
      )
    }
  }
}
debug_knn <- rbindlist(debug_knn_rows)

cat("  KNN construido para", length(equipos_all), "equipos.\n")
cat("  Equipos del Mundial:", length(equipos_mundial), "\n")

# --------------- 4b. Fuerza por equipo (interna + FIFA) -------------------
# Necesario para reponderar el pool: filas con diferencial de fuerza muy
# distinto al target reciben menos peso. Sin esto, KNN por estilo solo
# infla equipos débiles cuando comparten estilo con grandes.
cat("\n[4b] Calculando fuerzas (interna + FIFA) por equipo...\n")

# Fuerza interna: OFF (goles por partido) - DEF (goles_op por partido)
# Con shrinkage por nº de partidos (clubes con 1-2 partidos no contaminan).
fuerza_interna <- stats[, .(
  n_partidos = .N,
  off_rate = mean(goles,    na.rm = TRUE),
  def_rate = mean(goles_op, na.rm = TRUE)
), by = equipo_nombre]
# Shrinkage Bayesiano simple: tiende a 0 para n bajo
fuerza_interna[, raw := off_rate - def_rate]
# media global como prior
prior <- mean(fuerza_interna$raw, na.rm = TRUE)
fuerza_interna[, raw_shrunk := (raw * n_partidos + prior * 5) /
                               (n_partidos + 5)]
fuerza_interna[, z_interna := (raw_shrunk - mean(raw_shrunk, na.rm = TRUE)) /
                              sd(raw_shrunk, na.rm = TRUE)]

# ⚠ MEJORA #5 (REVISION_CRITICA, Fase 2 adelantada a Fase 1).
# ELO de eloratings.net (snapshot 14 mayo 2026) reemplaza al ranking FIFA.
# El ELO rompe la circularidad de fuerza_map: a diferencia de z_interna
# (que infla a equipos como Morocco por sus AFCON contra rivales débiles)
# y del ranking FIFA (saturado en top-10, actualización lenta), el ELO se
# ajusta partido a partido con diferencia de goles y refleja skill absoluto.
# Esto desbloquea el contrato de la mejora #2 (QoO) — la coordenada de
# fuerza_oponente deja de estar sesgada por el propio rendimiento del equipo.
#
# Lista: 48 selecciones del Mundial 2026, valores ELO directos (no rank).
# Nombres mapeados al canon del dataset:
#   eloratings "Ivory Coast"  → dataset "Côte d'Ivoire"
#   eloratings "Cape Verde"   → dataset "Cabo Verde"
#   eloratings "Bosnia and Herzegovina" → dataset "Bosnia & Herzegovina"
#   eloratings "Turkey"       → dataset "Türkiye"
#   eloratings "United States"→ dataset "USA"
elo_2026 <- c(
  "Spain" = 2165, "Argentina" = 2113, "France" = 2081, "England" = 2020,
  "Brazil" = 1984, "Portugal" = 1984, "Colombia" = 1975, "Netherlands" = 1961,
  "Ecuador" = 1933, "Croatia" = 1930, "Germany" = 1923, "Norway" = 1912,
  "Japan" = 1904, "T\u00fcrkiye" = 1902, "Uruguay" = 1892, "Switzerland" = 1889,
  "Senegal" = 1878, "Belgium" = 1866, "Mexico" = 1858, "Paraguay" = 1833,
  "Austria" = 1827, "Morocco" = 1821, "Canada" = 1784, "Australia" = 1783,
  "Scotland" = 1767, "Iran" = 1760, "South Korea" = 1752, "Algeria" = 1743,
  "Panama" = 1737, "Uzbekistan" = 1727, "Czechia" = 1726, "USA" = 1721,
  "Sweden" = 1719, "Jordan" = 1690, "Egypt" = 1689,
  "C\u00f4te d\u0027Ivoire" = 1676, "DR Congo" = 1655, "Tunisia" = 1636,
  "Iraq" = 1607, "Bosnia & Herzegovina" = 1594, "New Zealand" = 1585,
  "Saudi Arabia" = 1568, "Cabo Verde" = 1549, "Haiti" = 1532,
  "South Africa" = 1524, "Ghana" = 1505, "Cura\u00e7ao" = 1436, "Qatar" = 1425
)
names(elo_2026) <- enc2utf8(names(elo_2026))
stopifnot(length(elo_2026) == 48L)
# Alias retro-compatibilidad: ranking_fifa era el dict que get_rank() usaba
# antes de la mejora #5. Lo dejamos vacío para que cualquier código antiguo
# que aún lo referencie devuelva NA y se note inmediatamente. Ya no existe
# get_rank() — usar get_elo() para obtener el ELO de un equipo.
ranking_fifa <- integer(0)

# z_elo: estandarizado sobre los 48 equipos del Mundial (más estable que
# sobre un conjunto mezclado de clubes/sub-naciones del dataset).
mundial_con_elo <- intersect(equipos_mundial, names(elo_2026))
mu_elo <- mean(elo_2026[mundial_con_elo])
sd_elo <- sd(elo_2026[mundial_con_elo])

fuerza_interna[, z_elo := NA_real_]
for (eq in mundial_con_elo) {
  fuerza_interna[equipo_nombre == eq,
                 z_elo := (elo_2026[eq] - mu_elo) / sd_elo]
}

# Fuerza final: 50/50 si ambos disponibles; solo z_interna en caso contrario.
fuerza_interna[, fuerza := ifelse(is.na(z_elo),
                                  z_interna,
                                  0.5 * z_interna + 0.5 * z_elo)]

# Sanity check: las 12 fuerzas más altas filtradas sólo a equipos del
# Mundial deberían ser top selecciones reconocibles.
cat("  Top 12 por fuerza (filtrado a equipos del Mundial):\n")
print(fuerza_interna[equipo_nombre %in% equipos_mundial][order(-fuerza)][1:12,
       .(equipo_nombre, n = n_partidos,
         z_interna = round(z_interna, 2),
         z_elo = round(z_elo, 2),
         fuerza = round(fuerza, 2))])
cat("  Fondo (3 más débiles del Mundial):\n")
print(fuerza_interna[equipo_nombre %in% equipos_mundial][order(fuerza)][1:3,
       .(equipo_nombre, n = n_partidos,
         z_interna = round(z_interna, 2),
         z_elo = round(z_elo, 2),
         fuerza = round(fuerza, 2))])

# Mapeo nombre -> fuerza (lookup rápido para reweight)
fuerza_map <- setNames(fuerza_interna$fuerza, fuerza_interna$equipo_nombre)

mundial_sin_elo <- setdiff(equipos_mundial, mundial_con_elo)
if (length(mundial_sin_elo) > 0) {
  cat("  AVISO equipos Mundial sin ELO (usan sólo z_interna):",
      paste(mundial_sin_elo, collapse = ", "), "\n")
} else {
  cat("  Los 48 equipos del Mundial tienen ELO asignado.\n")
}


###############################################################################
# BLOQUE 5: pool bootstrap multivariado + simulación MC
# Sustituye el modelado independiente por métrica.
###############################################################################

# --------------------- 5.1 Construcción del pool por equipo ----------------
# Para predecir el equipo `propio` jugando contra `rival`, montamos un único
# data.table cuyas filas son partidos REALES con todas las métricas a la vez,
# cada fila con un peso de muestreo que codifica α + β + γ:
#
#   α: filas de partidos de `propio`. Peso uniforme dentro del componente.
#   β: filas de `propio` cuando se enfrentó a rivales en KNN-de-`rival`,
#      ponderadas por similitud(oponente_real, rival).
#   γ: filas de equipos en KNN-de-`propio` cuando se enfrentaron a rivales
#      en KNN-de-`rival`. Peso compuesto: sim(equipo, propio) × sim(opon, rival).
#      Ojo metodológico: las filas γ son de equipos parecidos a `propio`
#      (no del rival), porque queremos un pool COHERENTE de "filas de
#      equipos estilo-propio vs equipos estilo-rival". Así el bootstrap
#      preserva correlaciones internas del estilo-propio.
#
# Si algún componente está vacío para un partido concreto, redistribuimos
# su masa entre los presentes.
#
# MEJORA #8 (REVISION_CRITICA, Fase 3) NO APLICADA: peso de recencia vía
# partido_id. El protocolo de la revisión exige validar correlación
# partido_id↔fecha_real ≥ 0.9 antes de aplicar el half-life. Pero
# stats_final.csv NO tiene columna de fecha, así que la correlación es
# imposible de validar y la mejora se salta tal como prescribe el plan.
# Si en futuras revisiones del dataset se incorpora `fecha`, reabrir #8.

construir_pool <- function(propio, rival, stats_dt, vecinos_por_eq,
                           fuerza_map, bandwidth = 0.6,
                           alpha = 0.30, beta = 0.25, gamma = 0.45,
                           masa_threshold = 0.05) {

  vec_propio_dt <- vecinos_por_eq[[propio]]
  vec_rival_dt  <- vecinos_por_eq[[rival]]
  w_vec_rival  <- setNames(vec_rival_dt$peso,  vec_rival_dt$vecino)
  w_vec_propio <- setNames(vec_propio_dt$peso, vec_propio_dt$vecino)

  # Diferencial de fuerza objetivo (z-score units)
  f_prop <- fuerza_map[propio]; if (is.na(f_prop)) f_prop <- 0
  f_riv  <- fuerza_map[rival];  if (is.na(f_riv))  f_riv  <- 0
  fuerza_diff_TARGET <- f_prop - f_riv

  prox_fuerza_vec <- function(team_vec, opp_vec) {
    f_t <- fuerza_map[team_vec]; f_t[is.na(f_t)] <- 0
    f_o <- fuerza_map[opp_vec];  f_o[is.na(f_o)] <- 0
    diff_pool <- f_t - f_o
    exp(-((fuerza_diff_TARGET - diff_pool)^2) / (2 * bandwidth^2))
  }

  # Estrategia: pesos globales α/β/γ FIJOS (para componentes con masa
  # bruta de proximidad > threshold). Dentro de cada componente, las
  # filas se ponderan por proximidad. Si un componente queda por debajo
  # del threshold, su peso se redistribuye entre los presentes.
  # Esto garantiza que γ contribuya siempre que existan vecinos válidos,
  # incluso si α tiene muchas filas; γ aporta la perspectiva comparativa
  # internacional que de otro modo quedaría aplastada por la masa de α.

  rows_a <- stats_dt[equipo_nombre == propio]
  if (nrow(rows_a) > 0) {
    rows_a[, peso_raw := prox_fuerza_vec(equipo_nombre, oponente)]
    rows_a[, componente := "alpha"]
  }
  rows_b <- stats_dt[equipo_nombre == propio &
                     oponente %in% names(w_vec_rival)]
  if (nrow(rows_b) > 0) {
    rows_b[, w_sim  := w_vec_rival[oponente]]
    rows_b[, w_prox := prox_fuerza_vec(equipo_nombre, oponente)]
    rows_b[, peso_raw := w_sim * w_prox]
    rows_b[, c("w_sim", "w_prox") := NULL]
    rows_b[, componente := "beta"]
  }
  rows_g <- stats_dt[equipo_nombre %in% names(w_vec_propio) &
                     oponente      %in% names(w_vec_rival) &
                     equipo_nombre != propio]
  if (nrow(rows_g) > 0) {
    rows_g[, w_eq   := w_vec_propio[equipo_nombre]]
    rows_g[, w_op   := w_vec_rival[oponente]]
    rows_g[, w_prox := prox_fuerza_vec(equipo_nombre, oponente)]
    rows_g[, peso_raw := w_eq * w_op * w_prox]
    rows_g[, c("w_eq", "w_op", "w_prox") := NULL]
    rows_g[, componente := "gamma"]
  }

  masa_a <- if (nrow(rows_a) > 0) sum(rows_a$peso_raw, na.rm=TRUE) else 0
  masa_b <- if (nrow(rows_b) > 0) sum(rows_b$peso_raw, na.rm=TRUE) else 0
  masa_g <- if (nrow(rows_g) > 0) sum(rows_g$peso_raw, na.rm=TRUE) else 0

  presente <- c(alpha = masa_a > masa_threshold,
                beta  = masa_b > masa_threshold,
                gamma = masa_g > masa_threshold)
  pesos_globales <- c(alpha = alpha, beta = beta, gamma = gamma) * presente
  if (sum(pesos_globales) == 0) {
    # Ningún componente tiene afinidad: cae a α uniforme
    if (nrow(rows_a) > 0) {
      rows_a[, peso := 1 / .N][, peso_raw := NULL]
      return(rows_a)
    }
    return(NULL)
  }
  pesos_globales <- pesos_globales / sum(pesos_globales)

  if (nrow(rows_a) > 0 && presente["alpha"]) {
    rows_a[, peso := (peso_raw / masa_a) * pesos_globales["alpha"]]
    rows_a[, peso_raw := NULL]
  } else if (nrow(rows_a) > 0) {
    rows_a[, peso := 0][, peso_raw := NULL]
  }
  if (nrow(rows_b) > 0 && presente["beta"]) {
    rows_b[, peso := (peso_raw / masa_b) * pesos_globales["beta"]]
    rows_b[, peso_raw := NULL]
  } else if (nrow(rows_b) > 0) {
    rows_b[, peso := 0][, peso_raw := NULL]
  }
  if (nrow(rows_g) > 0 && presente["gamma"]) {
    rows_g[, peso := (peso_raw / masa_g) * pesos_globales["gamma"]]
    rows_g[, peso_raw := NULL]
  } else if (nrow(rows_g) > 0) {
    rows_g[, peso := 0][, peso_raw := NULL]
  }

  pool <- rbindlist(list(rows_a, rows_b, rows_g), fill = TRUE)
  pool <- pool[peso > 0]
  if (nrow(pool) == 0) return(NULL)
  pool[, peso := peso / sum(peso)]
  pool
}

# --------------------- 5.2 Tasas con shrinkage para eventos raros ----------
# Para columnas como red_cards, big_chances_missed, penalty_saves,
# errors_lead_to_a_goal, hit_woodwork, errors_lead_to_a_shot,
# goals_prevented: tasa pool con shrinkage hacia la media global.
#
# shrunk_rate = (pool_mean * 1 + global_mean * 0.5) / (1 + 0.5)
# Equivalente a un prior con masa muestral 0.5 (suave).

cols_raras_shrink <- c("red_cards", "big_chances_missed",
                       "penalty_saves", "errors_lead_to_a_goal",
                       "errors_lead_to_a_shot", "hit_woodwork",
                       "goals_prevented")
cols_raras_shrink <- intersect(cols_raras_shrink, metricas_equipo)

# Media global de cada columna rara (para el prior)
media_global_raras <- sapply(cols_raras_shrink, function(c) {
  mean(stats[[c]], na.rm = TRUE)
})

tasa_shrunk <- function(pool, col, masa_prior = 0.5) {
  v <- pool[[col]]
  w <- pool$peso
  ok <- !is.na(v)
  v <- v[ok]; w <- w[ok]
  if (length(v) == 0) return(media_global_raras[col])
  pool_mean <- sum(v * w) / sum(w)
  prior_mean <- media_global_raras[col]
  (pool_mean * 1 + prior_mean * masa_prior) / (1 + masa_prior)
}

# --------------------- 5.3 Simulación MC del partido -----------------------
# Bootstrap multivariado. Para cada partido pred:
#   1. Construir pool_A y pool_B.
#   2. Sortear N índices con reemplazo en cada pool (prob = peso).
#   3. Extraer matrices sim_A y sim_B (N × n_metricas).
#   4. Para eventos raros con tasa muy baja, sobrescribir con Poisson(rate
#      shrunk) en lugar del bootstrap (más estable, menos 0s pegados).
#   5. Devolver listas sim_A, sim_B listas para calcular mercados.

# --- Fix 3: prior Poisson basado en ranking FIFA, SOLO para goles. ---------
# El bootstrap reproduce excelentemente correlaciones de córners, tarjetas,
# faltas y tiros, pero los goles admiten una predicción a priori basada en
# ranking FIFA que el pool no puede generar cuando un equipo nunca jugó
# contra un rival del estilo target (caso ARG vs AUT: sin precedentes
# análogos en el dataset). Mezclamos λ_pool con λ_elo solo para goles.
# Nombre histórico W_FIFA conservado por retrocompatibilidad de comentarios;
# ahora alimentado por ratings ELO (mejora #5).
W_FIFA <- 0.40   # peso fijo: 0.40 ELO + 0.60 pool (NO TUNEAR)

# ELO "efectivo" para equipos sin entrada en elo_2026 (no debería pasar tras
# el bloque 4b para equipos del Mundial; sí pasa para vecinos del KNN que no
# están en el Mundial — esos casos solo afectan al pool, no a elo_lambdas
# que ya solo se llama con eA/eB del Mundial). 1400 = ELO típico de fútbol
# "promedio mundial" (cuartil bajo de los 48 del Mundial).
get_elo <- function(equipo) {
  e <- elo_2026[equipo]
  if (is.na(e)) return(1400)
  unname(e)
}

# elo_lambdas: λ_A, λ_B basados en diferencia ELO real (mejora #5).
# Fórmula Maher 1982 / De Boer 2018: 100 pts ELO ≈ 0.3 goles de ventaja en
# venue neutral. Sustituye la fórmula rank_diff/30 que infravaloraba la
# distancia entre selecciones top y reducía el efecto en partidos como
# MAR_BRA (rank 8 vs rank 6 daba diff goles 0.07 — despreciable;
# ELO 1821 vs 1984 da diff goles 0.49 — significativo).
elo_lambdas <- function(elo_a, elo_b, total_esperado = 2.55) {
  elo_diff <- elo_a - elo_b   # positivo si A es más fuerte
  goal_diff_esperada <- elo_diff / 100 * 0.3
  half <- total_esperado / 2
  list(
    lambda_a = max(0.25, half + goal_diff_esperada / 2),
    lambda_b = max(0.25, half - goal_diff_esperada / 2)
  )
}

# ⚠ MEJORA #2 (REVISION_CRITICA, Fase 1): quality-of-opposition adjustment.
# Cada fila del pool representa un partido REAL del equipo (o de su vecino)
# contra un oponente concreto. Sin ajuste, la μ del bootstrap es el promedio
# crudo de esos partidos — lo que castiga a equipos cuya muestra histórica
# está contra rivales fuertes (Brasil vs CONMEBOL → μ_goles=1.50) y premia a
# equipos cuya muestra está contra rivales débiles (KSA vs AFC qualifiers).
# Resultado documentado: MAR_BRA invertido (modelo 41/25/34 vs mercado 19/26/55).
#
# Cómo: residualización ponderada vía lm + CAP del shift al ±cap_pct (35%)
# de la media observada del equipo en esa métrica. El cap es defensa contra
# extrapolaciones absurdas cuando la pendiente del lm está sobreajustada
# (Bélgica: pendiente -4.89 córners/unidad-z producía 12.3 córners vs NZ,
# fuera de cualquier rango realista). En la práctica solo ~1% de los ~576
# ajustes posibles tocan el cap — es defensa, no recorte sistemático.
#
# LIMITACIÓN CONOCIDA: el ajuste usa `fuerza_map = 0.5*z_interna + 0.5*z_fifa`
# como coordenada del rival, lo que es circular para equipos con z_interna
# distorsionada (Morocco infla en AFCON, KSA hunde en partidos vs top-tier).
# Caso síntoma: en MAR_BRA fuerza_map[Morocco]=1.50 > fuerza_map[Brazil]=0.87,
# y el ajuste no consigue invertir el partido al rango de mercado (19/26/55).
# Esta limitación se resuelve en Fase 2 con la mejora #5 (ELO específico de
# fútbol vía eloratings.net), que reemplaza la coordenada de fuerza por una
# que NO depende del rendimiento ofensivo del equipo (los ELO se ajustan por
# diferencia de goles pero la dimensión que importa para el QoO es la
# diferencia de skill, ortogonal a "metió muchos vs débil").
#
# Métricas a ajustar: solo aquellas sensibles al rival (goles, tiros, córners,
# xG). NO se ajustan métricas de estilo intrínsecas al equipo (faltas, tackles,
# recoveries, free_kicks, throw-ins, amarillas) — son ortogonales al nivel del
# rival y ajustarlas introduciría ruido.
ajustar_pool_por_calidad_rival <- function(pool, f_rival_target,
                                            fuerza_map_,
                                            metricas_ajustar,
                                            etiqueta = "",
                                            cap_pct = 0.35) {
  if (is.null(pool) || nrow(pool) < 5) return(pool)
  pool <- copy(pool)
  pool[, f_oponente := fuerza_map_[oponente]]
  pool[is.na(f_oponente), f_oponente := 0]

  rango_obs <- range(pool$f_oponente)
  rango_95  <- quantile(pool$f_oponente, c(0.025, 0.975), names = FALSE)
  if (f_rival_target < rango_95[1] || f_rival_target > rango_95[2]) {
    warning(sprintf(
      "[QoO %s] f_rival=%.2f fuera del 95%% del pool [%.2f, %.2f] — truncado a [%.2f,%.2f]",
      etiqueta, f_rival_target, rango_95[1], rango_95[2],
      rango_obs[1], rango_obs[2]), call. = FALSE)
  }
  f_eff <- pmin(pmax(f_rival_target, rango_obs[1]), rango_obs[2])

  pesos <- pool$peso

  for (m in metricas_ajustar) {
    if (!m %in% names(pool)) next
    v <- pool[[m]]
    if (all(is.na(v)) || sum(!is.na(v)) < 5) next
    if (var(v, na.rm = TRUE) == 0) next
    if (mean(is.na(v) | v == 0) > 0.5) next  # demasiado NA/0: salto silencioso
    fml <- as.formula(paste0("`", m, "` ~ f_oponente"))
    mod <- tryCatch(
      lm(fml, data = pool, weights = pool$peso),
      error = function(e) NULL, warning = function(w) NULL
    )
    if (is.null(mod)) next
    pred_target <- as.numeric(predict(mod,
                     newdata = data.frame(f_oponente = f_eff)))
    pred_fila   <- as.numeric(predict(mod, newdata = pool))

    # CAP del shift al ±cap_pct de la media observada (default 35%).
    # Evita extrapolaciones absurdas cuando la pendiente está sobreajustada.
    mu_v           <- weighted.mean(v, pesos, na.rm = TRUE)
    mean_pred_fila <- weighted.mean(pred_fila, pesos, na.rm = TRUE)
    shift_prop     <- pred_target - mean_pred_fila
    cap_abs        <- cap_pct * mu_v
    shift_eff      <- max(min(shift_prop, cap_abs), -cap_abs)
    pred_target_eff <- mean_pred_fila + shift_eff

    if (abs(shift_eff - shift_prop) > 1e-6) {
      warning(sprintf(
        "[QoO %s] %s: shift cap'eado %.2f → %.2f (cap=±%.2f, mu=%.2f)",
        etiqueta, m, shift_prop, shift_eff, cap_abs, mu_v),
        call. = FALSE)
    }

    nuevo <- pmax(0, v - pred_fila + pred_target_eff)
    pool[, (m) := nuevo]
  }
  pool[, f_oponente := NULL]
  pool
}

METRICAS_QOO <- c("goles", "total_shots", "corner_kicks", "expected_goals")

simular_partido_bootstrap <- function(pool_A, pool_B, n_sim,
                                       metricas, cols_shrink,
                                       eA = NULL, eB = NULL) {
  if (is.null(pool_A) || is.null(pool_B) ||
      nrow(pool_A) == 0 || nrow(pool_B) == 0) {
    return(NULL)
  }

  idx_A <- sample.int(nrow(pool_A), size = n_sim,
                      replace = TRUE, prob = pool_A$peso)
  idx_B <- sample.int(nrow(pool_B), size = n_sim,
                      replace = TRUE, prob = pool_B$peso)

  # Matrices de simulación (filas = iteraciones, cols = métricas)
  sim_A <- as.matrix(pool_A[idx_A, ..metricas])
  sim_B <- as.matrix(pool_B[idx_B, ..metricas])

  # Sustituir eventos raros con Poisson shrunk (más estable)
  for (c in cols_shrink) {
    rate_A <- tasa_shrunk(pool_A, c)
    rate_B <- tasa_shrunk(pool_B, c)
    sim_A[, c] <- rpois(n_sim, lambda = max(rate_A, 1e-6))
    sim_B[, c] <- rpois(n_sim, lambda = max(rate_B, 1e-6))
  }

  # --- Fix 3: blend Poisson-FIFA para GOLES exclusivamente. ---
  # Re-derivamos sim_A[,"goles"] y sim_B[,"goles"] desde el blend:
  #   λ_blended = 0.60 * λ_pool + 0.40 * λ_fifa
  # Esto corrige asimetrías que el bootstrap regional no puede generar
  # (caso típico: ARG vs rival europeo modesto sin precedentes análogos).
  # No tocamos NINGUNA otra métrica — bootstrap se queda íntegro para
  # córners, tarjetas, faltas, tiros, pases, entradas, paradas, etc.
  #
  # ⚠ MEJORA #1 (REVISION_CRITICA, Fase 1): seguimos exponiendo lam_*_blend
  # en el retorno para que `calcular_mercados` re-derive 1X2/BTTS/marcador
  # exacto/margen/HT-FT/mitad-mas-goles/intervalo-goles desde la matriz
  # Dixon-Coles, en vez de desde las sims Poisson independientes que
  # destruyen la covarianza goles_A ↔ goles_B.
  lam_a_blend <- NA_real_
  lam_b_blend <- NA_real_
  if (!is.null(eA) && !is.null(eB) && "goles" %in% metricas) {
    lam_a_pool <- mean(sim_A[, "goles"])
    lam_b_pool <- mean(sim_B[, "goles"])
    el <- elo_lambdas(get_elo(eA), get_elo(eB))
    lam_a_blend <- (1 - W_FIFA) * lam_a_pool + W_FIFA * el$lambda_a
    lam_b_blend <- (1 - W_FIFA) * lam_b_pool + W_FIFA * el$lambda_b
    sim_A[, "goles"] <- rpois(n_sim, lambda = max(lam_a_blend, 1e-6))
    sim_B[, "goles"] <- rpois(n_sim, lambda = max(lam_b_blend, 1e-6))
  }

  list(A = sim_A, B = sim_B,
       n_pool_A = nrow(pool_A), n_pool_B = nrow(pool_B),
       lam_a_blend = lam_a_blend, lam_b_blend = lam_b_blend)
}


# --------------------- 5.4 Dixon-Coles τ-correction -----------------------
# ⚠ MEJORA #1 (REVISION_CRITICA, Fase 1).
# Reemplaza la mezcla 50/50 bootstrap+Poisson de marcador exacto y
# RE-DERIVA desde la matriz cerrada los mercados 1X2, BTTS, margen,
# marcador exacto, intervalo de goles, HT/FT y mitad-más-goles.
# Justificación: el blend Poisson-FIFA de la fase anterior resampleaba
# gA, gB como Poisson INDEPENDIENTES, destruyendo la covarianza empírica
# goles_A↔goles_B (ρ ≈ -0.05 a -0.10 según Dixon-Coles 1997). Con τ
# aplicado sobre las 4 celdas (0,0)/(0,1)/(1,0)/(1,1) inflamos 0-0 y 1-1
# y deflamos 1-0 y 0-1 — lo que añade la masa que el empate necesitaba.
# ρ = -0.08, valor central reportado para selecciones en venue neutral.
RHO_DC <- -0.08
MAX_GOLES_DC <- 6   # marcador exacto 0..6 (mismo dominio que el script original)

dixon_coles_matrix <- function(lam_a, lam_b, rho = RHO_DC, max_g = MAX_GOLES_DC) {
  lam_a <- max(lam_a, 1e-6)
  lam_b <- max(lam_b, 1e-6)
  ii <- 0:max_g
  M <- outer(ii, ii, function(I, J) dpois(I, lam_a) * dpois(J, lam_b))
  # aplicar τ a las 4 celdas
  M[1, 1] <- M[1, 1] * (1 - lam_a * lam_b * rho)  # (0,0)
  M[1, 2] <- M[1, 2] * (1 + lam_a * rho)          # (0,1)
  M[2, 1] <- M[2, 1] * (1 + lam_b * rho)          # (1,0)
  M[2, 2] <- M[2, 2] * (1 - rho)                  # (1,1)
  # renormalizar al subdominio truncado [0..max_g]²
  M / sum(M)
}

# Muestreador conjunto: dada matriz DC 7x7, devuelve N pares (i,j) con
# probabilidad proporcional a la celda. Garantiza que TODO el pipeline
# downstream de goles (rbinom de split H1/H2, intervalos, etc.) opere
# sobre samples coherentes con DC, no sobre los Poisson independientes
# del blend.
sample_dc <- function(M, n_sim) {
  k <- nrow(M)
  flat <- as.vector(M)
  idx <- sample.int(length(flat), size = n_sim,
                    replace = TRUE, prob = flat)
  # idx en columna-mayor: fila = ((idx-1) %% k); col = ((idx-1) %/% k)
  list(gA = as.integer((idx - 1L) %% k),
       gB = as.integer((idx - 1L) %/% k))
}


###############################################################################
# BLOQUE 6: cálculo de mercados de equipo a partir de las simulaciones MC
###############################################################################

# 6.1 Métricas que ofrecemos como O/U (todas en steps de 1.0, línea X+0.5)
metricas_ou <- c("goles", "corner_kicks", "yellow_cards", "fouls",
                 "total_shots", "shots_on_target", "shots_off_target",
                 "shots_inside_box", "shots_outside_box", "blocked_shots",
                 "offsides", "tackles", "goalkeeper_saves",
                 "free_kicks", "throw-ins", "goal_kicks",
                 "passes", "accurate_passes")
metricas_ou <- intersect(metricas_ou, metricas_equipo)

# Generar líneas semienteras alrededor de la media
generar_lineas <- function(mu) {
  if (is.na(mu) || mu < 0) return(numeric(0))
  centro <- floor(mu)
  ofs <- (-3):5
  lns <- centro + ofs + 0.5
  lns <- lns[lns >= 0.5]
  unique(round(lns, 2))
}

# ⚠ MEJORA #7 (REVISION_CRITICA, Fase 2): suavizado de O/U vía Negative
# Binomial. La estimación empírica P(X > L) = mean(sim > L) tiene saltos
# "spiky" cuando N_SIM·P(L) está cerca de un entero. Ejemplo documentado:
# córners PAN_GHA daba 51% over 7.5 → 25% over 8.5 (caída brusca, debería
# ser ~38% intermedio). Ajustando NB(μ, θ) por MLE sobre las sims y derivando
# 1 - pnbinom(L, size=θ, mu=μ), las líneas adyacentes se interpolan a una
# curva suave coherente con la sobre-dispersión empírica.
#
# Fallback escalonado:
#   1. NB MLE (fitdistr en MASS). Si converge y θ es razonable (>0, <10000).
#   2. Poisson MLE — válido si NB diverge por var ≈ mean (no hay sobredisp).
#   3. Empírico (mean(sim > L)) — último recurso, comportamiento original.
#
# Excepción: `goles` se OMITE de la suavización NB porque ya viene de la
# matriz Dixon-Coles (función analítica cerrada) — aplicar NB encima sería
# regularizar dos veces y borrar la covarianza inducida por τ.
#
# Optimización: el ajuste NB es caro (~10ms por vector), así que se hace
# UNA VEZ por (partido, métrica, ámbito) cacheando los parámetros, y se
# evalúa la cdf para las 9 líneas O(1) cada una. Coste total: ~6s en
# total sobre 72 partidos × 18 métricas × 3 ámbitos = 3888 fits.
# Optimización: para N_SIM=20000 el ajuste por MLE (fitdistr) es 100ms+
# por vector. Con 18 métricas × 3 ámbitos × 72 partidos = 3888 fits, eso
# son ~6 minutos solo de NB. El método de los momentos (MoM) da el mismo
# resultado para N grande y es 1000× más rápido:
#   μ = mean(sim); var = var(sim); size = μ² / (var - μ)
# Si var ≤ μ (no hay sobredisp), fallback a Poisson.
fit_distr_cache <- function(sim_vec) {
  if (length(sim_vec) == 0L || all(is.na(sim_vec))) {
    return(list(tipo = "empirico", sim_vec = sim_vec))
  }
  sim_vec <- sim_vec[!is.na(sim_vec)]
  mu <- mean(sim_vec)
  if (mu <= 0) return(list(tipo = "cero"))
  vv <- var(sim_vec)
  # MoM NB: size = μ² / (σ² - μ). Válido si σ² > μ.
  if (vv > mu * 1.02) {
    size <- mu^2 / (vv - mu)
    if (is.finite(size) && size > 0 && size < 1e4) {
      return(list(tipo = "nb", size = size, mu = mu))
    }
  }
  # Poisson (var ≈ mean o sub-disp espurio)
  list(tipo = "pois", mu = mu)
}

prob_ou_from_fit <- function(fit, linea) {
  if (fit$tipo == "cero") return(0)
  if (fit$tipo == "nb")
    return(1 - pnbinom(floor(linea), size = fit$size, mu = fit$mu))
  if (fit$tipo == "pois")
    return(1 - ppois(floor(linea), lambda = fit$mu))
  # empirico (sin caché)
  mean(fit$sim_vec > linea)
}

# 6.2 Función master: dadas sim_A, sim_B (matrices N×n_metricas), calcula
#     TODOS los mercados y devuelve una lista de filas para CSV largo.
calcular_mercados <- function(sims, pid, fecha, eA, eB,
                              metricas_equipo, metricas_ou,
                              n_sim = N_SIM) {
  out <- list()
  push <- function(mercado, ambito, evento, linea, prob) {
    out[[length(out) + 1L]] <<- list(
      partido_id = pid, fecha = fecha, equipo_a = eA, equipo_b = eB,
      mercado = mercado, ambito = ambito, evento_o_jugador = evento,
      linea_o_target = linea,
      probabilidad = round(max(0, min(1, prob)), 4)
    )
  }

  if (is.null(sims)) return(NULL)
  sA <- sims$A; sB <- sims$B

  # ⚠ MEJORA #1: re-samplear (gA, gB) desde la matriz Dixon-Coles.
  # Esto sustituye los gA/gB que venían como Poisson INDEPENDIENTES
  # del blend FIFA. Todos los mercados de goles downstream — 1X2, BTTS,
  # margen, marcador exacto, intervalos, HT/FT y mitad-más-goles —
  # operan sobre los nuevos gA, gB y heredan la covarianza inducida por τ.
  lam_a_dc <- sims$lam_a_blend
  lam_b_dc <- sims$lam_b_blend
  if (is.na(lam_a_dc) || is.na(lam_b_dc)) {
    # fallback: si no hay blend disponible, usa la media del bootstrap
    lam_a_dc <- mean(sA[, "goles"]); lam_b_dc <- mean(sB[, "goles"])
  }
  M_dc <- dixon_coles_matrix(lam_a_dc, lam_b_dc)  # 7x7 normalizada
  smp <- sample_dc(M_dc, n_sim)
  gA <- smp$gA; gB <- smp$gB
  # Sobrescribir también en las matrices sim_A/sim_B para que cualquier
  # consumidor downstream (mercados_jugadores_partido y O/U de goles)
  # vea los valores corregidos.
  sA[, "goles"] <- gA
  sB[, "goles"] <- gB

  # ------------------ MERCADOS DISCRETOS ------------------
  # 1X2  (derivado de la matriz DC vía samples re-derivados → coherente)
  p_a <- mean(gA > gB); p_x <- mean(gA == gB); p_b <- mean(gA < gB)
  push("1X2", "-", "gana_A", "-", p_a)
  push("1X2", "-", "empate", "-", p_x)
  push("1X2", "-", "gana_B", "-", p_b)

  # Doble oportunidad
  push("doble_oportunidad", "-", "1X", "-", p_a + p_x)
  push("doble_oportunidad", "-", "X2", "-", p_x + p_b)
  push("doble_oportunidad", "-", "12", "-", p_a + p_b)

  # BTTS
  p_btts <- mean(gA >= 1 & gB >= 1)
  push("btts", "-", "si", "-", p_btts)
  push("btts", "-", "no", "-", 1 - p_btts)

  # Margen de victoria (diff = gA - gB), agrupando colas a -5 y +5
  diff <- gA - gB
  diff_c <- pmax(pmin(diff, 5), -5)
  for (d in -5:5) {
    p_d <- mean(diff_c == d)
    etiqueta <- if (d == -5) "B_gana_5+" else if (d == 5) "A_gana_5+" else
                if (d == 0) "empate_0" else
                if (d > 0) sprintf("A_gana_%d", d) else
                            sprintf("B_gana_%d", -d)
    push("margen_victoria", "-", etiqueta, "-", p_d)
  }

  # Marcador exacto 0..6: leído DIRECTAMENTE de la matriz DC normalizada.
  # Ya no es una mezcla 50/50 — la suma del mercado pasa de 0.99 a 1.00
  # exacto, porque la matriz está renormalizada al subdominio truncado.
  for (i in 0:MAX_GOLES_DC) for (j in 0:MAX_GOLES_DC) {
    push("marcador_exacto", "-", sprintf("%d-%d", i, j), "-",
         M_dc[i + 1L, j + 1L])
  }

  # Repartir goles por mitades (Bin(g, 0.45) para H1) — opera sobre los
  # gA, gB ya muestreados desde DC. La covarianza inducida por τ se
  # propaga automáticamente a HT/FT y mitad-más-goles.
  gA_h1 <- rbinom(n_sim, size = gA, prob = 0.45); gA_h2 <- gA - gA_h1
  gB_h1 <- rbinom(n_sim, size = gB, prob = 0.45); gB_h2 <- gB - gB_h1

  # HT/FT (resultado al descanso / final)
  ht <- ifelse(gA_h1 > gB_h1, "1", ifelse(gA_h1 == gB_h1, "X", "2"))
  ft <- ifelse(gA    > gB,    "1", ifelse(gA    == gB,    "X", "2"))
  for (h in c("1","X","2")) for (f in c("1","X","2")) {
    p_hf <- mean(ht == h & ft == f)
    push("ht_ft", "-", sprintf("%s/%s", h, f), "-", p_hf)
  }

  # Mitad con más goles
  gh1 <- gA_h1 + gB_h1; gh2 <- gA_h2 + gB_h2
  push("mitad_mas_goles", "-", "H1",    "-", mean(gh1 > gh2))
  push("mitad_mas_goles", "-", "H2",    "-", mean(gh1 < gh2))
  push("mitad_mas_goles", "-", "igual", "-", mean(gh1 == gh2))

  # Intervalos de goles (total) — re-derivado desde gA, gB DC
  tot <- gA + gB
  push("intervalo_goles", "TOTAL", "0-1", "-", mean(tot <= 1))
  push("intervalo_goles", "TOTAL", "2-3", "-", mean(tot >= 2 & tot <= 3))
  push("intervalo_goles", "TOTAL", "4-6", "-", mean(tot >= 4 & tot <= 6))
  push("intervalo_goles", "TOTAL", "7+",  "-", mean(tot >= 7))

  # =====================================================================
  # ⚠ MEJORAS FASE 4 (REVISION_CRITICA, sección E): 10 mercados nuevos
  # =====================================================================
  # Todos derivados de gA, gB, gA_h1, gB_h1 ya muestreados desde DC ⇒
  # coherencia interna automática con 1X2/BTTS/marcador exacto.

  # 1) Asian Handicap A — líneas -2.5 a +2.5 en steps de 0.5
  # Formato: ámbito = "A" o "B" (equipo que recibe el handicap),
  #          evento_o_jugador = "cubre", linea_o_target = valor del handicap.
  for (h in seq(-2.5, 2.5, by = 0.5)) {
    # A "cubre" h si (gA + h) > gB  ⇔  diff > -h
    p_cover_A <- mean((gA - gB) > -h)
    etiqueta_h <- if (h >= 0) sprintf("+%.1f", h) else sprintf("%.1f", h)
    push("asian_handicap", "A", "cubre", etiqueta_h, p_cover_A)
    push("asian_handicap", "B", "cubre", etiqueta_h, 1 - p_cover_A)
  }

  # 2) Clean sheet por equipo
  push("clean_sheet", "A", "si", "-", mean(gB == 0))
  push("clean_sheet", "A", "no", "-", 1 - mean(gB == 0))
  push("clean_sheet", "B", "si", "-", mean(gA == 0))
  push("clean_sheet", "B", "no", "-", 1 - mean(gA == 0))

  # 3) Win to nil (gana sin encajar)
  push("win_to_nil", "A", "si", "-", mean(gA > gB & gB == 0))
  push("win_to_nil", "A", "no", "-", 1 - mean(gA > gB & gB == 0))
  push("win_to_nil", "B", "si", "-", mean(gB > gA & gA == 0))
  push("win_to_nil", "B", "no", "-", 1 - mean(gB > gA & gA == 0))

  # 4) Both halves with goal (al menos un gol en cada mitad)
  tot_h1 <- gA_h1 + gB_h1; tot_h2 <- gA_h2 + gB_h2
  push("both_halves_goal", "-", "si", "-", mean(tot_h1 >= 1 & tot_h2 >= 1))
  push("both_halves_goal", "-", "no", "-", 1 - mean(tot_h1 >= 1 & tot_h2 >= 1))

  # 5) HT goles O/U (líneas 0.5, 1.5, 2.5)
  fit_ht <- fit_distr_cache(tot_h1)
  for (L in c(0.5, 1.5, 2.5)) {
    p_over <- prob_ou_from_fit(fit_ht, L)
    push("goles_ht", "TOTAL", "over",  L, p_over)
    push("goles_ht", "TOTAL", "under", L, 1 - p_over)
  }

  # 6) Win + BTTS combinado (gana A o B y ambos marcan)
  push("win_btts", "A_btts", "si", "-", mean(gA > gB & gA >= 1 & gB >= 1))
  push("win_btts", "A_btts", "no", "-", 1 - mean(gA > gB & gA >= 1 & gB >= 1))
  push("win_btts", "B_btts", "si", "-", mean(gB > gA & gA >= 1 & gB >= 1))
  push("win_btts", "B_btts", "no", "-", 1 - mean(gB > gA & gA >= 1 & gB >= 1))

  # 7) Time of first goal — Poisson uniforme en minuto. Asume tasa
  # constante: λ_total_min = (gA+gB) por 90'. P(no goal en intervalo) =
  # exp(-λ_min · longitud_intervalo). Para mejor precisión usaríamos
  # el patrón empírico (más goles en últimos 15 de cada mitad), pero el
  # plan dice "asume Poisson uniforme en primera implementación".
  lam_tot <- lam_a_dc + lam_b_dc                  # goles esperados por 90'
  if (lam_tot > 0) {
    lam_min <- lam_tot / 90
    # P(primer gol cae en intervalo [a,b]) = P(>=1 gol en [0,b]) - P(>=1 gol en [0,a])
    intervalos <- list(c(1,15), c(16,30), c(31,45), c(46,60), c(61,75), c(76,90))
    nombres <- c("1-15","16-30","31-45","46-60","61-75","76-90")
    prev_acc <- 0
    for (k in seq_along(intervalos)) {
      b_end <- intervalos[[k]][2]
      p_acc <- 1 - exp(-lam_min * b_end)
      push("primer_gol", "-", nombres[k], "-", p_acc - prev_acc)
      prev_acc <- p_acc
    }
    push("primer_gol", "-", "no_goal", "-", exp(-lam_tot))
  }

  # 8) Corners H1 O/U — split 48/52 H1/H2 (literatura OPTA)
  # No tenemos sims separadas por mitad, así que aplicamos split a vT.
  vC <- sA[, "corner_kicks"] + sB[, "corner_kicks"]
  vC_h1 <- rbinom(n_sim, size = vC, prob = 0.48)
  fit_cor_h1 <- fit_distr_cache(vC_h1)
  for (L in seq(2.5, 6.5, by = 1)) {
    p_over <- prob_ou_from_fit(fit_cor_h1, L)
    push("corners_ht", "TOTAL", "over",  L, p_over)
    push("corners_ht", "TOTAL", "under", L, 1 - p_over)
  }

  # Tarjetas rojas: por partido y por mitad (distribución 30%/70% a H1/H2)
  rA <- sA[, "red_cards"]; rB <- sB[, "red_cards"]
  rA_h1 <- rbinom(n_sim, size = pmin(rA, 5), prob = 0.30); rA_h2 <- pmin(rA, 5) - rA_h1
  rB_h1 <- rbinom(n_sim, size = pmin(rB, 5), prob = 0.30); rB_h2 <- pmin(rB, 5) - rB_h1
  push("roja_partido",   "-", "si", "-", mean((rA + rB) >= 1))
  push("roja_partido",   "-", "no", "-", mean((rA + rB) == 0))
  push("roja_H1",        "-", "si", "-", mean((rA_h1 + rB_h1) >= 1))
  push("roja_H2",        "-", "si", "-", mean((rA_h2 + rB_h2) >= 1))

  # Ambos equipos al menos una amarilla
  yA <- sA[, "yellow_cards"]; yB <- sB[, "yellow_cards"]
  push("ambos_amarilla", "-", "si", "-", mean(yA >= 1 & yB >= 1))
  push("ambos_amarilla", "-", "no", "-", 1 - mean(yA >= 1 & yB >= 1))

  # Equipo con más amarillas / córners / faltas
  for (m in c("yellow_cards", "corner_kicks", "fouls")) {
    nombre_m <- switch(m,
      "yellow_cards" = "equipo_mas_amarillas",
      "corner_kicks" = "equipo_mas_corners",
      "fouls"        = "equipo_mas_faltas")
    vA <- sA[, m]; vB <- sB[, m]
    push(nombre_m, "-", "A",      "-", mean(vA > vB))
    push(nombre_m, "-", "empate", "-", mean(vA == vB))
    push(nombre_m, "-", "B",      "-", mean(vA < vB))
  }

  # 9) Penalty en el partido (S/N). Tasa = 1 - (1-tasa_A)(1-tasa_B) asumiendo
  # independencia entre equipos. Fuente: tasa histórica por equipo desde tel.
  # Conservador: si un equipo no tiene tasa estimada, usa media global (~0.10).
  tasa_default <- 0.10
  tA <- penalty_rate_map[eA]; if (is.na(tA)) tA <- tasa_default
  tB <- penalty_rate_map[eB]; if (is.na(tB)) tB <- tasa_default
  # Tasa partido: probabilidad de penalty asociado a cualquier equipo
  # Suponiendo eventos independientes: P(>=1 pen) = 1 - (1-tA)(1-tB) si las
  # tasas son por-partido del equipo (capturan penalties a favor o en contra).
  # Como tA y tB ya cuentan penalties que involucran a A y B respectivamente
  # y se solapan en el mismo evento (si tu equipo gana un pen tu rival lo
  # concedió), promediamos en vez de combinar como independientes.
  p_pen <- (tA + tB) / 2
  p_pen <- max(0.01, min(0.5, p_pen))
  push("penalty_partido", "-", "si", "-", p_pen)
  push("penalty_partido", "-", "no", "-", 1 - p_pen)
  # Penalty para A (lanzado por A): usa la mitad correspondiente al equipo
  pA_pen <- max(0.005, min(0.4, tA / 2))
  pB_pen <- max(0.005, min(0.4, tB / 2))
  push("penalty_equipo", "A", "si", "-", pA_pen)
  push("penalty_equipo", "A", "no", "-", 1 - pA_pen)
  push("penalty_equipo", "B", "si", "-", pB_pen)
  push("penalty_equipo", "B", "no", "-", 1 - pB_pen)

  # ------------------ MERCADOS DE CONTEO (O/U) ------------------
  # ⚠ MEJORA #7: NB-smoothing para todas las métricas EXCEPTO `goles`,
  # que ya viene de Dixon-Coles (analítico cerrado). Aplicar NB encima de
  # DC sería regularizar dos veces y romper la coherencia. Ajuste cacheado:
  # un fit por (métrica, ámbito) reutilizado para las ~9 líneas.
  for (m in metricas_ou) {
    vA <- sA[, m]; vB <- sB[, m]; vT <- vA + vB
    lns_A <- generar_lineas(mean(vA))
    lns_B <- generar_lineas(mean(vB))
    lns_T <- generar_lineas(mean(vT))
    usar_nb <- (m != "goles")
    if (usar_nb) {
      fitA <- fit_distr_cache(vA)
      fitB <- fit_distr_cache(vB)
      fitT <- fit_distr_cache(vT)
    }
    for (L in lns_A) {
      p_over <- if (usar_nb) prob_ou_from_fit(fitA, L) else mean(vA > L)
      push(m, "A", "over",  L, p_over)
      push(m, "A", "under", L, 1 - p_over)
    }
    for (L in lns_B) {
      p_over <- if (usar_nb) prob_ou_from_fit(fitB, L) else mean(vB > L)
      push(m, "B", "over",  L, p_over)
      push(m, "B", "under", L, 1 - p_over)
    }
    for (L in lns_T) {
      p_over <- if (usar_nb) prob_ou_from_fit(fitT, L) else mean(vT > L)
      push(m, "TOTAL", "over",  L, p_over)
      push(m, "TOTAL", "under", L, 1 - p_over)
    }
  }

  rbindlist(out)
}


###############################################################################
# BLOQUE 7: mercados de jugador (los 58 a 80 minutos, bootstrap por jugador)
###############################################################################

# 7.1 Mapeo jugador -> selección (el equipo del jugador es el que más se
#     repite entre home_team / away_team de sus partidos)
cat("\n[7] Construyendo perfiles de jugador...\n")

# Imputar NA->0 en métricas de telemetría para no propagarlos al bootstrap
metricas_jugador <- c(
  "minutesPlayed", "goals", "goalAssist", "expectedGoals", "expectedAssists",
  "totalShots", "onTargetScoringAttempt", "shotOffTarget",
  "blockedScoringAttempt", "totalPass", "accuratePass", "keyPass",
  "bigChanceCreated", "totalTackle", "wonTackle", "interceptionWon",
  "ballRecovery", "fouls", "wasFouled", "aerialWon", "aerialLost",
  "duelWon", "duelLost", "saves", "savedShotsFromInsideTheBox",
  "penaltySave", "goalsPrevented", "punches", "totalCross", "accurateCross",
  "totalContest", "wonContest", "dispossessed", "totalLongBalls",
  "accurateLongBalls", "touches", "totalOffside", "hitWoodwork"
)
metricas_jugador <- intersect(metricas_jugador, names(tel))
for (m in metricas_jugador) {
  if (!is.double(tel[[m]])) tel[, (m) := as.numeric(get(m))]
  tel[is.na(get(m)), (m) := 0]
}

# Determinar selección de cada jugador (la más frecuente entre home/away)
seleccion_jugador <- tel[, {
  combos <- c(home_team, away_team)
  combos <- combos[!is.na(combos) & combos != ""]
  if (length(combos) == 0) "(desconocido)"
  else {
    tab <- sort(table(combos), decreasing = TRUE)
    names(tab)[1]
  }
}, by = jugador]
setnames(seleccion_jugador, "V1", "seleccion")

# Filtrar a jugadores con selección que juega el Mundial
seleccion_jugador <- seleccion_jugador[seleccion %in% equipos_mundial]
cat("  Jugadores asignados a selección del Mundial:",
    nrow(seleccion_jugador), "de", uniqueN(tel$jugador), "\n")

# 7.2 Construcción del pool del jugador:
#     50% sus partidos generales + 50% sus partidos cuando el rival era estilo
#     del rival en el próximo partido del Mundial.
construir_pool_jugador <- function(jugador_nombre, propia_sel, rival_real,
                                   tel_dt, vecinos_por_eq) {
  rows_player <- tel_dt[jugador == jugador_nombre]
  if (nrow(rows_player) == 0) return(NULL)

  # Identificar oponente de cada partido del jugador
  rows_player[, oponente := ifelse(home_team == propia_sel, away_team, home_team)]

  # Componente general (50%)
  rows_gen <- copy(rows_player); rows_gen[, peso := 1 / .N]

  # Componente contextual: rivales en KNN del rival real
  vec_rival <- vecinos_por_eq[[rival_real]]
  if (is.null(vec_rival)) {
    rows_ctx <- rows_player[0]
  } else {
    rows_ctx <- rows_player[oponente %in% vec_rival$vecino]
    if (nrow(rows_ctx) > 0) {
      w_sim <- setNames(vec_rival$peso, vec_rival$vecino)
      rows_ctx[, peso := w_sim[oponente] / sum(w_sim[oponente])]
    }
  }

  presente <- c(general = nrow(rows_gen) > 0, ctx = nrow(rows_ctx) > 0)
  w_glob <- c(general = 0.5, ctx = 0.5) * presente
  if (sum(w_glob) == 0) return(NULL)
  w_glob <- w_glob / sum(w_glob)

  if (nrow(rows_gen) > 0) rows_gen[, peso := peso * w_glob["general"]]
  if (nrow(rows_ctx) > 0) rows_ctx[, peso := peso * w_glob["ctx"]]
  rows_ctx[, componente := "ctx"]; rows_gen[, componente := "general"]

  pool <- rbindlist(list(rows_gen, rows_ctx), fill = TRUE)
  pool[, peso := peso / sum(peso)]
  pool
}

# 7.3 Simular un jugador a 80' usando bootstrap del pool
#     Convertimos cada fila a tasa por-90 y escalamos a 80', luego
#     Poisson-sampleamos para añadir incertidumbre de evento.
simular_jugador <- function(pool, n_sim, minutos = 80,
                             jugador_nombre = NULL) {
  if (is.null(pool) || nrow(pool) == 0) return(NULL)
  # ⚠ MEJORA #6 (REVISION_CRITICA, Fase 2): filtro escalonado de
  # minutesPlayed. Antes: ≥15 min. Justificación: bootstrap escalaba un
  # cameo de 15 min × (80/15) = 5.3× — un jugador con 1 disparo en 15'
  # se proyecta a 5.3 disparos en 80', exagerando varianza y sobre-
  # estimando counts. Con ≥45' filtramos a appearances "sustanciales"
  # (no entradas finales para chupar minutos), reducimos el factor de
  # escala máximo a ~1.8× y eliminamos extrapolaciones absurdas.
  # Fallback: si <5 filas en pool, baja a ≥30; si <3, ≥15 + warning
  # (cobertura crítica de jugadores con poca historia).
  n_total <- nrow(pool)
  pool_45 <- pool[minutesPlayed >= 45]
  if (nrow(pool_45) >= 5) {
    pool <- pool_45
  } else {
    pool_30 <- pool[minutesPlayed >= 30]
    if (nrow(pool_30) >= 3) {
      pool <- pool_30
    } else {
      pool_15 <- pool[minutesPlayed >= 15]
      if (nrow(pool_15) > 0 && !is.null(jugador_nombre)) {
        warning(sprintf("[#6] %s: pool insuficiente >=30 (n=%d) y >=45 (n=%d), fallback a >=15 (n=%d)",
                        jugador_nombre, nrow(pool_30), nrow(pool_45), nrow(pool_15)),
                call. = FALSE)
      }
      pool <- pool_15
    }
  }
  if (nrow(pool) == 0) return(NULL)
  pool[, peso := peso / sum(peso)]

  idx <- sample.int(nrow(pool), n_sim, replace = TRUE, prob = pool$peso)
  fila_min <- pool[idx, minutesPlayed]
  escala <- minutos / fila_min  # factor a aplicar para reescalar a 80'

  # Acciones de conteo: λ por sim = (valor_fila / min_fila × 90) × (80/90)
  #                              = valor_fila × (80/min_fila)
  # ⚠ MEJORA #4 (REVISION_CRITICA, Fase 1) + REFINADO post-validación:
  # bootstrap directo escalado a 80'. Por Jensen, una segunda capa rpois(λ)
  # encima de conteos Poisson observados inflaba P(Y=0) en 5-10pp. La forma
  # naive de quitarlo — `round(λ_escalada)` — es DETERMINISTA y produce el
  # problema opuesto: una fila con goals*80/min=0.89 redondea a 1 SIEMPRE,
  # disparando P(anota) artificialmente (Haaland 61% → 90% observado).
  # Solución: split a λ=1.
  #   - λ < 1  → Bernoulli con prob=λ  (preserva λ esperada Y varianza
  #              correcta para eventos raros como goles, tarjetas).
  #   - λ ≥ 1  → round (conteo medio-alto: el redondeo solo recorta cola
  #              fraccional sin afectar masa en 0 o 1).
  # Esto preserva la mejora #4 (sin Jensen) sin reintroducir bias inverso.
  cnt_cols <- c("goals", "goalAssist", "totalShots",
                "onTargetScoringAttempt", "shotOffTarget",
                "blockedScoringAttempt", "totalPass", "accuratePass",
                "keyPass", "bigChanceCreated", "totalTackle", "wonTackle",
                "interceptionWon", "ballRecovery", "fouls", "wasFouled",
                "aerialWon", "duelWon", "saves",
                "savedShotsFromInsideTheBox", "totalCross",
                "accurateCross", "totalLongBalls", "accurateLongBalls")
  cnt_cols <- intersect(cnt_cols, names(pool))
  sim <- matrix(0L, nrow = n_sim, ncol = length(cnt_cols),
                dimnames = list(NULL, cnt_cols))
  for (c in cnt_cols) {
    val_real <- pool[idx, get(c)] * escala
    val_real[is.na(val_real) | val_real < 0] <- 0
    # split λ<1 (Bernoulli) vs λ≥1 (bootstrap empírico redondeado)
    out <- integer(n_sim)
    bajo <- val_real < 1
    if (any(bajo)) {
      out[bajo] <- rbinom(sum(bajo), size = 1, prob = pmin(val_real[bajo], 1))
    }
    if (any(!bajo)) {
      out[!bajo] <- as.integer(round(val_real[!bajo]))
    }
    sim[, c] <- out
  }
  sim
}

# 7.4 Detección de porteros: jugadores con saves > 0 en >50% de sus
#     partidos jugados (los outfielders casi nunca tienen saves)
es_portero <- function(jugador_nombre, tel_dt) {
  r <- tel_dt[jugador == jugador_nombre]
  if (nrow(r) == 0) return(FALSE)
  mean(r$saves > 0 | r$minutesPlayed > 60 & r$totalKeeperSweeper > 0,
       na.rm = TRUE) > 0.5
}

# 7.5 Calcular mercados de jugador para un partido del Mundial
mercados_jugadores_partido <- function(pid, fecha, eA, eB, sims_eq) {
  # sims_eq: las simulaciones de equipo (para amarillas/falta ratio)
  jug_A <- seleccion_jugador[seleccion == eA, jugador]
  jug_B <- seleccion_jugador[seleccion == eB, jugador]

  filas <- list()
  push <- function(j, mercado, evento, linea, prob) {
    filas[[length(filas) + 1L]] <<- list(
      partido_id = pid, fecha = fecha, equipo_a = eA, equipo_b = eB,
      mercado = mercado, ambito = "JUGADOR", evento_o_jugador = j,
      linea_o_target = linea,
      probabilidad = round(max(0, min(1, prob)), 4)
    )
  }

  # Recolectar λ_goles por jugador para el mercado first_goalscorer
  lam_goles_jug <- list()

  for (info in list(list(jugs = jug_A, propio = eA, rival = eB),
                    list(jugs = jug_B, propio = eB, rival = eA))) {
    for (j in info$jugs) {
      pool_j <- construir_pool_jugador(j, info$propio, info$rival,
                                       tel, vecinos_por_eq)
      if (is.null(pool_j) || nrow(pool_j) == 0) next
      sim_j <- simular_jugador(pool_j, n_sim = N_SIM, minutos = MIN_TITULAR,
                                jugador_nombre = j)
      if (is.null(sim_j)) next

      # P(anotar), P(asistir), P(anotar o asistir)
      p_gol <- mean(sim_j[, "goals"] >= 1)
      p_ast <- mean(sim_j[, "goalAssist"] >= 1)
      p_g_o_a <- mean(sim_j[, "goals"] >= 1 | sim_j[, "goalAssist"] >= 1)
      push(j, "anotara", "si", "-", p_gol)
      push(j, "anotara", "no", "-", 1 - p_gol)
      push(j, "asistira", "si", "-", p_ast)
      push(j, "asistira", "no", "-", 1 - p_ast)
      push(j, "anotara_o_asistira", "si", "-", p_g_o_a)

      # Guardar λ de goles para el mercado first_goalscorer
      lam_goles_jug[[j]] <- mean(sim_j[, "goals"])

      # Amarilla del jugador: heurística desde su ratio de faltas y
      # ratio team-level yellow/foul del propio equipo
      eq_stats <- stats[equipo_nombre == info$propio]
      ratio_y_f <- if (nrow(eq_stats) > 0 && sum(eq_stats$fouls, na.rm=TRUE) > 0) {
        sum(eq_stats$yellow_cards, na.rm=TRUE) /
          sum(eq_stats$fouls, na.rm=TRUE)
      } else 0.10
      f_sim <- sim_j[, "fouls"]
      # P(amarilla) ≈ 1 - exp(-fouls * ratio) por sim, promediar
      p_yj <- mean(1 - exp(-f_sim * ratio_y_f))
      push(j, "tarjeta_amarilla", "si", "-", p_yj)
      push(j, "tarjeta_amarilla", "no", "-", 1 - p_yj)

      # Remates O/U
      sh <- sim_j[, "totalShots"]
      for (L in c(0.5, 1.5, 2.5, 3.5)) {
        push(j, "remates", "over",  L, mean(sh > L))
        push(j, "remates", "under", L, mean(sh <= L))
      }
      # Remates a puerta O/U
      st <- sim_j[, "onTargetScoringAttempt"]
      for (L in c(0.5, 1.5)) {
        push(j, "remates_a_puerta", "over",  L, mean(st > L))
        push(j, "remates_a_puerta", "under", L, mean(st <= L))
      }
      # Remates de cabeza: heurística (sin columna directa)
      # λ_cabeza ≈ 0.15 * λ_remates (típico ~12-18% de tiros de cabeza)
      lam_h <- 0.15 * mean(sh)
      p_h <- 1 - dpois(0, lambda = lam_h)
      push(j, "remates_cabeza", "si", "-", p_h)
      # Remates fuera del área: ratio team-level shots_outside_box/total_shots
      r_out <- if (sum(eq_stats$total_shots, na.rm=TRUE) > 0) {
        sum(eq_stats$shots_outside_box, na.rm=TRUE) /
          sum(eq_stats$total_shots, na.rm=TRUE)
      } else 0.40
      lam_out <- r_out * mean(sh)
      p_out <- 1 - dpois(0, lambda = lam_out)
      push(j, "remates_fuera_area", "si", "-", p_out)

      # Pases O/U
      ps <- sim_j[, "totalPass"]
      mu_ps <- mean(ps)
      lineas_pases <- c(30.5, 50.5, 70.5, 90.5)
      for (L in lineas_pases) {
        push(j, "pases", "over",  L, mean(ps > L))
        push(j, "pases", "under", L, mean(ps <= L))
      }
      # Entradas O/U
      tk <- sim_j[, "totalTackle"]
      for (L in c(0.5, 1.5, 2.5)) {
        push(j, "entradas", "over",  L, mean(tk > L))
        push(j, "entradas", "under", L, mean(tk <= L))
      }
      # Faltas concedidas O/U
      fl <- sim_j[, "fouls"]
      for (L in c(0.5, 1.5)) {
        push(j, "faltas_concedidas", "over",  L, mean(fl > L))
        push(j, "faltas_concedidas", "under", L, mean(fl <= L))
      }
      # Recibirá falta
      wf <- sim_j[, "wasFouled"]
      push(j, "recibira_falta", "si", "-", mean(wf >= 1))

      # Paradas (solo portero)
      if (es_portero(j, tel)) {
        sv <- sim_j[, "saves"]
        for (L in c(1.5, 2.5, 3.5, 4.5)) {
          push(j, "paradas", "over",  L, mean(sv > L))
          push(j, "paradas", "under", L, mean(sv <= L))
        }
      }
    }
  }

  # ⚠ MEJORA FASE 4 (mercado first_goalscorer): probabilidad de que cada
  # jugador con telemetría sea EL PRIMER GOLEADOR del partido.
  # Modelo: tiempo hasta primer gol de j ~ Exp(λ_j). De entre los procesos
  # competitivos, el menor gana con prob λ_j / Σλ. Adicionalmente:
  #   P(j es primero) = P(hay al menos un gol total) × (λ_j / Σλ_TOTAL_PARTIDO)
  # donde la primera parte = 1 - exp(-λ_total_partido).
  #
  # IMPORTANTE: el dataset cubre solo 2-4 jugadores con telemetría por
  # selección (los que SofaScore destaca). Los goleadores "no observados"
  # (defensas, mediocampistas suplentes, etc.) representan masa real.
  # Por eso usamos λ_TOTAL del partido (de DC) como denominador, NO la
  # suma de λ de los jugadores observados — eso atribuye automáticamente
  # la masa residual a la categoría "otro_jugador" sin sobre-asignar a
  # los pocos jugadores con telemetría. Ejemplo: si Messi λ_j=0.4 y el
  # partido tiene λ_TOTAL=2.5, P(Messi primero | gol) = 0.4/2.5 = 16%,
  # no 0.4/(λ_observados) que daría 60%+.
  #
  # RESCALADO: λ_jugador del bootstrap empírico puede estar inflado para
  # equipos con pool histórico vs rivales débiles (Morocco/AFCON). Para
  # alinear con la P(gol) del 1X2, normalizamos para que Σλ_obs_A <= λ_A_DC
  # (los obs no pueden exceder el total del equipo).
  if (length(lam_goles_jug) > 0 && !is.null(sims_eq)) {
    lam_a_target <- if (!is.na(sims_eq$lam_a_blend)) sims_eq$lam_a_blend else
                      mean(sims_eq$A[, "goles"])
    lam_b_target <- if (!is.na(sims_eq$lam_b_blend)) sims_eq$lam_b_blend else
                      mean(sims_eq$B[, "goles"])
    lam_total <- lam_a_target + lam_b_target

    jug_A_set <- intersect(names(lam_goles_jug),
                           seleccion_jugador[seleccion == eA, jugador])
    jug_B_set <- intersect(names(lam_goles_jug),
                           seleccion_jugador[seleccion == eB, jugador])

    sum_A_jug <- sum(unlist(lam_goles_jug[jug_A_set]))
    sum_B_jug <- sum(unlist(lam_goles_jug[jug_B_set]))

    # Capear suma observada A al 70% de λ_A_DC (deja >=30% para "otros")
    # En equipos top con buena cobertura, sum_obs ya estará ~50-60% del total.
    # En equipos con 1 solo titular destacado, baja a ese 70% para no
    # sobre-asignar al goleador estrella.
    fac_A <- if (sum_A_jug > 0) min(1, 0.70 * lam_a_target / sum_A_jug) else 1
    fac_B <- if (sum_B_jug > 0) min(1, 0.70 * lam_b_target / sum_B_jug) else 1

    lam_resc <- lam_goles_jug
    for (jj in jug_A_set) lam_resc[[jj]] <- lam_goles_jug[[jj]] * fac_A
    for (jj in jug_B_set) lam_resc[[jj]] <- lam_goles_jug[[jj]] * fac_B

    p_at_least_one_goal <- 1 - exp(-lam_total)
    sum_lam_obs <- sum(unlist(lam_resc))

    if (lam_total > 0) {
      # Cada jugador observado: P(j es primero) = (λ_j / λ_TOTAL) × P(≥1 gol)
      for (jj in names(lam_resc)) {
        lam_j <- lam_resc[[jj]]
        p_first <- (lam_j / lam_total) * p_at_least_one_goal
        push(jj, "primer_goleador", "si", "-", p_first)
      }
      # "otro_jugador" = masa restante de jugadores sin telemetría
      p_otro <- ((lam_total - sum_lam_obs) / lam_total) * p_at_least_one_goal
      push("otro_jugador", "primer_goleador", "si", "-", p_otro)
      # "no_goal" = no se marca ningún gol (incluye 0-0)
      push("ninguno", "primer_goleador", "no_goal", "-", exp(-lam_total))
    }
  }

  if (length(filas) == 0) return(NULL)
  rbindlist(filas)
}


###############################################################################
# BLOQUE 8: ejecución completa sobre los 72 partidos + escritura de los 4 CSV
###############################################################################

cat("\n[8] Ejecutando predicción sobre los 72 partidos del Mundial...\n")
t0 <- Sys.time()

all_filas <- list()
for (pi in seq_len(nrow(pred))) {
  fila <- pred[pi]
  pid <- fila$partido_id; fecha <- as.character(fila$fecha)
  eA <- fila$equipo_a; eB <- fila$equipo_b

  pool_A <- construir_pool(eA, eB, stats, vecinos_por_eq, fuerza_map)
  pool_B <- construir_pool(eB, eA, stats, vecinos_por_eq, fuerza_map)

  # ⚠ MEJORA #2: ajustar μ por calidad del rival HISTÓRICO del pool al
  # nivel del rival TARGET de este partido. Aplicado SOLO a las 4 métricas
  # sensibles al rival (goles, total_shots, corner_kicks, expected_goals);
  # el resto (faltas, tackles, recoveries, free_kicks, throw-ins, amarillas)
  # quedan intactas porque son métricas de estilo, no de calidad.
  f_a <- fuerza_map[eA]; if (is.na(f_a)) f_a <- 0
  f_b <- fuerza_map[eB]; if (is.na(f_b)) f_b <- 0
  pool_A <- ajustar_pool_por_calidad_rival(pool_A, f_b, fuerza_map,
                                          METRICAS_QOO,
                                          etiqueta = sprintf("%s vs %s", eA, eB))
  pool_B <- ajustar_pool_por_calidad_rival(pool_B, f_a, fuerza_map,
                                          METRICAS_QOO,
                                          etiqueta = sprintf("%s vs %s", eB, eA))

  sims <- simular_partido_bootstrap(pool_A, pool_B, N_SIM,
                                     metricas_equipo, cols_raras_shrink,
                                     eA = eA, eB = eB)
  if (is.null(sims)) {
    cat(sprintf("  [WARN] %s sin sims (pool vacío)\n", pid)); next
  }
  res_eq <- calcular_mercados(sims, pid, fecha, eA, eB,
                              metricas_equipo, metricas_ou)
  res_j  <- mercados_jugadores_partido(pid, fecha, eA, eB, sims)
  all_filas[[pid]] <- rbindlist(list(res_eq, res_j), fill = TRUE)

  if (pi %% 12 == 0) {
    cat(sprintf("  %d/%d partidos (%.1fs)\n", pi, nrow(pred),
                as.numeric(Sys.time() - t0)))
  }
}
predicciones <- rbindlist(all_filas, fill = TRUE)
cat(sprintf("  Predicción completa en %.1fs. Total filas: %d\n",
            as.numeric(Sys.time() - t0), nrow(predicciones)))

# 8.1 Sanity checks globales
cat("\n[SANITY GLOBAL]\n")
cat("  Partidos cubiertos:", uniqueN(predicciones$partido_id), "(esperado 72)\n")
cat("  Mercados únicos:", uniqueN(predicciones$mercado), "\n")
print(predicciones[, .N, by = mercado][order(-N)])

cat("\n  Rango de probabilidades: [",
    min(predicciones$probabilidad), ",",
    max(predicciones$probabilidad), "]\n")

# 1X2 suma 1 para cada partido
check_1x2 <- predicciones[mercado == "1X2",
                          .(suma = round(sum(probabilidad), 4)),
                          by = partido_id]
cat("  Partidos con 1X2 NO sumando 1:",
    nrow(check_1x2[abs(suma - 1) > 0.01]), "\n")

# BTTS suma 1
check_btts <- predicciones[mercado == "btts",
                           .(suma = round(sum(probabilidad), 4)),
                           by = partido_id]
cat("  Partidos con BTTS NO sumando 1:",
    nrow(check_btts[abs(suma - 1) > 0.01]), "\n")

# Probabilidades >0.99 en mercados abiertos (no en O/U muy alejados)
abusivos <- predicciones[mercado %in% c("1X2", "btts", "ambos_amarilla",
                                         "roja_partido") &
                          probabilidad > 0.99]
cat("  Probabilidades >0.99 en mercados abiertos (debería ser pocos):",
    nrow(abusivos), "\n")
if (nrow(abusivos) > 0) print(head(abusivos))

# Ejemplo de un partido completo: MEX_RSA y SEN_FRA
cat("\n[EJEMPLO] MEX_RSA, mercados clave:\n")
print(predicciones[partido_id == "MEX_RSA" &
                    mercado %in% c("1X2", "btts", "mitad_mas_goles",
                                    "doble_oportunidad", "intervalo_goles")])

# 8.2 Escritura de los 4 CSV de salida
cat("\n[9] Escribiendo CSV de salida...\n")

# predicciones_largo.csv (formato largo)
fout1 <- "predicciones_largo.csv"
fwrite(predicciones, fout1, sep = ";", dec = ",", bom = TRUE, na = "")
cat("  Escrito:", fout1, "(", nrow(predicciones), "filas )\n")

# predicciones_resumen.csv: formato ancho con mercados clave
resumen_filas <- predicciones[mercado == "1X2"][, .(
  partido_id, fecha, equipo_a, equipo_b,
  prob_gana_A = probabilidad[evento_o_jugador == "gana_A"],
  prob_empate = probabilidad[evento_o_jugador == "empate"],
  prob_gana_B = probabilidad[evento_o_jugador == "gana_B"]
), by = partido_id]
resumen_filas[, partido_id := NULL]  # evita la duplicación que crea by

# Sí, recreo desde cero con un cast más limpio
# Capa B (defensa): merge con all.x = TRUE en cada join para que el resumen
# NUNCA pierda un partido por la ausencia de una línea O/U concreta. Si la
# línea 2.5 de goles o 9.5 de córners no existe para un partido (porque la
# media cayó muy fuera del rango típico), queda como NA en lugar de eliminar
# la fila entera. Resuelve además el caso baseline silencioso: si el cliente
# añade equipos cuyos pools predicen córners <5 o >15, no se rompe el CSV.
res_w_1x2 <- dcast(predicciones[mercado == "1X2"],
                   partido_id + fecha + equipo_a + equipo_b ~ evento_o_jugador,
                   value.var = "probabilidad")
setnames(res_w_1x2,
         old = c("gana_A","empate","gana_B"),
         new = c("p_1","p_X","p_2"))

res_btts <- dcast(predicciones[mercado == "btts"],
                  partido_id ~ evento_o_jugador, value.var = "probabilidad")
setnames(res_btts, old = c("si","no"), new = c("btts_si","btts_no"))

# Goles TOTAL O/U 2.5
res_ou25 <- predicciones[mercado == "goles" & ambito == "TOTAL" &
                          linea_o_target == 2.5]
res_ou25 <- dcast(res_ou25, partido_id ~ evento_o_jugador,
                  value.var = "probabilidad")
setnames(res_ou25, old = c("over","under"),
         new = c("goles_over_2_5","goles_under_2_5"))

# Córners TOTAL O/U 9.5
res_co95 <- predicciones[mercado == "corner_kicks" & ambito == "TOTAL" &
                          linea_o_target == 9.5]
res_co95 <- dcast(res_co95, partido_id ~ evento_o_jugador,
                  value.var = "probabilidad")
setnames(res_co95, old = c("over","under"),
         new = c("corners_over_9_5","corners_under_9_5"))

# merge defensivo: res_w_1x2 es la "tabla maestra" (todos los partidos).
# Cualquier ausencia de btts/ou25/co95 entra como NA, NO elimina filas.
resumen <- merge(res_w_1x2, res_btts, by = "partido_id", all.x = TRUE)
resumen <- merge(resumen,   res_ou25, by = "partido_id", all.x = TRUE)
resumen <- merge(resumen,   res_co95, by = "partido_id", all.x = TRUE)

# Si por la mejora #2 córners 9.5 quedó fuera del rango de líneas para algún
# partido, las columnas existen pero ese partido tiene NA. Avisar.
n_nas_co95 <- sum(is.na(resumen$corners_over_9_5))
if (n_nas_co95 > 0) {
  cat(sprintf("  [INFO] %d partido(s) sin línea córners 9.5 (media fuera del rango típico)\n",
              n_nas_co95))
}
# Reordenar columnas en orden lógico
setcolorder(resumen, c("partido_id", "fecha", "equipo_a", "equipo_b",
                       "p_1", "p_X", "p_2",
                       "btts_si", "btts_no",
                       "goles_over_2_5", "goles_under_2_5",
                       "corners_over_9_5", "corners_under_9_5"))

fout2 <- "predicciones_resumen.csv"
fwrite(resumen, fout2, sep = ";", dec = ",", bom = TRUE, na = "")
cat("  Escrito:", fout2, "(", nrow(resumen), "filas )\n")

# debug_perfiles.csv (limitado a equipos del Mundial)
deb_perf <- debug_perfiles[equipo %in% equipos_mundial]
fout3 <- "debug_perfiles.csv"
fwrite(deb_perf, fout3, sep = ";", dec = ",", bom = TRUE, na = "")
cat("  Escrito:", fout3, "(", nrow(deb_perf), "filas )\n")

# debug_knn.csv
fout4 <- "debug_knn.csv"
fwrite(debug_knn, fout4, sep = ";", dec = ",", bom = TRUE, na = "")
cat("  Escrito:", fout4, "(", nrow(debug_knn), "filas )\n")

cat("\n[FIN] Predicción completada.\n")

# ------------------------ [REGRESIÓN-CHECK] --------------------------------
# Bloque de logging para detectar regresiones silenciosas entre versiones.
# Imprime: tiempo total, conteo de filas por output, sha256 de cada CSV.
cat("\n[REGRESIÓN-CHECK]\n")
t_total <- as.numeric(difftime(Sys.time(), T0_GLOBAL, units = "secs"))
cat(sprintf("  tiempo_total_seg : %.2f\n", t_total))
cat(sprintf("  partidos_procesados : %d (esperado 72)\n",
            uniqueN(predicciones$partido_id)))

csv_outputs <- c("predicciones_largo.csv",
                 "predicciones_resumen.csv",
                 "debug_perfiles.csv",
                 "debug_knn.csv")
for (f in csv_outputs) {
  if (file.exists(f)) {
    n_filas <- length(readLines(f, warn = FALSE)) - 1L
    h <- digest::digest(file = f, algo = "sha256")
    cat(sprintf("  %-28s  filas=%6d  sha256=%s\n", f, n_filas, h))
  } else {
    cat(sprintf("  %-28s  AUSENTE\n", f))
  }
}
cat("[/REGRESIÓN-CHECK]\n")
