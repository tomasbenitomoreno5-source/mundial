"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export type Option = { value: string; label: string };

function norm(s: string): string {
  return s
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

/**
 * Dropdown propio (no nativo): panel con scroll fijo que no "sigue al ratón".
 * Cierra al hacer clic fuera o con Escape. Con `searchable`, muestra un buscador
 * arriba para filtrar opciones largas (p. ej. las 48 selecciones).
 */
export function Dropdown({
  value,
  options,
  onChange,
  ariaLabel,
  searchable = false,
}: {
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  ariaLabel?: string;
  searchable?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const current = options.find((o) => o.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Limpia la búsqueda al cerrar
  useEffect(() => {
    if (!open) setQ("");
  }, [open]);

  const visibles = useMemo(() => {
    if (!searchable || q === "") return options;
    const nq = norm(q);
    return options.filter((o) => norm(o.label).includes(nq));
  }, [options, q, searchable]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-2 rounded-full border bg-white px-4 py-2.5 text-sm transition ${
          open
            ? "border-indigo-400 ring-2 ring-indigo-100"
            : "border-slate-200 hover:border-slate-300"
        }`}
      >
        <span className="text-slate-700">{current?.label}</span>
        <svg
          className={`h-4 w-4 text-slate-400 transition ${open ? "rotate-180" : ""}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 z-30 mt-2 w-max min-w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl shadow-slate-300/40">
          {searchable && (
            <div className="border-b border-slate-100 p-2">
              <input
                autoFocus
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Buscar…"
                className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
              />
            </div>
          )}
          <ul role="listbox" className="max-h-64 overflow-y-auto p-1">
            {visibles.length === 0 && (
              <li className="px-3 py-2 text-sm text-slate-400">Sin resultados</li>
            )}
            {visibles.map((o) => {
              const selected = o.value === value;
              return (
                <li key={o.value} role="option" aria-selected={selected}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(o.value);
                      setOpen(false);
                    }}
                    className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition ${
                      selected
                        ? "bg-indigo-50 font-medium text-indigo-700"
                        : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    <span className="whitespace-nowrap">{o.label}</span>
                    {selected && (
                      <svg
                        className="h-4 w-4 shrink-0"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                      >
                        <path d="M20 6 9 17l-5-5" />
                      </svg>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
