// Catálogo de mercados de jugador. El seed los genera (Poisson sobre la media
// por partido del jugador) y la web los renderiza recorriendo esta lista.
// Añadir un mercado nuevo = añadir una entrada aquí (la métrica debe existir en
// la telemetría / metrics JSON).
//
//  - tipo "binary": sí/no (P(métrica >= 1) = 1 - e^-media).
//  - tipo "ou":     Over/Under con líneas semienteras alrededor de la media.
//  - `metric` "__goal_or_assist__" es especial: usa goals + goalAssist.
//  - `cat` agrupa los O/U en la ficha del partido (chips).

export type PlayerMarketDef = {
  key: string;
  metric: string;
  label: string;
  tipo: "binary" | "ou";
  cat?: string;
};

// Orden de las categorías de O/U.
export const PLAYER_MARKET_CATS = [
  "Ataque",
  "Pase",
  "Regate",
  "Defensa",
  "Disciplina",
  "Portería",
] as const;

export const PLAYER_MARKETS: PlayerMarketDef[] = [
  // --- Sí/No ---
  { key: "anytime_scorer", metric: "goals", label: "Marca gol", tipo: "binary" },
  { key: "assist", metric: "goalAssist", label: "Da asistencia", tipo: "binary" },
  { key: "goal_or_assist", metric: "__goal_or_assist__", label: "Gol o asistencia", tipo: "binary" },
  { key: "big_chance_created", metric: "bigChanceCreated", label: "Crea ocasión clara", tipo: "binary" },
  { key: "penalty_won", metric: "penaltyWon", label: "Provoca penalti", tipo: "binary" },
  { key: "yellow_card", metric: "__yellow_card__", label: "Ve amarilla", tipo: "binary" },

  // --- Ataque ---
  { key: "shots", metric: "totalShots", label: "Tiros", tipo: "ou", cat: "Ataque" },
  { key: "shots_on_target", metric: "onTargetScoringAttempt", label: "Tiros a puerta", tipo: "ou", cat: "Ataque" },
  { key: "shots_off_target", metric: "shotOffTarget", label: "Tiros fuera", tipo: "ou", cat: "Ataque" },
  { key: "shots_blocked", metric: "blockedScoringAttempt", label: "Tiros bloqueados", tipo: "ou", cat: "Ataque" },
  { key: "big_chances_missed", metric: "bigChanceMissed", label: "Ocasiones falladas", tipo: "ou", cat: "Ataque" },

  // --- Pase ---
  { key: "passes", metric: "totalPass", label: "Pases", tipo: "ou", cat: "Pase" },
  { key: "accurate_passes", metric: "accuratePass", label: "Pases precisos", tipo: "ou", cat: "Pase" },
  { key: "key_passes", metric: "keyPass", label: "Pases clave", tipo: "ou", cat: "Pase" },
  { key: "crosses", metric: "totalCross", label: "Centros", tipo: "ou", cat: "Pase" },
  { key: "accurate_crosses", metric: "accurateCross", label: "Centros precisos", tipo: "ou", cat: "Pase" },
  { key: "long_balls", metric: "totalLongBalls", label: "Pases largos", tipo: "ou", cat: "Pase" },

  // --- Regate / conducción ---
  { key: "dribbles", metric: "wonContest", label: "Regates completados", tipo: "ou", cat: "Regate" },
  { key: "dribbles_att", metric: "totalContest", label: "Regates intentados", tipo: "ou", cat: "Regate" },
  { key: "touches", metric: "touches", label: "Toques", tipo: "ou", cat: "Regate" },

  // --- Defensa ---
  { key: "tackles", metric: "totalTackle", label: "Entradas", tipo: "ou", cat: "Defensa" },
  { key: "won_tackles", metric: "wonTackle", label: "Entradas ganadas", tipo: "ou", cat: "Defensa" },
  { key: "interceptions", metric: "interceptionWon", label: "Intercepciones", tipo: "ou", cat: "Defensa" },
  { key: "clearances", metric: "totalClearance", label: "Despejes", tipo: "ou", cat: "Defensa" },
  { key: "recoveries", metric: "ballRecovery", label: "Recuperaciones", tipo: "ou", cat: "Defensa" },
  { key: "duels_won", metric: "duelWon", label: "Duelos ganados", tipo: "ou", cat: "Defensa" },
  { key: "aerials_won", metric: "aerialWon", label: "Duelos aéreos ganados", tipo: "ou", cat: "Defensa" },
  { key: "blocks", metric: "outfielderBlock", label: "Bloqueos", tipo: "ou", cat: "Defensa" },

  // --- Disciplina / pérdidas ---
  { key: "fouls", metric: "fouls", label: "Faltas cometidas", tipo: "ou", cat: "Disciplina" },
  { key: "fouled", metric: "wasFouled", label: "Faltas recibidas", tipo: "ou", cat: "Disciplina" },
  { key: "offsides", metric: "totalOffside", label: "Fueras de juego", tipo: "ou", cat: "Disciplina" },
  { key: "possession_lost", metric: "possessionLostCtrl", label: "Pérdidas de balón", tipo: "ou", cat: "Disciplina" },
  { key: "dispossessed", metric: "dispossessed", label: "Robos recibidos", tipo: "ou", cat: "Disciplina" },

  // --- Portería ---
  { key: "saves", metric: "saves", label: "Paradas", tipo: "ou", cat: "Portería" },
];

export const PLAYER_MARKETS_BINARY = PLAYER_MARKETS.filter((m) => m.tipo === "binary");
export const PLAYER_MARKETS_OU = PLAYER_MARKETS.filter((m) => m.tipo === "ou");
