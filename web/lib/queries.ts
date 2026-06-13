import { prisma } from "@/lib/prisma";
import { metricLabel } from "@/lib/metric-labels";
import type { Bin, MarketPerf } from "@/lib/rendimiento";

/** Rendimiento por mercado (calibración + Brier) desde MarketPerformance. */
export async function getMarketPerformance(): Promise<MarketPerf[]> {
  const rows = await prisma.marketPerformance.findMany();
  return rows.map((r) => {
    let bins: Bin[] = [];
    try {
      bins = JSON.parse(r.binsJson) as Bin[];
    } catch {
      bins = [];
    }
    return {
      mercado: r.mercado,
      etiqueta: metricLabel(r.mercado),
      fuente: r.fuente,
      n: r.n,
      brier: r.brier,
      acierto: r.acierto,
      ece: r.ece,
      cob80: r.cob80,
      bins,
    };
  });
}

export async function getMatches() {
  return prisma.match.findMany({
    orderBy: [{ date: "asc" }, { id: "asc" }],
  });
}

export async function getMatch(id: string) {
  return prisma.match.findUnique({
    where: { id },
    include: { markets: true },
  });
}

export async function getMatchIds() {
  const rows = await prisma.match.findMany({ select: { id: true } });
  return rows.map((r) => r.id);
}

/** Partidos ya jugados (con marcador), para el rendimiento del modelo. */
export async function getSettledMatches() {
  return prisma.match.findMany({
    where: { settled: true },
    orderBy: [{ kickoff: "asc" }, { date: "asc" }],
  });
}

export type MatchWithMarkets = NonNullable<
  Awaited<ReturnType<typeof getMatch>>
>;
export type MarketRow = MatchWithMarkets["markets"][number];

// --- Selecciones ---

export async function getTeams() {
  return prisma.team.findMany({ orderBy: { name: "asc" } });
}

export async function getTeamNames() {
  const rows = await prisma.team.findMany({ select: { name: true } });
  return rows.map((r) => r.name);
}

/** Nombres con ficha: las 48 + los vecinos KNN (que pueden no ser mundialistas). */
export async function getLinkableTeamNames() {
  const [teams, vecinos] = await Promise.all([
    prisma.team.findMany({ select: { name: true } }),
    prisma.teamSimilar.findMany({
      select: { vecino: true },
      distinct: ["vecino"],
    }),
  ]);
  return [
    ...new Set([
      ...teams.map((t) => t.name),
      ...vecinos.map((v) => v.vecino),
    ]),
  ];
}

export async function getTeamDetail(name: string) {
  const team = await prisma.team.findUnique({ where: { name } });
  if (!team) return null;
  const [similares, perfiles, historialRaw, matches, allProfiles, odds] =
    await Promise.all([
      prisma.teamSimilar.findMany({
        where: { team: name },
        orderBy: { rank: "asc" },
      }),
      prisma.teamMetricProfile.findMany({ where: { team: name } }),
      prisma.teamMatchStat.findMany({ where: { team: name } }),
      prisma.match.findMany({
        where: { OR: [{ teamAName: name }, { teamBName: name }] },
        orderBy: [{ date: "asc" }, { id: "asc" }],
      }),
      prisma.teamMetricProfile.findMany({
        select: { metrica: true, media: true },
      }),
      prisma.tournamentOdds.findUnique({ where: { team: name } }),
    ]);

  // Enriquecer el historial con rival y marcador (la fila del rival es la otra
  // entrada con el mismo partidoId).
  const golesDe = (metrics: string): number | null => {
    const g = (JSON.parse(metrics) as Record<string, number | null>).goles;
    return typeof g === "number" ? g : null;
  };
  const oponentes = await prisma.teamMatchStat.findMany({
    where: {
      partidoId: { in: historialRaw.map((h) => h.partidoId) },
      team: { not: name },
    },
  });
  const oppByPid = new Map(oponentes.map((o) => [o.partidoId, o]));
  const historial = historialRaw.map((h) => {
    const o = oppByPid.get(h.partidoId);
    return {
      partidoId: h.partidoId,
      partidoCompleto: h.partidoCompleto,
      tipoEquipo: h.tipoEquipo,
      metrics: h.metrics,
      rival: o?.team ?? null,
      golesFavor: golesDe(h.metrics),
      golesContra: o ? golesDe(o.metrics) : null,
    };
  });

  // Ranking por métrica: puesto de esta selección por media (desc) entre todas
  // las que tienen valor. Empates → mismo puesto (rank competición).
  const mediasPorMetrica = new Map<string, number[]>();
  for (const r of allProfiles) {
    if (r.media == null) continue;
    if (!mediasPorMetrica.has(r.metrica)) mediasPorMetrica.set(r.metrica, []);
    mediasPorMetrica.get(r.metrica)!.push(r.media);
  }
  const rankByMetric: Record<string, number> = {};
  let totalTeams = 0;
  for (const p of perfiles) {
    const medias = mediasPorMetrica.get(p.metrica);
    if (!medias || p.media == null) continue;
    totalTeams = Math.max(totalTeams, medias.length);
    rankByMetric[p.metrica] = medias.filter((m) => m > p.media!).length + 1;
  }

  // Radar de estilo: percentil (0-100) de la selección entre las 48 por eje.
  const RADAR_AXES: { key: string; label: string }[] = [
    { key: "expected_goals", label: "Ataque" },
    { key: "total_shots", label: "Remate" },
    { key: "big_chances", label: "Creación" },
    { key: "ball_possession", label: "Posesión" },
    { key: "accurate_passes", label: "Pase" },
    { key: "tackles", label: "Presión" },
  ];
  const perfilMedia = new Map(perfiles.map((p) => [p.metrica, p.media]));
  const radar = RADAR_AXES.map((ax) => {
    const medias = mediasPorMetrica.get(ax.key) ?? [];
    const mine = perfilMedia.get(ax.key);
    let value = 0;
    if (mine != null && medias.length > 0) {
      value = Math.round(
        (medias.filter((m) => m <= mine).length / medias.length) * 100,
      );
    }
    return { label: ax.label, value };
  });

  return {
    team,
    similares,
    perfiles,
    historial,
    matches,
    rankByMetric,
    totalTeams,
    radar,
    odds,
  };
}

export type TeamRow = Awaited<ReturnType<typeof getTeams>>[number];
export type TeamDetail = NonNullable<Awaited<ReturnType<typeof getTeamDetail>>>;

// --- Jugadores ---

/** Estadísticas agregadas por jugador de una selección (de PlayerAggregate). */
export async function getTeamPlayers(team: string) {
  const rows = await prisma.playerAggregate.findMany({
    where: { team },
    orderBy: [{ goles: "desc" }, { partidos: "desc" }],
  });
  return rows.map((p) => ({
    player: p.player,
    partidos: p.partidos,
    goles: p.goles,
    asistencias: p.asistencias,
    tirosPorPartido: p.tiros,
    sotPorPartido: p.sot,
    xgPorPartido: p.xg,
    xaPorPartido: p.xa,
    pasesClavePorPartido: p.pasesClave,
    pasesPorPartido: p.pases,
    regatesPorPartido: p.regates,
    entradasPorPartido: p.entradas,
    intercepcionesPorPartido: p.intercep,
    duelosGanadosPorPartido: p.duelos,
    recuperacionesPorPartido: p.recuperaciones,
    rating: p.rating,
    minutos: p.minutos,
  }));
}

/** Nombres de jugadores con página (los de las 48 selecciones). */
export async function getPlayerNames() {
  const teams = (await prisma.team.findMany({ select: { name: true } })).map(
    (t) => t.name,
  );
  const rows = await prisma.playerAggregate.findMany({
    where: { team: { in: teams } },
    select: { player: true },
  });
  return rows.map((r) => r.player);
}

/** Detalle de un jugador: agregado + sus partidos del Mundial + sus mercados. */
export async function getPlayerDetail(name: string) {
  const agg = await prisma.playerAggregate.findUnique({
    where: { player: name },
  });
  if (!agg) return null;
  const [bio, markets] = await Promise.all([
    prisma.playerBio.findUnique({ where: { player: name } }),
    prisma.playerMarket.findMany({ where: { player: name } }),
  ]);
  const matchIds = [...new Set(markets.map((m) => m.matchId))];
  const matches = await prisma.match.findMany({
    where: { id: { in: matchIds } },
    orderBy: [{ kickoff: "asc" }, { date: "asc" }],
  });
  return { agg, bio, markets, matches };
}

/** Mercados de jugador de un partido. */
export async function getPlayerMarkets(matchId: string) {
  return prisma.playerMarket.findMany({ where: { matchId } });
}

/** Convocatoria (jugador, equipo) de las selecciones dadas. */
export async function getConvocatoria(equipos: string[]) {
  return prisma.convocatoria.findMany({ where: { equipo: { in: equipos } } });
}

/** Probabilidades de marcador exacto de un partido. */
export async function getScoreProbs(matchId: string) {
  return prisma.scoreProb.findMany({ where: { matchId } });
}

/** Probabilidades de torneo de todas las selecciones (ranking de favoritas). */
export async function getTournamentOdds() {
  return prisma.tournamentOdds.findMany({ orderBy: { pCampeon: "desc" } });
}

export type TournamentOddsRow = Awaited<
  ReturnType<typeof getTournamentOdds>
>[number];

/** Selecciones agrupadas por grupo, con sus probabilidades de clasificación. */
export async function getGroupStandings() {
  const [teams, odds] = await Promise.all([
    prisma.team.findMany(),
    prisma.tournamentOdds.findMany(),
  ]);
  const oddsByTeam = new Map(odds.map((o) => [o.team, o]));
  const byGroup = new Map<
    string,
    { name: string; p1: number; p2: number; pAdv: number; pts: number }[]
  >();
  for (const t of teams) {
    const g = t.groupLabel ?? "?";
    if (!byGroup.has(g)) byGroup.set(g, []);
    const o = oddsByTeam.get(t.name);
    byGroup.get(g)!.push({
      name: t.name,
      p1: o?.p1Grupo ?? 0,
      p2: o?.p2Grupo ?? 0,
      pAdv: o?.pGrupo ?? 0,
      pts: o?.ptsGrupo ?? 0,
    });
  }
  return [...byGroup.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(
      ([g, ts]) => [g, ts.sort((x, y) => y.pAdv - x.pAdv)] as const,
    );
}

export type TeamPlayer = Awaited<ReturnType<typeof getTeamPlayers>>[number];
export type PlayerMarketRow = Awaited<
  ReturnType<typeof getPlayerMarkets>
>[number];

// --- Árbitros ---------------------------------------------------------------

/** Todos los árbitros del plantel (para el índice). */
export async function getReferees() {
  return prisma.referee.findMany({ orderBy: { name: "asc" } });
}

/** sofaIds del plantel, para generateStaticParams. */
export async function getRefereeSofaIds() {
  const rows = await prisma.referee.findMany({ select: { sofaId: true } });
  return rows.map((r) => r.sofaId);
}

/** Detalle de un árbitro: perfil + sus últimos partidos (más reciente primero). */
export async function getRefereeDetail(sofaId: number) {
  const ref = await prisma.referee.findUnique({ where: { sofaId } });
  if (!ref) return null;
  const [matches, teamHistory] = await Promise.all([
    prisma.refereeMatch.findMany({
      where: { refereeSofaId: sofaId },
      orderBy: [{ ts: "desc" }],
    }),
    prisma.refereeTeamHistory.findMany({
      where: { refereeSofaId: sofaId },
      orderBy: [{ games: "desc" }, { team: "asc" }],
    }),
  ]);
  return { ref, matches, teamHistory };
}

/** Cruces de eliminatoria aún sin equipos (placeholders "Por determinar"). */
export async function getKnockoutPlaceholders() {
  return prisma.knockoutFixture.findMany({ orderBy: { kickoff: "asc" } });
}

export type RefereeRow = Awaited<ReturnType<typeof getReferees>>[number];
export type RefereeMatchRow = NonNullable<
  Awaited<ReturnType<typeof getRefereeDetail>>
>["matches"][number];
