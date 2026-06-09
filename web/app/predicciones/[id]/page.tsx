import Link from "next/link";
import { notFound } from "next/navigation";

import { MatchMarkets } from "@/components/MatchMarkets";
import type { OULine } from "@/components/OverUnderTable";
import { ScoreHeatmap } from "@/components/ScoreHeatmap";
import { outcome, pred1x2 } from "@/lib/accuracy";
import { bestBets } from "@/lib/best-bets";
import { SECTIONS } from "@/lib/markets-ui";
import { PLAYER_MARKETS } from "@/lib/player-markets";
import { ProbBar } from "@/components/ProbBar";
import { flag } from "@/lib/flags";
import { formatFecha, pct } from "@/lib/format";
import { teamES } from "@/lib/teams";
import {
  getMatch,
  getMatchIds,
  getPlayerMarkets,
  getScoreProbs,
  type MarketRow,
  type PlayerMarketRow,
} from "@/lib/queries";

export const revalidate = 1800; // ISR: refleja el re-seed sin rebuild

export async function generateStaticParams() {
  const ids = await getMatchIds();
  return ids.map((id) => ({ id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const match = await getMatch(id);
  if (!match) return {};
  return {
    title: `${teamES(match.teamAName)} vs ${teamES(match.teamBName)} · Mundial.Predict`,
  };
}

function ouLinesByScope(markets: MarketRow[], mercado: string) {
  const byScope = (ambito: string): OULine[] =>
    markets
      .filter(
        (m) =>
          m.mercado === mercado &&
          m.ambito === ambito &&
          m.evento === "over",
      )
      .map((m) => ({ linea: m.linea, over: m.probabilidad }))
      .sort((a, b) => parseFloat(a.linea) - parseFloat(b.linea));
  return {
    total: byScope("TOTAL"),
    teamA: byScope("A"),
    teamB: byScope("B"),
  };
}

function evento(
  markets: MarketRow[],
  mercado: string,
  ev: string,
): number | null {
  const m = markets.find((x) => x.mercado === mercado && x.evento === ev);
  return m ? m.probabilidad : null;
}

export default async function MatchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [match, playerMarkets, scoreProbs] = await Promise.all([
    getMatch(id),
    getPlayerMarkets(id),
    getScoreProbs(id),
  ]);
  if (!match) notFound();

  const { markets } = match;

  const principales = {
    doble: {
      "1X": evento(markets, "doble_oportunidad", "1X"),
      X2: evento(markets, "doble_oportunidad", "X2"),
      "12": evento(markets, "doble_oportunidad", "12"),
    },
    btts: {
      si: evento(markets, "btts", "si"),
      no: evento(markets, "btts", "no"),
    },
  };

  const secciones = SECTIONS.map((section) => ({
    key: section.key,
    titulo: section.titulo,
    mercados: section.mercados.map(({ mercado, label }) => ({
      mercado,
      label,
      ...ouLinesByScope(markets, mercado),
    })),
  }));

  // Agrupar mercados de jugador por jugador.
  const ouJugador = (rows: PlayerMarketRow[], mercado: string): OULine[] =>
    rows
      .filter((r) => r.mercado === mercado && r.evento === "over")
      .map((r) => ({ linea: r.linea, over: r.probabilidad }))
      .sort((a, b) => parseFloat(a.linea) - parseFloat(b.linea));
  const siJugador = (rows: PlayerMarketRow[], mercado: string): number | null =>
    rows.find((r) => r.mercado === mercado && r.evento === "si")
      ?.probabilidad ?? null;
  const porJugador = new Map<string, PlayerMarketRow[]>();
  for (const pm of playerMarkets) {
    if (!porJugador.has(pm.player)) porJugador.set(pm.player, []);
    porJugador.get(pm.player)!.push(pm);
  }
  const jugadores = [...porJugador.entries()]
    .map(([player, rows]) => {
      const binarios: Record<string, number | null> = {};
      const ou: Record<string, OULine[]> = {};
      for (const def of PLAYER_MARKETS) {
        if (def.tipo === "binary") binarios[def.key] = siJugador(rows, def.key);
        else ou[def.key] = ouJugador(rows, def.key);
      }
      return { player, team: rows[0].team, binarios, ou };
    })
    .sort(
      (a, b) =>
        (b.binarios["anytime_scorer"] ?? 0) -
        (a.binarios["anytime_scorer"] ?? 0),
    );

  const topScorer =
    jugadores[0]?.binarios["anytime_scorer"] != null
      ? {
          player: jugadores[0].player,
          prob: jugadores[0].binarios["anytime_scorer"]!,
        }
      : null;
  const destacadas = bestBets(
    markets,
    teamES(match.teamAName),
    teamES(match.teamBName),
    topScorer,
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <Link
        href="/predicciones"
        className="text-sm text-slate-500 hover:text-slate-900"
      >
        ← Todos los partidos
      </Link>

      {/* Cabecera del partido */}
      <div className="mt-4 rounded-3xl bg-white p-6 ring-1 ring-slate-200 sm:p-8">
        <p className="text-sm font-medium text-slate-400">
          {formatFecha(match.date)}
        </p>
        <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          <TeamHead
            name={match.teamAName}
            prob={match.p1}
            side="left"
            accent="indigo"
          />
          <div className="text-center">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Empate
            </div>
            <div className="text-lg font-bold text-slate-500">
              {pct(match.pX)}
            </div>
          </div>
          <TeamHead
            name={match.teamBName}
            prob={match.p2}
            side="right"
            accent="rose"
          />
        </div>
        <div className="mt-6">
          <ProbBar p1={match.p1} pX={match.pX} p2={match.p2} />
        </div>
      </div>

      {match.settled && match.scoreA != null && match.scoreB != null && (
        <div className="mt-4 rounded-2xl bg-white p-4 ring-1 ring-slate-200">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Resultado final
            </span>
            <span className="text-2xl font-black tabular-nums">
              {match.scoreA}–{match.scoreB}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {pred1x2(match.p1, match.pX, match.p2) ===
            outcome(match.scoreA, match.scoreB)
              ? "✓ El modelo acertó el 1X2."
              : "✗ El modelo falló el 1X2."}
          </p>
        </div>
      )}

      {destacadas.length > 0 && (
        <section className="mt-4">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Apuestas destacadas
          </h2>
          <div className="flex flex-wrap gap-2">
            {destacadas.map((d, i) => (
              <span
                key={i}
                className="rounded-full bg-white px-3 py-1.5 text-sm ring-1 ring-slate-200"
              >
                {d.label}{" "}
                <span className="font-bold text-indigo-600">{pct(d.prob)}</span>
              </span>
            ))}
          </div>
        </section>
      )}

      {scoreProbs.length > 0 && (
        <section className="mt-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Mapa de marcadores
          </h2>
          <ScoreHeatmap
            probs={scoreProbs}
            teamA={match.teamAName}
            teamB={match.teamBName}
          />
        </section>
      )}

      <MatchMarkets
        principales={principales}
        secciones={secciones}
        jugadores={jugadores}
        flagA={flag(match.teamAName)}
        flagB={flag(match.teamBName)}
      />
    </div>
  );
}

function TeamHead({
  name,
  prob,
  side,
  accent,
}: {
  name: string;
  prob: number | null;
  side: "left" | "right";
  accent: "indigo" | "rose";
}) {
  const accentText = accent === "indigo" ? "text-indigo-600" : "text-rose-600";
  return (
    <div className={side === "right" ? "text-right" : "text-left"}>
      <div
        className={`flex items-center gap-2 sm:gap-3 ${
          side === "right" ? "flex-row-reverse" : ""
        }`}
      >
        <span className="text-3xl leading-none sm:text-4xl">{flag(name)}</span>
        <span className="text-base font-bold tracking-tight sm:text-lg">
          {teamES(name)}
        </span>
      </div>
      <div className={`mt-2 text-3xl font-black ${accentText}`}>
        {pct(prob)}
      </div>
    </div>
  );
}
