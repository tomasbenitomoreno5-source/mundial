// Categorías de columnas para la tabla de historial (stats_final tiene ~50
// métricas). Cada chip muestra solo un subconjunto, para que cada vista sea
// estrecha y legible. `cols: null` = todas las columnas disponibles.

export type HistCategoria = { key: string; label: string; cols: string[] | null };

export const HIST_CATEGORIAS: HistCategoria[] = [
  {
    key: "resumen",
    label: "Resumen",
    cols: [
      "goles",
      "expected_goals",
      "total_shots",
      "shots_on_target",
      "ball_possession",
      "corner_kicks",
      "fouls",
      "yellow_cards",
    ],
  },
  {
    key: "ataque",
    label: "Ataque",
    cols: [
      "goles",
      "expected_goals",
      "big_chances",
      "big_chances_scored",
      "big_chances_missed",
      "touches_in_penalty_area",
      "through_balls",
      "final_third_entries",
      "dribbles",
      "crosses",
    ],
  },
  {
    key: "tiros",
    label: "Tiros",
    cols: [
      "total_shots",
      "shots_on_target",
      "shots_off_target",
      "blocked_shots",
      "shots_inside_box",
      "shots_outside_box",
      "hit_woodwork",
    ],
  },
  {
    key: "posesion",
    label: "Posesión",
    cols: [
      "ball_possession",
      "passes",
      "accurate_passes",
      "long_balls",
      "throw-ins",
      "dispossessed",
    ],
  },
  {
    key: "disciplina",
    label: "Disciplina",
    cols: [
      "fouls",
      "yellow_cards",
      "red_cards",
      "offsides",
      "free_kicks",
      "fouled_in_final_third",
    ],
  },
  {
    key: "defensa",
    label: "Defensa",
    cols: [
      "total_tackles",
      "tackles_won",
      "interceptions",
      "recoveries",
      "clearances",
      "duels",
      "ground_duels",
      "aerial_duels",
    ],
  },
  {
    key: "porteria",
    label: "Portería",
    cols: [
      "goalkeeper_saves",
      "total_saves",
      "big_saves",
      "high_claims",
      "punches",
      "goal_kicks",
      "penalty_saves",
      "goals_prevented",
    ],
  },
  { key: "todas", label: "Todas", cols: null },
];
