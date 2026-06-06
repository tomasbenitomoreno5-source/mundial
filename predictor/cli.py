"""Entrypoint de línea de comandos: ejecuta la predicción y escribe los CSV."""

from __future__ import annotations

import argparse
import time

from . import config
from .pipeline import predict_all, write_outputs


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
    largo = predict_all(n_sim=args.n_sim, seed=args.seed, verbose=True)
    fl, fr = write_outputs(largo, prefix=args.prefix)
    print(f"[*] {len(largo)} filas | {largo['partido_id'].nunique()} partidos "
          f"en {time.time() - t0:.1f}s")
    print(f"[*] Escrito: {fl} y {fr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
