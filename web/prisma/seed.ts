import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { PrismaClient } from "@prisma/client";

import { PLAYER_MARKETS } from "../lib/player-markets";

const prisma = new PrismaClient();

// Los datos (raw scrape + inputs/outputs del modelo) viven en mundial/data/.
const ROOT = join(process.cwd(), "..", "data");

/** Parser de los CSV del motor: `;`-separados, BOM, sin comillas. */
function parseCsv(file: string): Record<string, string>[] {
  const text = readFileSync(join(ROOT, file), "utf8").replace(/^﻿/, "");
  const [headerLine, ...lines] = text.trim().split("\n");
  // Quita el \r de CRLF y las comillas envolventes (stats_final.csv va citado).
  const strip = (s: string) => s.replace(/\r$/, "").replace(/^"(.*)"$/, "$1");
  const headers = headerLine.replace(/^﻿/, "").split(";").map(strip);
  return lines
    .filter((l) => l.length > 0)
    .map((line) => {
      const cells = line.split(";").map(strip);
      const row: Record<string, string> = {};
      headers.forEach((h, i) => (row[h] = cells[i]));
      return row;
    });
}

/** Convierte texto a número tolerando decimal-coma y el placeholder "-". */
function num(s: string | undefined): number | null {
  if (s == null || s === "" || s === "-") return null;
  return parseFloat(s.replace(",", "."));
}

/**
 * Deriva los grupos del Mundial a partir de los cruces: en fase de grupos cada
 * equipo solo juega contra los otros 3 de su grupo, así que las componentes
 * conexas del grafo "A juega contra B" son los grupos. Se etiquetan A, B, C…
 * por orden de la primera fecha de cada grupo.
 */
function derivarGrupos(
  rows: Record<string, string>[],
): Map<string, string> {
  const parent = new Map<string, string>();
  const find = (x: string): string => {
    if (!parent.has(x)) parent.set(x, x);
    if (parent.get(x) !== x) parent.set(x, find(parent.get(x)!));
    return parent.get(x)!;
  };
  const union = (a: string, b: string) => {
    parent.set(find(a), find(b));
  };
  for (const r of rows) union(r.equipo_a, r.equipo_b);

  // Componente -> equipos y primera fecha
  const comps = new Map<string, { teams: Set<string>; firstDate: string }>();
  for (const r of rows) {
    const root = find(r.equipo_a);
    if (!comps.has(root)) {
      comps.set(root, { teams: new Set(), firstDate: r.fecha });
    }
    const c = comps.get(root)!;
    c.teams.add(r.equipo_a);
    c.teams.add(r.equipo_b);
    if (r.fecha < c.firstDate) c.firstDate = r.fecha;
  }

  // Ordenar grupos por primera fecha y etiquetar A, B, C…
  const ordenadas = [...comps.values()].sort((x, y) =>
    x.firstDate < y.firstDate ? -1 : x.firstDate > y.firstDate ? 1 : 0,
  );
  const teamToGroup = new Map<string, string>();
  ordenadas.forEach((c, i) => {
    const label = String.fromCharCode(65 + i); // A, B, C…
    for (const t of c.teams) teamToGroup.set(t, label);
  });
  return teamToGroup;
}

async function main() {
  const resumen = parseCsv("predicciones_resumen_py.csv");
  const largo = parseCsv("predicciones_largo_py.csv");
  // Fase de cada partido (grupos | eliminatoria) desde partidos_a_predecir.csv.
  const faseMap = new Map<string, string>();
  if (existsSync(join(ROOT, "partidos_a_predecir.csv"))) {
    for (const r of parseCsv("partidos_a_predecir.csv")) {
      faseMap.set(r.partido_id, r.fase || "grupos");
    }
  }
  // Los grupos se derivan SOLO de los partidos de fase de grupos (si no, las
  // eliminatorias conectarían grupos distintos y los mezclarían).
  const teamToGroup = derivarGrupos(
    resumen.filter((r) => (faseMap.get(r.partido_id) ?? "grupos") === "grupos"),
  );

  // Reset idempotente (orden por las FK)
  await prisma.market.deleteMany();
  await prisma.match.deleteMany();
  await prisma.team.deleteMany();

  // Equipos
  const teamNames = new Set<string>();
  for (const r of resumen) {
    teamNames.add(r.equipo_a);
    teamNames.add(r.equipo_b);
  }
  const eloMap = new Map(
    parseCsv("elo_2026.csv").map((r) => [r.equipo, parseInt(r.elo, 10)]),
  );
  await prisma.team.createMany({
    data: [...teamNames].map((name) => ({
      name,
      elo: eloMap.get(name) ?? null,
      groupLabel: teamToGroup.get(name) ?? null,
    })),
  });

  // Calendario real (id de evento + hora) y resultados (si existen).
  const cal = new Map<string, { eventId: number | null; kickoff: number | null }>();
  if (existsSync(join(ROOT, "calendario.csv"))) {
    for (const r of parseCsv("calendario.csv")) {
      cal.set(r.partido_id, {
        eventId: r.sofa_event_id ? parseInt(r.sofa_event_id, 10) : null,
        kickoff: r.kickoff ? parseInt(r.kickoff, 10) : null,
      });
    }
  }
  const res = new Map<string, { a: number | null; b: number | null }>();
  if (existsSync(join(ROOT, "resultados.csv"))) {
    for (const r of parseCsv("resultados.csv")) {
      if (r.finished === "1" || r.finished === "true") {
        res.set(r.partido_id, {
          a: r.score_a === "" ? null : parseInt(r.score_a, 10),
          b: r.score_b === "" ? null : parseInt(r.score_b, 10),
        });
      }
    }
  }

  // Partidos (con mercados clave denormalizados + calendario + resultado)
  for (const r of resumen) {
    const c = cal.get(r.partido_id);
    const rr = res.get(r.partido_id);
    const fase = faseMap.get(r.partido_id) ?? "grupos";
    await prisma.match.create({
      data: {
        id: r.partido_id,
        date: r.fecha,
        teamAName: r.equipo_a,
        teamBName: r.equipo_b,
        stage: fase,
        groupLabel: fase === "grupos" ? (teamToGroup.get(r.equipo_a) ?? null) : null,
        kickoff: c?.kickoff ?? null,
        sofaEventId: c?.eventId ?? null,
        p1: num(r.p_1),
        pX: num(r.p_X),
        p2: num(r.p_2),
        bttsSi: num(r.btts_si),
        golesOver25: num(r.goles_over_2_5),
        cornersOver95: num(r.corners_over_9_5),
        scoreA: rr?.a ?? null,
        scoreB: rr?.b ?? null,
        settled: rr != null,
      },
    });
  }

  // Todos los mercados (formato largo) en lotes
  const marketData = largo.map((r) => ({
    matchId: r.partido_id,
    mercado: r.mercado,
    ambito: r.ambito,
    evento: r.evento_o_jugador,
    linea: r.linea_o_target,
    probabilidad: num(r.probabilidad) ?? 0,
  }));
  for (let i = 0; i < marketData.length; i += 5000) {
    await prisma.market.createMany({ data: marketData.slice(i, i + 5000) });
  }

  // --- Datos por selección (estilo, perfiles, historial crudo) ---
  await prisma.teamSimilar.deleteMany();
  await prisma.teamMetricProfile.deleteMany();
  await prisma.teamMatchStat.deleteMany();

  const knn = parseCsv("debug_knn.csv");
  await prisma.teamSimilar.createMany({
    data: knn.map((r) => ({
      team: r.equipo,
      rank: parseInt(r.rank, 10),
      vecino: r.vecino,
      distancia: num(r.distancia) ?? 0,
      peso: num(r.peso) ?? 0,
    })),
  });

  const perfiles = parseCsv("debug_perfiles.csv");
  await prisma.teamMetricProfile.createMany({
    data: perfiles.map((r) => ({
      team: r.equipo,
      metrica: r.metrica,
      n: parseInt(r.n, 10) || 0,
      media: num(r.media),
      mediana: num(r.mediana),
      moda: num(r.moda),
      sd: num(r.sd),
      min: num(r.min),
      max: num(r.max),
    })),
  });

  const stats = parseCsv("stats_final.csv");
  const NO_METRICA = new Set([
    "partido_id",
    "partido_completo",
    "equipo_nombre",
    "tipo_equipo",
  ]);
  const statData = stats.map((r) => {
    const metrics: Record<string, number | null> = {};
    for (const [k, v] of Object.entries(r)) {
      if (!NO_METRICA.has(k)) metrics[k] = num(v);
    }
    return {
      team: r.equipo_nombre,
      partidoId: r.partido_id,
      partidoCompleto: r.partido_completo ?? null,
      tipoEquipo: r.tipo_equipo ?? null,
      metrics: JSON.stringify(metrics),
    };
  });
  for (let i = 0; i < statData.length; i += 5000) {
    await prisma.teamMatchStat.createMany({ data: statData.slice(i, i + 5000) });
  }

  // Aviso: mundialistas (las 48 de Team) sin datos de estilo/perfiles
  const conPerfil = new Set([
    ...knn.map((r) => r.equipo),
    ...perfiles.map((r) => r.equipo),
  ]);
  const sinDatos = [...teamNames].filter((t) => !conPerfil.has(t));
  if (sinDatos.length > 0) {
    console.warn(
      `AVISO: ${sinDatos.length} selección(es) sin estilo/perfiles: ${sinDatos.join(", ")}`,
    );
  }

  // --- Jugadores: telemetría + mercados ---
  await prisma.playerMarket.deleteMany();
  await prisma.playerMatchStat.deleteMany();

  // Plantillas completas (telemetria_full.csv) si existen; si no, las 58 estrellas.
  const telFile = existsSync(join(ROOT, "telemetria_full.csv"))
    ? "telemetria_full.csv"
    : "telemetria_final.csv";
  const tel = parseCsv(telFile);
  console.log(`Telemetría: ${telFile}`);
  const TEL_NO_METRICA = new Set([
    "partido_id",
    "partido_completo",
    "jugador",
    "home_team",
    "away_team",
  ]);

  // Inferir la selección de cada jugador: equipo más frecuente entre home/away.
  const cuentaEquipo = new Map<string, Map<string, number>>();
  for (const r of tel) {
    if (!cuentaEquipo.has(r.jugador)) cuentaEquipo.set(r.jugador, new Map());
    const m = cuentaEquipo.get(r.jugador)!;
    for (const t of [r.home_team, r.away_team]) {
      if (t) m.set(t, (m.get(t) ?? 0) + 1);
    }
  }
  const equipoJugador = new Map<string, string>();
  for (const [p, m] of cuentaEquipo) {
    let best = "";
    let bestN = -1;
    for (const [t, n] of m) {
      if (n > bestN) {
        best = t;
        bestN = n;
      }
    }
    equipoJugador.set(p, best);
  }

  // Convocatorias (si existen): quedarse SOLO con los jugadores de la plantilla
  // actual de cada selección. Sin el archivo, no se filtra (todos los jugadores).
  const squad = new Map<string, Set<string>>();
  if (existsSync(join(ROOT, "convocatorias.csv"))) {
    for (const r of parseCsv("convocatorias.csv")) {
      if (!squad.has(r.equipo)) squad.set(r.equipo, new Set());
      squad.get(r.equipo)!.add(r.jugador);
    }
  }
  const jugadorOk = (p: string) =>
    squad.size === 0 ||
    (squad.get(equipoJugador.get(p) ?? "")?.has(p) ?? false);
  const telSquad = tel.filter((r) => jugadorOk(r.jugador));
  console.log(
    `Convocatorias: ${squad.size} selecciones · ${telSquad.length}/${tel.length} filas tras filtrar`,
  );

  const pmsData = telSquad.map((r) => {
    const metrics: Record<string, number | null> = {};
    for (const [k, v] of Object.entries(r)) {
      if (!TEL_NO_METRICA.has(k)) metrics[k] = num(v);
    }
    return {
      player: r.jugador,
      team: equipoJugador.get(r.jugador) ?? "",
      partidoId: r.partido_id,
      partidoCompleto: r.partido_completo ?? null,
      minutes: num(r.minutesPlayed),
      rating: num(r.rating),
      metrics: JSON.stringify(metrics),
    };
  });
  for (let i = 0; i < pmsData.length; i += 5000) {
    await prisma.playerMatchStat.createMany({ data: pmsData.slice(i, i + 5000) });
  }

  // Medias por partido (para los mercados) y nº de partidos por jugador.
  const filasJugador = new Map<string, Record<string, string>[]>();
  for (const r of telSquad) {
    if (!filasJugador.has(r.jugador)) filasJugador.set(r.jugador, []);
    filasJugador.get(r.jugador)!.push(r);
  }
  const media = (rows: Record<string, string>[], key: string): number | null => {
    const vals = rows
      .map((r) => num(r[key]))
      .filter((v): v is number => v != null);
    if (vals.length === 0) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  };
  const poissonPmf = (k: number, lam: number): number => {
    let lf = 0;
    for (let i = 2; i <= k; i++) lf += Math.log(i);
    return Math.exp(-lam + k * Math.log(lam || 1e-9) - lf);
  };
  const poissonOver = (L: number, lam: number): number => {
    const f = Math.floor(L);
    let cdf = 0;
    for (let k = 0; k <= f; k++) cdf += poissonPmf(k, lam);
    return Math.min(1, Math.max(0, 1 - cdf));
  };
  const lineasJugador = (m: number): number[] => {
    const c = Math.floor(m);
    const out = new Set<number>();
    for (let o = -1; o <= 3; o++) {
      const x = c + o + 0.5;
      if (x >= 0.5) out.add(Math.round(x * 10) / 10);
    }
    return [...out];
  };
  const r4 = (x: number) => Math.round(x * 1e4) / 1e4;

  // Media por partido de cada métrica usada por los mercados (config-driven).
  const METRICAS_MK = [
    ...new Set(
      PLAYER_MARKETS.map((m) => m.metric).filter(
        (m) => m !== "__goal_or_assist__",
      ),
    ),
  ];
  const statsJugador = new Map<
    string,
    { n: number; mean: Record<string, number | null> }
  >();
  for (const [p, rows] of filasJugador) {
    const mean: Record<string, number | null> = {};
    for (const k of METRICAS_MK) mean[k] = media(rows, k);
    statsJugador.set(p, { n: rows.length, mean });
  }

  // Amonestaciones: nº de partidos en que cada jugador vio amarilla.
  const cardMatches = new Map<string, number>();
  if (existsSync(join(ROOT, "tarjetas.csv"))) {
    for (const r of parseCsv("tarjetas.csv")) {
      cardMatches.set(r.jugador, parseInt(r.partidos_amonestado, 10) || 0);
    }
  }

  // Jugadores por selección.
  const jugadoresPorEquipo = new Map<string, string[]>();
  for (const [p, t] of equipoJugador) {
    if (!jugadoresPorEquipo.has(t)) jugadoresPorEquipo.set(t, []);
    jugadoresPorEquipo.get(t)!.push(p);
  }

  type PMk = {
    matchId: string;
    player: string;
    team: string;
    mercado: string;
    evento: string;
    linea: string;
    probabilidad: number;
  };
  const pmkData: PMk[] = [];
  type Base = { matchId: string; player: string; team: string };
  const pushSiNo = (base: Base, mercado: string, pSi: number) => {
    pmkData.push({ ...base, mercado, evento: "si", linea: "-", probabilidad: r4(pSi) });
    pmkData.push({ ...base, mercado, evento: "no", linea: "-", probabilidad: r4(1 - pSi) });
  };
  const pushOU = (base: Base, mercado: string, lam: number | null) => {
    if (lam == null || lam <= 0) return;
    for (const L of lineasJugador(lam)) {
      const pOver = r4(poissonOver(L, lam));
      pmkData.push({ ...base, mercado, evento: "over", linea: String(L), probabilidad: pOver });
      pmkData.push({ ...base, mercado, evento: "under", linea: String(L), probabilidad: r4(1 - pOver) });
    }
  };
  for (const r of resumen) {
    for (const teamName of [r.equipo_a, r.equipo_b]) {
      for (const p of jugadoresPorEquipo.get(teamName) ?? []) {
        const st = statsJugador.get(p);
        if (!st || st.n < 3) continue;
        const base: Base = { matchId: r.partido_id, player: p, team: teamName };
        for (const def of PLAYER_MARKETS) {
          if (def.tipo === "binary") {
            if (def.metric === "__yellow_card__") {
              // Probabilidad empírica de ser amonestado en un partido.
              const booked = cardMatches.get(p);
              if (booked != null)
                pushSiNo(base, def.key, Math.min(0.95, booked / st.n));
              continue;
            }
            let lam: number | null;
            if (def.metric === "__goal_or_assist__") {
              const g = st.mean["goals"];
              const a = st.mean["goalAssist"];
              lam = g == null && a == null ? null : (g ?? 0) + (a ?? 0);
            } else {
              lam = st.mean[def.metric];
            }
            if (lam != null) pushSiNo(base, def.key, 1 - Math.exp(-lam));
          } else {
            pushOU(base, def.key, st.mean[def.metric]);
          }
        }
      }
    }
  }
  for (let i = 0; i < pmkData.length; i += 5000) {
    await prisma.playerMarket.createMany({ data: pmkData.slice(i, i + 5000) });
  }

  // --- Agregados de jugador (totales, medias y radar de percentiles) ---
  await prisma.playerAggregate.deleteMany();
  const sumK = (rows: Record<string, string>[], k: string) =>
    rows.reduce((a, r) => a + (num(r[k]) ?? 0), 0);
  const axis: Record<string, number[]> = {
    gol: [], tiro: [], crea: [], pase: [], regate: [], def: [],
  };
  const perPlayer = [...filasJugador.entries()].map(([p, rows]) => {
    const v = {
      gol: media(rows, "goals") ?? 0,
      tiro: media(rows, "totalShots") ?? 0,
      crea: media(rows, "keyPass") ?? 0,
      pase: media(rows, "accuratePass") ?? 0,
      regate: media(rows, "wonContest") ?? 0,
      def:
        (media(rows, "totalTackle") ?? 0) +
        (media(rows, "interceptionWon") ?? 0) +
        (media(rows, "duelWon") ?? 0),
    };
    for (const k of Object.keys(axis)) axis[k].push(v[k as keyof typeof v]);
    return { p, rows, v };
  });
  const pctl = (arr: number[], val: number) =>
    arr.length
      ? Math.round((arr.filter((x) => x <= val).length / arr.length) * 100)
      : 0;
  const aggData = perPlayer.map(({ p, rows, v }) => ({
    player: p,
    team: equipoJugador.get(p) ?? "",
    partidos: rows.length,
    goles: Math.round(sumK(rows, "goals")),
    asistencias: Math.round(sumK(rows, "goalAssist")),
    tiros: media(rows, "totalShots"),
    sot: media(rows, "onTargetScoringAttempt"),
    xg: media(rows, "expectedGoals"),
    xa: media(rows, "expectedAssists"),
    pasesClave: media(rows, "keyPass"),
    pases: media(rows, "totalPass"),
    regates: media(rows, "wonContest"),
    entradas: media(rows, "totalTackle"),
    intercep: media(rows, "interceptionWon"),
    duelos: media(rows, "duelWon"),
    recuperaciones: media(rows, "ballRecovery"),
    minutos: media(rows, "minutesPlayed"),
    rating: media(rows, "rating"),
    radarGol: pctl(axis.gol, v.gol),
    radarTiro: pctl(axis.tiro, v.tiro),
    radarCrea: pctl(axis.crea, v.crea),
    radarPase: pctl(axis.pase, v.pase),
    radarRegate: pctl(axis.regate, v.regate),
    radarDef: pctl(axis.def, v.def),
  }));
  for (let i = 0; i < aggData.length; i += 2000) {
    await prisma.playerAggregate.createMany({ data: aggData.slice(i, i + 2000) });
  }

  // --- Bios de jugador ---
  await prisma.playerBio.deleteMany();
  if (existsSync(join(ROOT, "bios.csv"))) {
    const bios = parseCsv("bios.csv").map((r) => ({
      player: r.jugador,
      sofaId: r.sofa_id ? parseInt(r.sofa_id, 10) : null,
      position: r.posicion || null,
      age: r.edad ? parseInt(r.edad, 10) : null,
      height: r.altura ? parseInt(r.altura, 10) : null,
      foot: r.pie || null,
      marketEur: r.valor_eur ? parseInt(r.valor_eur, 10) : null,
    }));
    for (let i = 0; i < bios.length; i += 2000) {
      await prisma.playerBio.createMany({ data: bios.slice(i, i + 2000) });
    }
  }

  // --- Marcadores exactos (Dixon-Coles) ---
  await prisma.scoreProb.deleteMany();
  if (existsSync(join(ROOT, "marcadores_py.csv"))) {
    const sp = parseCsv("marcadores_py.csv").map((r) => ({
      matchId: r.partido_id,
      a: parseInt(r.a, 10),
      b: parseInt(r.b, 10),
      prob: num(r.prob) ?? 0,
    }));
    for (let i = 0; i < sp.length; i += 5000) {
      await prisma.scoreProb.createMany({ data: sp.slice(i, i + 5000) });
    }
  }

  // --- Probabilidades de torneo ---
  await prisma.tournamentOdds.deleteMany();
  if (existsSync(join(ROOT, "probabilidades_torneo.csv"))) {
    await prisma.tournamentOdds.createMany({
      data: parseCsv("probabilidades_torneo.csv").map((r) => ({
        team: r.equipo,
        pGrupo: num(r.p_grupo) ?? 0,
        pR16: num(r.p_r16) ?? 0,
        pQf: num(r.p_qf) ?? 0,
        pSf: num(r.p_sf) ?? 0,
        pFinal: num(r.p_final) ?? 0,
        pCampeon: num(r.p_campeon) ?? 0,
        p1Grupo: num(r.p_1grupo) ?? 0,
        p2Grupo: num(r.p_2grupo) ?? 0,
        ptsGrupo: num(r.pts_grupo) ?? 0,
      })),
    });
  }

  console.log(
    `Seed OK: ${teamNames.size} equipos, ${resumen.length} partidos, ${marketData.length} mercados, ` +
      `${knn.length} similares, ${perfiles.length} perfiles, ${statData.length} filas de historial, ` +
      `${pmsData.length} telemetría jugador, ${pmkData.length} mercados jugador`,
  );
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
