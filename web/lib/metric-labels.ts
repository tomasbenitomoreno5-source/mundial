// Etiquetas y descripciones (es-ES) de las métricas de equipo, compartidas por
// la tabla de perfiles y el historial.

export const METRIC_LABELS: Record<string, string> = {
  // Mercados de resultado (no son métricas de conteo, pero comparten lookup).
  "1X2": "Resultado (1X2)",
  doble_oportunidad: "Doble oportunidad",
  btts: "Ambos marcan",
  // Métricas de equipo / mercados O/U.
  goles: "Goles",
  expected_goals: "Goles esperados (xG)",
  total_shots: "Tiros totales",
  shots_on_target: "Tiros a puerta",
  shots_off_target: "Tiros fuera",
  shots_inside_box: "Tiros dentro del área",
  shots_outside_box: "Tiros desde fuera del área",
  blocked_shots: "Tiros bloqueados",
  ball_possession: "Posesión (%)",
  corner_kicks: "Córners",
  free_kicks: "Tiros libres",
  goal_kicks: "Saques de puerta",
  "throw-ins": "Saques de banda",
  fouls: "Faltas",
  yellow_cards: "Tarjetas amarillas",
  red_cards: "Tarjetas rojas",
  offsides: "Fueras de juego",
  passes: "Pases",
  accurate_passes: "Pases precisos",
  tackles: "Entradas",
  goalkeeper_saves: "Paradas del portero",
};

export const METRIC_DESC: Record<string, string> = {
  goles: "Goles marcados.",
  expected_goals: "Goles esperados (xG): suma de la calidad de las ocasiones.",
  total_shots: "Tiros totales intentados.",
  shots_on_target: "Tiros que van a portería.",
  shots_off_target: "Tiros que se van fuera.",
  blocked_shots: "Tiros bloqueados por un rival.",
  shots_inside_box: "Tiros desde dentro del área.",
  shots_outside_box: "Tiros desde fuera del área.",
  ball_possession: "Porcentaje de posesión del balón.",
  corner_kicks: "Saques de esquina a favor.",
  fouls: "Faltas cometidas.",
  free_kicks: "Tiros libres a favor.",
  yellow_cards: "Tarjetas amarillas recibidas.",
  red_cards: "Tarjetas rojas recibidas.",
  offsides: "Fueras de juego señalados.",
  passes: "Pases intentados.",
  accurate_passes: "Pases completados con éxito.",
  long_balls: "Pases largos.",
  crosses: "Centros al área.",
  tackles: "Entradas para robar el balón.",
  total_tackles: "Entradas totales.",
  tackles_won: "Entradas ganadas.",
  interceptions: "Balones interceptados.",
  recoveries: "Balones recuperados.",
  clearances: "Despejes.",
  goalkeeper_saves: "Paradas del portero.",
  total_saves: "Paradas totales.",
  big_chances: "Ocasiones claras de gol generadas.",
  big_chances_scored: "Ocasiones claras transformadas en gol.",
  big_chances_missed: "Ocasiones claras falladas.",
  duels: "Duelos disputados.",
  ground_duels: "Duelos por el suelo.",
  aerial_duels: "Duelos aéreos.",
  dribbles: "Regates intentados.",
  through_balls: "Pases en profundidad.",
  touches_in_penalty_area: "Toques en el área rival.",
  final_third_entries: "Entradas al último tercio del campo.",
  dispossessed: "Veces que perdió el balón en un duelo.",
};

/** Etiqueta legible de una métrica (con mayúscula inicial). */
export function metricLabel(metrica: string): string {
  const l = METRIC_LABELS[metrica] ?? metrica.replace(/_/g, " ");
  return l.charAt(0).toUpperCase() + l.slice(1);
}

/** Formatea un valor numérico de métrica (entero o 2 decimales; – si falta). */
export function fmtMetric(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "–";
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}
