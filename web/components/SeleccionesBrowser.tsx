"use client";

import { useMemo, useState } from "react";

import { Dropdown, type Option } from "@/components/Dropdown";
import { TeamCard } from "@/components/TeamCard";
import { teamES } from "@/lib/teams";

export type TeamLike = {
  name: string;
  groupLabel: string | null;
};

/** Normaliza para búsqueda: sin acentos, en minúsculas. */
function norm(s: string): string {
  return s
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

const ORDEN_OPTS: Option[] = [
  { value: "alfabetico", label: "Alfabético" },
  { value: "grupo", label: "Por grupo" },
];

export function SeleccionesBrowser({ teams }: { teams: TeamLike[] }) {
  const [query, setQuery] = useState("");
  const [orden, setOrden] = useState("alfabetico");
  const [grupo, setGrupo] = useState("all");

  const grupoOpts: Option[] = useMemo(() => {
    const gs = [
      ...new Set(teams.map((t) => t.groupLabel).filter(Boolean)),
    ].sort() as string[];
    return [
      { value: "all", label: "Todos los grupos" },
      ...gs.map((g) => ({ value: g, label: `Grupo ${g}` })),
    ];
  }, [teams]);

  const filtradas = useMemo(() => {
    const q = norm(query);
    const list = teams.filter((t) => {
      if (grupo !== "all" && t.groupLabel !== grupo) return false;
      return q === "" || norm(`${t.name} ${teamES(t.name)}`).includes(q);
    });
    return [...list].sort((a, b) => {
      if (orden === "grupo") {
        const ga = a.groupLabel ?? "ZZ";
        const gb = b.groupLabel ?? "ZZ";
        if (ga !== gb) return ga < gb ? -1 : 1;
      }
      return teamES(a.name).localeCompare(teamES(b.name), "es");
    });
  }, [teams, query, orden, grupo]);

  // Cuando se ordena por grupo, agrupamos visualmente.
  const grupos = useMemo(() => {
    if (orden !== "grupo") return null;
    const map = new Map<string, TeamLike[]>();
    for (const t of filtradas) {
      const k = t.groupLabel ?? "Sin grupo";
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(t);
    }
    return [...map.entries()];
  }, [filtradas, orden]);

  return (
    <div>
      <div className="sticky top-[57px] z-10 -mx-4 mb-6 border-b border-slate-200 bg-[var(--background)]/95 px-4 py-3 backdrop-blur">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar selección (p. ej. españa, brasil…)"
          className="mb-3 w-full rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
        />
        <div className="flex flex-wrap items-center gap-2">
          <Dropdown
            value={grupo}
            options={grupoOpts}
            onChange={setGrupo}
            ariaLabel="Filtrar por grupo"
          />
          <Dropdown
            value={orden}
            options={ORDEN_OPTS}
            onChange={setOrden}
            ariaLabel="Ordenar selecciones"
          />
          <span className="ml-auto text-xs text-slate-500">
            {filtradas.length}{" "}
            {filtradas.length === 1 ? "selección" : "selecciones"}
          </span>
        </div>
      </div>

      {grupos ? (
        <div className="space-y-8">
          {grupos.map(([g, lista]) => (
            <section key={g}>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                {g === "Sin grupo" ? g : `Grupo ${g}`}
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {lista.map((t) => (
                  <TeamCard
                    key={t.name}
                    name={t.name}
                    groupLabel={t.groupLabel}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : filtradas.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 py-16 text-center text-slate-500">
          No hay selecciones que coincidan con la búsqueda.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtradas.map((t) => (
            <TeamCard key={t.name} name={t.name} groupLabel={t.groupLabel} />
          ))}
        </div>
      )}
    </div>
  );
}
