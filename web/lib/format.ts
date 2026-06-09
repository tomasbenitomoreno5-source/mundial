/** Formatea una probabilidad [0,1] como porcentaje entero. */
export function pct(p: number | null | undefined): string {
  if (p == null) return "–";
  return `${Math.round(p * 100)}%`;
}

/** Formatea la fecha ISO (o dd/mm/yyyy) a algo legible en es-ES. */
export function formatFecha(fecha: string): string {
  // El dataset trae "2026-06-17" o "17/06/2026"; normalizamos a Date.
  let d: Date | null = null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(fecha)) {
    d = new Date(`${fecha}T00:00:00`);
  } else if (/^\d{2}\/\d{2}\/\d{4}$/.test(fecha)) {
    const [dd, mm, yyyy] = fecha.split("/");
    d = new Date(`${yyyy}-${mm}-${dd}T00:00:00`);
  }
  if (!d || isNaN(d.getTime())) return fecha;
  return d.toLocaleDateString("es-ES", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

/** Clave de fecha ordenable (ISO) para agrupar. */
export function fechaKey(fecha: string): string {
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(fecha)) {
    const [dd, mm, yyyy] = fecha.split("/");
    return `${yyyy}-${mm}-${dd}`;
  }
  return fecha;
}
