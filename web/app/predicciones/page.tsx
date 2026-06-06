import { PrediccionesBrowser } from "@/components/PrediccionesBrowser";
import { getMatches } from "@/lib/queries";

export const revalidate = 1800; // ISR: refleja el re-seed sin rebuild

export const metadata = {
  title: "Predicciones · Mundial.Predict",
  description: "Probabilidades de los 72 partidos del Mundial 2026.",
};

export default async function PrediccionesPage() {
  const matches = await getMatches();

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-6">
        <h1 className="text-3xl font-black tracking-tight">Predicciones</h1>
        <p className="mt-1 text-slate-500">
          {matches.length} partidos · busca tu selección o filtra por fecha.
          Toca un partido para ver todos los mercados.
        </p>
      </header>

      <PrediccionesBrowser matches={matches} />
    </div>
  );
}
