"""Entrypoint de línea de comandos: ejecuta la predicción y escribe los CSV."""

from __future__ import annotations

import argparse
import time

from . import config
from .dataset import load_dataset
from .pipeline import predict_all, write_outputs, write_scores
from .players import predict_players, write_players
from .style import compute_style_knn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Predictor Mundial 2026 (Python)")
    parser.add_argument("--n-sim", type=int, default=config.N_SIM,
                        help="simulaciones Monte Carlo por partido")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--prefix", default="predicciones",
                        help="prefijo de los ficheros de salida")
    args = parser.parse_args(argv)

    t0 = time.time()
    print(f"[*] Prediciendo (n_sim={args.n_sim}, seed={args.seed})...")
    d = load_dataset()
    scores: list[dict] = []
    lambdas: dict = {}
    largo = predict_all(dataset=d, n_sim=args.n_sim, seed=args.seed, verbose=True,
                        scores_out=scores, lambdas_out=lambdas)
    fl, fr = write_outputs(largo, prefix=args.prefix)
    write_scores(scores)
    print(f"[*] {len(largo)} filas | {largo['partido_id'].nunique()} partidos "
          f"en {time.time() - t0:.1f}s")
    print(f"[*] Escrito: {fl} y {fr}")

    # Mercados de jugador (bloque 7, motor real — Task 6.1)
    knn = compute_style_knn(d.stats)
    jug = predict_players(d, knn, lambdas, n_sim=args.n_sim, seed=args.seed)
    fj = write_players(jug)
    n_jug = jug["jugador"].nunique() if len(jug) else 0
    print(f"[*] Jugador: {len(jug)} filas | {n_jug} jugadores -> {fj}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
