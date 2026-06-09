// web/lib/markets-ui.ts
// Agrupado y etiquetas (es-ES) de los mercados O/U de equipo para la vista de
// detalle de partido. Las claves `mercado` coinciden con la columna `mercado`
// de la tabla Market en la DB. El campo `key` es la categoría (chip) a la que
// pertenece la sección.

export type MarketSection = {
  key: string;
  titulo: string;
  mercados: { mercado: string; label: string }[];
};

export const SECTIONS: MarketSection[] = [
  {
    key: "goles",
    titulo: "Goles",
    mercados: [{ mercado: "goles", label: "Goles" }],
  },
  {
    key: "tiros",
    titulo: "Tiros",
    mercados: [
      { mercado: "total_shots", label: "Tiros totales" },
      { mercado: "shots_on_target", label: "Tiros a puerta" },
      { mercado: "shots_off_target", label: "Tiros fuera" },
      { mercado: "shots_inside_box", label: "Tiros dentro del área" },
      { mercado: "shots_outside_box", label: "Tiros desde fuera del área" },
      { mercado: "blocked_shots", label: "Tiros bloqueados" },
    ],
  },
  {
    key: "corners",
    titulo: "Córners y balón parado",
    mercados: [
      { mercado: "corner_kicks", label: "Córners" },
      { mercado: "free_kicks", label: "Tiros libres" },
      { mercado: "goal_kicks", label: "Saques de puerta" },
      { mercado: "throw-ins", label: "Saques de banda" },
    ],
  },
  {
    key: "disciplina",
    titulo: "Disciplina",
    mercados: [
      { mercado: "yellow_cards", label: "Tarjetas amarillas" },
      { mercado: "fouls", label: "Faltas" },
      { mercado: "offsides", label: "Fueras de juego" },
    ],
  },
  {
    key: "posesion",
    titulo: "Posesión y defensa",
    mercados: [
      { mercado: "passes", label: "Pases" },
      { mercado: "accurate_passes", label: "Pases precisos" },
      { mercado: "tackles", label: "Entradas" },
    ],
  },
  {
    key: "porteria",
    titulo: "Portería",
    mercados: [{ mercado: "goalkeeper_saves", label: "Paradas del portero" }],
  },
];

export type Categoria = { key: string; label: string };

// Orden de los chips. "principales" (DO + BTTS) y "todos" no son secciones O/U:
// se gestionan aparte en MatchMarkets. El resto casa 1:1 con SECTIONS por `key`.
export const CATEGORIAS: Categoria[] = [
  { key: "principales", label: "Principales" },
  { key: "todos", label: "Todos" },
  { key: "goles", label: "Goles" },
  { key: "tiros", label: "Tiros" },
  { key: "corners", label: "Córners y balón parado" },
  { key: "disciplina", label: "Disciplina" },
  { key: "posesion", label: "Posesión y defensa" },
  { key: "porteria", label: "Portería" },
  { key: "jugadores", label: "Jugadores" },
];
