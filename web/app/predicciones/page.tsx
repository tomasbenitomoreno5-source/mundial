import type { MatchLike } from "@/components/MatchCard";
import { PrediccionesBrowser } from "@/components/PrediccionesBrowser";
import { getKnockoutPlaceholders, getMatches } from "@/lib/queries";

export const revalidate = 60; // ISR: refleja el re-seed sin rebuild

export const metadata = {
  title: "Predicciones · Mundial.Predict",
  description: "Probabilidades de los 72 partidos del Mundial 2026.",
};

export default async function PrediccionesPage() {
  const [matches, knockout] = await Promise.all([
    getMatches(),
    getKnockoutPlaceholders(),
  ]);

  // Los cruces de eliminatoria sin equipos se muestran en la MISMA lista,
  // ordenados por fecha, con el formato de tarjeta (placeholder "Por determinar").
  const placeholders: MatchLike[] = knockout.map((k) => {
    const [slotA, slotB] = (k.label ?? "").split(/\s+vs\.?\s+/i);
    return {
      id: `ko-${k.sofaEventId}`,
      date: k.kickoff
        ? new Date(k.kickoff * 1000).toISOString().slice(0, 10)
        : "",
      kickoff: k.kickoff,
      teamAName: slotA || "Por determinar",
      teamBName: slotB || "Por determinar",
      groupLabel: null,
      p1: null,
      pX: null,
      p2: null,
      bttsSi: null,
      golesOver25: null,
      cornersOver95: null,
      placeholder: true,
      ronda: k.ronda,
    };
  });

  const todos = [...matches, ...placeholders];

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-6">
        <h1 className="text-3xl font-black tracking-tight">Predicciones</h1>
        <p className="mt-1 text-slate-500">
          {matches.length} partidos
          {placeholders.length > 0 &&
            ` · ${placeholders.length} de eliminatoria por determinar`}{" "}
          · busca tu selección o filtra por fecha. Toca un partido para ver
          todos los mercados.
        </p>
      </header>

      <PrediccionesBrowser matches={todos} />
    </div>
  );
}
