import { SECTIONS } from "@/lib/markets-ui";
import type { MarketRow } from "@/lib/queries";

const OU_LABEL: Record<string, string> = Object.fromEntries(
  SECTIONS.flatMap((s) => s.mercados.map((m) => [m.mercado, m.label])),
);
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
