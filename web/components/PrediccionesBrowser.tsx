"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Dropdown, type Option } from "@/components/Dropdown";
import { MatchCard, type MatchLike } from "@/components/MatchCard";
import { flag } from "@/lib/flags";
import { fechaKey, formatFecha } from "@/lib/format";
import { teamES } from "@/lib/teams";

/** Normaliza para búsqueda: sin acentos, en minúsculas. */
function norm(s: string): string {
  return s
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

export function PrediccionesBrowser({ matches }: { matches: MatchLike[] }) {
  const [query, setQuery] = useState("");
  const [grupo, setGrupo] = useState("all");
  const [equipo, setEquipo] = useState("all");
  const [fecha, setFecha] = useState("all");

  // --- Sincronización con la URL (filtros compartibles y persistentes) ---
  const hydrated = useRef(false);

  // Al montar: leer filtros de la URL (?q=&grupo=&equipo=&fecha=)
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    if (sp.get("q")) setQuery(sp.get("q")!);
    if (sp.get("grupo")) setGrupo(sp.get("grupo")!);
    if (sp.get("equipo")) setEquipo(sp.get("equipo")!);
    if (sp.get("fecha")) setFecha(sp.get("fecha")!);
    hydrated.current = true;
  }, []);

  // Al cambiar: escribir en la URL sin recargar (history.replaceState)
  useEffect(() => {
    if (!hydrated.current) return;
    const sp = new URLSearchParams();
    if (query) sp.set("q", query);
    if (grupo !== "all") sp.set("grupo", grupo);
    if (equipo !== "all") sp.set("equipo", equipo);
    if (fecha !== "all") sp.set("fecha", fecha);
    const qs = sp.toString();
    window.history.replaceState(
      null,
      "",
      qs ? `${window.location.pathname}?${qs}` : window.location.pathname,
    );
  }, [query, grupo, equipo, fecha]);

  // Opciones de los desplegables
  const grupos = useMemo(
    () =>
      [...new Set(matches.map((m) => m.groupLabel).filter(Boolean))].sort() as string[],
    [matches],
  );
  const equipos = useMemo(() => {
    const set = new Set<string>();
    for (const m of matches) {
      if (m.placeholder) continue; // los placeholders no tienen equipos reales
      set.add(m.teamAName);
      set.add(m.teamBName);
    }
    return [...set].sort((a, b) => teamES(a).localeCompare(teamES(b), "es"));
  }, [matches]);
  const fechas = useMemo(
    () => [...new Set(matches.map((m) => fechaKey(m.date)))].sort(),
    [matches],
  );

  const grupoOpts: Option[] = [
    { value: "all", label: "Todos los grupos" },
    ...grupos.map((g) => ({ value: g, label: `Grupo ${g}` })),
  ];
  const equipoOpts: Option[] = [
    { value: "all", label: "Todas las selecciones" },
    ...equipos.map((t) => ({ value: t, label: `${flag(t)}  ${teamES(t)}` })),
  ];
  const fechaOpts: Option[] = [
    { value: "all", label: "Todas las fechas" },
    ...fechas.map((f) => ({ value: f, label: formatFecha(f) })),
  ];

  const filtradas = useMemo(() => {
    const q = norm(query);
    return matches.filter((m) => {
      if (grupo !== "all" && m.groupLabel !== grupo) return false;
      if (equipo !== "all" && m.teamAName !== equipo && m.teamBName !== equipo)
        return false;
      if (fecha !== "all" && fechaKey(m.date) !== fecha) return false;
      if (q !== "") {
        const haystack = norm(
          `${m.teamAName} ${m.teamBName} ${teamES(m.teamAName)} ${teamES(
            m.teamBName,
          )}`,
        );
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [matches, query, grupo, equipo, fecha]);

  const grupos_render = useMemo(() => {
    const map = new Map<string, MatchLike[]>();
    for (const m of filtradas) {
      const k = fechaKey(m.date);
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(m);
    }
    return [...map.keys()].sort().map(
      (k) =>
        [
          k,
          map
            .get(k)!
            .sort((a, b) => (a.kickoff ?? 0) - (b.kickoff ?? 0)),
        ] as const,
    );
  }, [filtradas]);

  const activo = query !== "" || grupo !== "all" || equipo !== "all" || fecha !== "all";
  const limpiar = () => {
    setQuery("");
    setGrupo("all");
    setEquipo("all");
    setFecha("all");
  };

  return (
    <div>
      {/* Toolbar: buscador + filtros */}
      <div className="sticky top-[57px] z-10 -mx-4 mb-6 border-b border-slate-200 bg-[var(--background)]/95 px-4 py-3 backdrop-blur">
        <div className="relative mb-3">
          <svg
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar selección (p. ej. españa, brasil…)"
            className="w-full rounded-full border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Dropdown
            value={grupo}
            options={grupoOpts}
            onChange={setGrupo}
            ariaLabel="Filtrar por grupo"
          />
          <Dropdown
            value={equipo}
            options={equipoOpts}
            onChange={setEquipo}
            ariaLabel="Filtrar por selección"
            searchable
          />
          <Dropdown
            value={fecha}
            options={fechaOpts}
            onChange={setFecha}
            ariaLabel="Filtrar por fecha"
          />
          {activo && (
            <button
              onClick={limpiar}
              className="rounded-full px-3 py-2.5 text-sm font-medium text-indigo-600 transition hover:bg-indigo-50"
            >
              Limpiar
            </button>
          )}
          <span className="ml-auto text-xs text-slate-500">
            {filtradas.length} {filtradas.length === 1 ? "partido" : "partidos"}
          </span>
        </div>
      </div>

      {/* Resultados */}
      {grupos_render.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 py-16 text-center text-slate-500">
          No hay partidos que coincidan con los filtros.
          <button
            onClick={limpiar}
            className="ml-1 font-medium text-indigo-600 hover:underline"
          >
            Limpiar
          </button>
        </div>
      ) : (
        <div className="space-y-10">
          {grupos_render.map(([fk, lista]) => (
            <section key={fk}>
              <h2 className="mb-4 flex items-center gap-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                <span className="h-px flex-1 bg-slate-200" />
                {formatFecha(fk)}
                <span className="h-px flex-1 bg-slate-200" />
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {lista.map((m) => (
                  <MatchCard key={m.id} m={m} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
