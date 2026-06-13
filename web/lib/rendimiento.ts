// Tipos del rendimiento del modelo por mercado. Los datos se cargan desde la DB
// (modelo MarketPerformance, ver lib/queries.ts → getMarketPerformance).

export type Bin = {
  lo: number;
  hi: number;
  pred: number;
  real: number;
  n: number;
};

export type MarketPerf = {
  mercado: string;
  etiqueta: string;
  fuente: string;
  n: number;
  brier: number;
  acierto: number;
  ece: number;
  cob80: number | null;
  bins: Bin[];
};
