import { SECTIONS } from "@/lib/markets-ui";
import { PLAYER_MARKETS_BINARY } from "@/lib/player-markets";
import type { MarketRow } from "@/lib/queries";

const OU_LABEL: Record<string, string> = Object.fromEntries(
  SECTIONS.flatMap((s) => s.mercados.map((m) => [m.mercado, m.label])),
);

// periodo es el código FT | 1H | 2H (para filtrar por el selector de periodo).
export type Apuesta = { label: string; prob: number; periodo: string; key: string };

type JugadorLike = {
  player: string;
  binarios: Record<string, number | null>;
  ou: Record<string, { linea: string; over: number }[]>;
};

/**
 * Todas las selecciones del partido (equipo + jugador, todos los periodos) con
 * su probabilidad, usando el lado más probable en cada Over/Under. Pre-filtra a
 * ≥60% (banda útil) y cap a 300 para no inflar el payload; el filtro fino por
 * umbral lo hace el cliente.
 */
export function todasLasApuestas(
  markets: MarketRow[],
  jugadores: JugadorLike[],
  teamA: string,
  teamB: string,
): Apuesta[] {
  const out: Apuesta[] = [];
  const per = (m: MarketRow) => m.periodo ?? "FT";
  const periodos = [...new Set(markets.map(per))];
  const evP = (mercado: string, evento: string, periodo: string) =>
    markets.find(
      (m) =>
        m.mercado === mercado &&
        m.evento === evento &&
        m.ambito === "-" &&
        per(m) === periodo,
    )?.probabilidad ?? null;

  for (const p of periodos) {
    for (const [e, l] of [
      ["gana_A", `${teamA} gana`],
      ["empate", "Empate"],
      ["gana_B", `${teamB} gana`],
    ] as const) {
      const v = evP("1X2", e, p);
      if (v != null) out.push({ label: l, prob: v, periodo: p, key: `1X2|${e}|${p}` });
    }
    for (const [e, l] of [
      ["1X", `${teamA} o empate`],
      ["X2", `${teamB} o empate`],
      ["12", "No habrá empate"],
    ] as const) {
      const v = evP("doble_oportunidad", e, p);
      if (v != null) out.push({ label: l, prob: v, periodo: p, key: `do|${e}|${p}` });
    }
    const si = evP("btts", "si", p);
    const no = evP("btts", "no", p);
    if (si != null && no != null)
      out.push(
        si >= no
          ? { label: "Ambos marcan", prob: si, periodo: p, key: `btts|${p}` }
          : { label: "No marcan ambos", prob: no, periodo: p, key: `btts|${p}` },
      );
  }

  // Over/Under de equipo: una selección por línea (el lado más probable).
  for (const m of markets) {
    if (m.evento !== "over") continue;
    const over = m.probabilidad;
    const lado = over >= 0.5 ? { t: "Más de", p: over } : { t: "Menos de", p: 1 - over };
    const lbl = (OU_LABEL[m.mercado] ?? m.mercado).toLowerCase();
    const amb = m.ambito === "A" ? ` · ${teamA}` : m.ambito === "B" ? ` · ${teamB}` : "";
    out.push({
      label: `${lado.t} ${m.linea} ${lbl}${amb}`,
      prob: lado.p,
      periodo: per(m),
      key: `${m.mercado}|${m.ambito}|${per(m)}|${lado.t}`,
    });
  }

  // Mercados de jugador: solo los binarios apostables (marca gol, asistencia,
  // tarjeta…). Los O/U de jugador (tiros, recuperaciones…) NO entran aquí —
  // inundan la lista con líneas triviales; viven en la pestaña "Jugadores".
  for (const j of jugadores) {
    for (const def of PLAYER_MARKETS_BINARY) {
      const v = j.binarios[def.key];
      if (v != null)
        out.push({
          label: `${j.player} · ${def.label}`,
          prob: v,
          periodo: "FT",
          key: `${j.player}|${def.key}`,
        });
    }
  }

  // Banda útil: ≥60% y ≤99% (descarta solo el ~100% absoluto, trivial). Cap
  // alto para no perder nada de la banda; el cliente deduplica por mercado.
  return out
    .filter((a) => a.prob >= 0.6 && a.prob <= 0.99)
    .sort((a, b) => b.prob - a.prob)
    .slice(0, 800);
}
const OU_MERCADOS = [
  "goles",
  "total_shots",
  "shots_on_target",
  "corner_kicks",
  "yellow_cards",
  "fouls",
];

export type Pick = { label: string; prob: number };

/**
 * Selecciona las apuestas más "destacadas" de un partido: los picks más
 * confiados dentro de una banda útil (0.60–0.92), evitando lo trivial (>92%)
 * y los lanzamientos de moneda (<60%).
 */
export function bestBets(
  markets: MarketRow[],
  teamA: string,
  teamB: string,
  scorer?: { player: string; prob: number } | null,
): Pick[] {
  const ev = (mercado: string, evento: string, ambito = "-") =>
    markets.find(
      (m) => m.mercado === mercado && m.evento === evento && m.ambito === ambito,
    )?.probabilidad ?? null;
  const cand: Pick[] = [];

  // 1X2 (el resultado más probable)
  const x2 = [
    ["gana_A", `${teamA} gana`],
    ["empate", "Empate"],
    ["gana_B", `${teamB} gana`],
  ] as const;
  let mejor1x2: Pick | null = null;
  for (const [e, l] of x2) {
    const p = ev("1X2", e);
    if (p != null && (!mejor1x2 || p > mejor1x2.prob)) mejor1x2 = { label: l, prob: p };
  }
  if (mejor1x2) cand.push(mejor1x2);

  // Doble oportunidad
  for (const [e, l] of [
    ["1X", `${teamA} o empate`],
    ["X2", `${teamB} o empate`],
    ["12", "No habrá empate"],
  ] as const) {
    const p = ev("doble_oportunidad", e);
    if (p != null) cand.push({ label: l, prob: p });
  }

  // BTTS
  const si = ev("btts", "si");
  const no = ev("btts", "no");
  if (si != null && no != null)
    cand.push(
      si >= no
        ? { label: "Ambos equipos marcan", prob: si }
        : { label: "No marcan ambos", prob: no },
    );

  // Over/Under (total): la línea útil más confiada por métrica
  for (const mer of OU_MERCADOS) {
    let best: Pick | null = null;
    for (const m of markets) {
      if (
        m.mercado === mer &&
        m.ambito === "TOTAL" &&
        (m.evento === "over" || m.evento === "under") &&
        m.probabilidad <= 0.92 &&
        (!best || m.probabilidad > best.prob)
      ) {
        best = {
          label: `${m.evento === "over" ? "Más de" : "Menos de"} ${m.linea} ${(
            OU_LABEL[mer] ?? mer
          ).toLowerCase()}`,
          prob: m.probabilidad,
        };
      }
    }
    if (best) cand.push(best);
  }

  if (scorer && scorer.prob >= 0.45)
    cand.push({ label: `${scorer.player} marca gol`, prob: scorer.prob });

  return cand
    .filter((c) => c.prob >= 0.6 && c.prob <= 0.92)
    .sort((a, b) => b.prob - a.prob)
    .slice(0, 6);
}
