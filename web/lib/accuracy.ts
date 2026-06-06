// Utilidades de acierto del modelo (predicho vs real).

export type Outcome = "A" | "X" | "B";

/** Resultado real desde el marcador. */
export function outcome(a: number, b: number): Outcome {
  return a > b ? "A" : a < b ? "B" : "X";
}

/** Predicción 1X2 del modelo = resultado más probable. */
export function pred1x2(
  p1: number | null,
  pX: number | null,
  p2: number | null,
): Outcome {
  const a = p1 ?? 0;
  const x = pX ?? 0;
  const b = p2 ?? 0;
  if (a >= x && a >= b) return "A";
  if (b >= a && b >= x) return "B";
  return "X";
}

/** Brier score de un 1X2 (0 perfecto; menor es mejor). */
export function brier1x2(
  p1: number,
  pX: number,
  p2: number,
  real: Outcome,
): number {
  const oa = real === "A" ? 1 : 0;
  const ox = real === "X" ? 1 : 0;
  const ob = real === "B" ? 1 : 0;
  return (p1 - oa) ** 2 + (pX - ox) ** 2 + (p2 - ob) ** 2;
}
