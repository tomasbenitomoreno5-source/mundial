"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Inicio" },
  { href: "/predicciones", label: "Predicciones" },
  { href: "/selecciones", label: "Selecciones" },
  { href: "/rendimiento", label: "Rendimiento" },
  { href: "/metodologia", label: "Metodología" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center gap-0.5 sm:gap-1">
      {LINKS.map((l) => {
        const active =
          l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            className={`rounded-full px-2.5 py-1.5 text-[13px] font-medium transition sm:px-3 sm:text-sm ${
              active
                ? "bg-indigo-600 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
