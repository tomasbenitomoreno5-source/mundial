import Link from "next/link";
import { notFound } from "next/navigation";

import { MatchMarkets } from "@/components/MatchMarkets";
import type { OULine } from "@/components/OverUnderTable";
import { ScoreHeatmap } from "@/components/ScoreHeatmap";
import { outcome, pred1x2 } from "@/lib/accuracy";
import { todasLasApuestas } from "@/lib/best-bets";
import { SECTIONS } from "@/lib/markets-ui";
import { PLAYER_MARKETS } from "@/lib/player-markets";
import { ProbBar } from "@/components/ProbBar";
import { flag } from "@/lib/flags";
import { formatFecha, formatHora, pct } from "@/lib/format";
import { teamES } from "@/lib/teams";
import {
  getConvocatoria,
  getMatch,
  getMatchIds,
  getPlayerMarkets,
  getScoreProbs,
  type MarketRow,
  type PlayerMarketRow,
} from "@/lib/queries";

export const revalidate = 60; // ISR: refleja el re-seed sin rebuild

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

function ouLinesByScope(
  markets: MarketRow[],
  mercado: string,
  periodo = "FT",
) {
  const byScope = (ambito: string): OULine[] =>
    markets
      .filter(
        (m) =>
          m.mercado === mercado &&
          m.ambito === ambito &&
          m.evento === "over" &&
          (m.periodo ?? "FT") === periodo,
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
  periodo = "FT",
): number | null {
  const m = markets.find(
    (x) =>
      x.mercado === mercado &&
      x.evento === ev &&
      (x.periodo ?? "FT") === periodo,
  );
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

  const seccionesDe = (periodo: string) =>
    SECTIONS.map((section) => ({
      key: section.key,
      titulo: section.titulo,
      mercados: section.mercados.map(({ mercado, label }) => ({
        mercado,
        label,
        ...ouLinesByScope(markets, mercado, periodo),
      })),
    }));
  const secciones = seccionesDe("FT");
  // Por periodo: solo se ofrecen FT/1H/2H para las métricas viables por mitad.
  const seccionesPorPeriodo = {
    FT: secciones,
    "1H": seccionesDe("1H"),
    "2H": seccionesDe("2H"),
  };
  // ¿Hay datos por mitad? (algún mercado 1H/2H con líneas)
  const hayMitades = ["1H", "2H"].some((p) =>
    seccionesPorPeriodo[p as "1H" | "2H"].some((s) =>
      s.mercados.some((m) => m.total.length || m.teamA.length || m.teamB.length),
    ),
  );
  // Resultado de 1ª parte (1X2 + BTTS HT).
  const resultado1h = {
    p1: evento(markets, "1X2", "gana_A", "1H"),
    pX: evento(markets, "1X2", "empate", "1H"),
    p2: evento(markets, "1X2", "gana_B", "1H"),
    bttsSi: evento(markets, "btts", "si", "1H"),
    bttsNo: evento(markets, "btts", "no", "1H"),
  };

  // Agrupar mercados de jugador por jugador.
  const ouJugador = (rows: PlayerMarketRow[], mercado: string): OULine[] =>
    rows
      .filter((r) => r.mercado === mercado && r.evento === "over")
      .map((r) => ({ linea: r.linea, over: r.probabilidad }))
      .sort((a, b) => parseFloat(a.linea) - parseFloat(b.linea));
  const siJugador = (rows: PlayerMarketRow[], mercado: string): number | null =>
    rows.find((r) => r.mercado === mercado && r.evento === "si")
      ?.probabilidad ?? null;
  // "otro_jugador" y "ninguno" son cajones del mercado de primer goleador (que
  // otro/nadie marque), no jugadores reales: no se listan como tales.
  const NO_JUGADORES = new Set(["otro_jugador", "ninguno"]);
  const porJugador = new Map<string, PlayerMarketRow[]>();
  for (const pm of playerMarkets) {
    if (NO_JUGADORES.has(pm.player)) continue;
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

  // Convocados SIN telemetría → se listan como "sin datos" (plantilla completa).
  const conMercado = new Set(jugadores.map((j) => j.player));
  const conv = await getConvocatoria([match.teamAName, match.teamBName]);
  const sinDatos = conv
    .filter((c) => !conMercado.has(c.jugador))
    .map((c) => ({ player: c.jugador, team: c.equipo }));

  const apuestas = todasLasApuestas(
    markets,
    jugadores,
    teamES(match.teamAName),
    teamES(match.teamBName),
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
          {formatHora(match.kickoff) && ` · ${formatHora(match.kickoff)} (hora España)`}
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

      {/* Árbitro designado */}
      <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl bg-white p-4 ring-1 ring-slate-200">
        <span className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Árbitro
        </span>
        {match.refereeSofaId ? (
          <Link
            href={`/arbitros/${match.refereeSofaId}`}
            className="flex items-center gap-2 text-sm font-bold text-indigo-600 hover:underline"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`https://img.sofascore.com/api/v1/referee/${match.refereeSofaId}/image`}
              alt={match.refereeName ?? "Árbitro"}
              width={28}
              height={28}
              className="h-7 w-7 rounded-full bg-slate-100 object-cover ring-1 ring-slate-200"
              style={{ height: 28, width: 28 }}
            />
            {match.refereeName ?? "Ver ficha"}
          </Link>
        ) : (
          <span className="text-sm font-medium text-slate-400">Por designar</span>
        )}
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
        seccionesPorPeriodo={seccionesPorPeriodo}
        resultado1h={resultado1h}
        hayMitades={hayMitades}
        jugadores={jugadores}
        sinDatos={sinDatos}
        apuestas={apuestas}
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
