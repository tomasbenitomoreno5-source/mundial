import Link from "next/link";

import { MatchCard } from "@/components/MatchCard";
import { flag } from "@/lib/flags";
import { pct } from "@/lib/format";
import { prisma } from "@/lib/prisma";
import { getMatches, getTournamentOdds } from "@/lib/queries";
import { teamES } from "@/lib/teams";

export const revalidate = 1800; // ISR: refleja el re-seed sin rebuild

// Gradiente oscuro aplicado inline para garantizar el contraste del hero.
const HERO_BG: React.CSSProperties = {
  backgroundColor: "#1e1b4b",
  backgroundImage: [
    "radial-gradient(1100px 480px at 85% -15%, rgba(251,191,36,0.28), transparent 60%)",
    "radial-gradient(900px 500px at 5% 0%, rgba(99,102,241,0.45), transparent 55%)",
    "linear-gradient(160deg, #312e81 0%, #1e1b4b 55%, #0b1020 100%)",
  ].join(","),
};
const DOTS: React.CSSProperties = {
  backgroundImage:
    "radial-gradient(rgba(255,255,255,0.07) 1px, transparent 1px)",
  backgroundSize: "22px 22px",
};

export default async function HomePage() {
  const [matches, teamCount, marketCount, odds] = await Promise.all([
    getMatches(),
    prisma.team.count(),
    prisma.market.count(),
    getTournamentOdds(),
  ]);
  const destacados = matches.slice(0, 6);
  const favoritas = odds.slice(0, 10);

  return (
    <div>
      {/* HERO */}
      <section className="relative overflow-hidden text-white" style={HERO_BG}>
        <div className="absolute inset-0" style={DOTS} />
        <div className="relative mx-auto max-w-6xl px-4 py-20 sm:py-28">
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white ring-1 ring-white/20">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
            Mundial FIFA 2026 · USA · Canadá · México
          </span>
          <h1 className="mt-6 max-w-3xl text-4xl font-black leading-[1.05] tracking-tight sm:text-6xl">
            Las probabilidades reales de cada partido del Mundial.
          </h1>
          <p className="mt-5 max-w-2xl text-base text-indigo-100/90 sm:text-lg">
            Un modelo estadístico simula 20.000 veces los 72 partidos para
            estimar resultados, goles, córners y mucho más. Sin opiniones: solo
            datos.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/predicciones"
              className="rounded-full bg-amber-400 px-6 py-3 text-center text-sm font-bold text-indigo-950 shadow-sm transition hover:bg-amber-300"
            >
              Ver predicciones
            </Link>
            <Link
              href="/metodologia"
              className="rounded-full px-6 py-3 text-center text-sm font-semibold text-white ring-1 ring-white/40 transition hover:bg-white/10"
            >
              Cómo funciona
            </Link>
          </div>

          <dl className="mt-14 grid max-w-2xl grid-cols-3 gap-6">
            <Stat value="72" label="partidos" />
            <Stat value={`${teamCount}`} label="selecciones" />
            <Stat
              value={`${Math.round(marketCount / 1000)}k`}
              label="mercados estimados"
            />
          </dl>
        </div>
      </section>

      {/* FAVORITAS AL TÍTULO */}
      {favoritas.length > 0 && (
        <section className="mx-auto max-w-6xl px-4 py-16">
          <div className="mb-6 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">
                Favoritas al título
              </h2>
              <p className="text-sm text-slate-500">
                Probabilidad de ganar el Mundial según el Monte Carlo del torneo.
              </p>
            </div>
            <Link
              href="/selecciones"
              className="shrink-0 text-sm font-semibold text-indigo-600 hover:underline"
            >
              Todas las selecciones →
            </Link>
          </div>
          <ol className="overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200">
            {favoritas.map((o, i) => (
              <li key={o.team}>
                <Link
                  href={`/selecciones/${encodeURIComponent(o.team)}`}
                  className="flex items-center gap-3 border-t border-slate-100 px-4 py-3 transition first:border-t-0 hover:bg-slate-50"
                >
                  <span className="w-5 text-sm font-semibold text-slate-400">
                    {i + 1}
                  </span>
                  <span className="text-2xl leading-none">{flag(o.team)}</span>
                  <span className="flex-1 font-medium text-slate-900">
                    {teamES(o.team)}
                  </span>
                  <span className="text-sm font-bold tabular-nums text-indigo-600">
                    {pct(o.pCampeon)}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* DESTACADOS */}
      <section className="mx-auto max-w-6xl px-4 py-16">
        <div className="mb-6 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">
              Próximos partidos
            </h2>
            <p className="text-sm text-slate-500">
              Una muestra. Tienes los 72 en Predicciones.
            </p>
          </div>
          <Link
            href="/predicciones"
            className="shrink-0 text-sm font-semibold text-indigo-600 hover:underline"
          >
            Ver todos →
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {destacados.map((m) => (
            <MatchCard key={m.id} m={m} />
          ))}
        </div>
      </section>

      {/* CÓMO FUNCIONA */}
      <section className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="text-2xl font-bold tracking-tight">Cómo se calcula</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Tres pasos, explicados en detalle en la página de metodología.
          </p>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            <Step
              n="1"
              title="Datos reales"
              body="Estadísticas partido a partido de cada selección y sus jugadores, desde su ciclo actual."
            />
            <Step
              n="2"
              title="Equipos similares"
              body="Un modelo de estilo (KNN) y la fuerza ELO construyen un universo de partidos comparables para cada cruce."
            />
            <Step
              n="3"
              title="20.000 simulaciones"
              body="Cada partido se simula con bootstrap y corrección Dixon-Coles para obtener probabilidades coherentes."
            />
          </div>
        </div>
      </section>
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <dt className="text-3xl font-black tracking-tight sm:text-4xl">
        {value}
      </dt>
      <dd className="mt-1 text-xs text-indigo-200/80 sm:text-sm">{label}</dd>
    </div>
  );
}

function Step({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-6 ring-1 ring-slate-200">
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 text-sm font-bold text-white">
        {n}
      </span>
      <h3 className="mt-4 font-semibold">{title}</h3>
      <p className="mt-1 text-sm leading-relaxed text-slate-600">{body}</p>
    </div>
  );
}
