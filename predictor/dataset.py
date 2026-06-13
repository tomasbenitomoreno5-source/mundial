"""Carga y limpieza de datos (port de los bloques 1-2 del script R).

Lee los tres CSV de entrada (``;``-separados, ``,``-decimal, UTF-8 con BOM),
limpia nombres de equipo, imputa NAs y deriva oponente + goles encajados.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


def _read_csv(path: Path) -> pd.DataFrame:
    """Lee un CSV en el formato del dataset (``;`` sep, ``,`` decimal, BOM)."""
    return pd.read_csv(
        path,
        sep=";",
        decimal=",",
        encoding="utf-8-sig",  # tolera el BOM que el R limpiaba a mano
        dtype=str,             # leemos todo como str y convertimos a mano
        keep_default_na=True,
        na_values=[""],
    )


def _limpia_nombre(s: pd.Series) -> pd.Series:
    """Equivalente a ``limpia_nombre`` del R: normaliza UTF-8 y hace trim."""
    return (
        s.astype("string")
        .map(lambda x: unicodedata.normalize("NFC", x) if isinstance(x, str) else x)
        .str.strip()
    )


def _to_numeric(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")


@dataclass
class Dataset:
    """Datos limpios listos para el modelo."""

    stats: pd.DataFrame          # equipo-partido, con oponente y goles_op
    tel: pd.DataFrame            # jugador-partido
    pred: pd.DataFrame           # 72 partidos a predecir
    metricas_equipo: list[str]   # métricas presentes en stats (orden canónico)
    legacy: bool = False         # True = sin mejoras Fase 2-3 (fidelidad vs R)

    @property
    def equipos_mundial(self) -> list[str]:
        return sorted(set(self.pred["equipo_a"]) | set(self.pred["equipo_b"]))


def _load_excluidos() -> set[str]:
    """Equipos a purgar (clubes / no-selecciones coladas en amistosos)."""
    if not config.EQUIPOS_EXCLUIDOS_CSV.exists():
        return set()
    df = pd.read_csv(config.EQUIPOS_EXCLUIDOS_CSV, sep=";", encoding="utf-8-sig")
    return set(df["equipo"].astype(str).str.strip())


def _excluir_fecha_futura(stats: pd.DataFrame, corte: str | None = None) -> pd.DataFrame:
    """Descarta partidos con fecha posterior al corte (por defecto, hoy).

    SofaScore lista fixtures futuros (Mundial 2026, Nations League sept '26…)
    que el scraper rellenó con marcadores espurios. No se han jugado, así que
    contaminan el entrenamiento; los reales los reincorpora el loop en vivo.
    Filas sin fecha se conservan (no se puede afirmar que sean futuras).
    """
    if "fecha" not in stats.columns:
        return stats
    import datetime as dt

    corte = corte or dt.date.today().isoformat()
    keep = stats["fecha"].isna() | (stats["fecha"] <= corte)
    return stats[keep].reset_index(drop=True)


def _merge_fechas(stats: pd.DataFrame) -> pd.DataFrame:
    """Añade fecha/torneo/categoria por partido_id desde el backfill.

    Left join: los partidos sin fecha (aún no scrapeada) quedan con NaN; esas
    columnas no son métricas del modelo, así que no rompen el bootstrap.
    """
    fechas = pd.read_csv(
        config.PARTIDO_FECHAS_CSV, sep=";", encoding="utf-8-sig",
        dtype={"partido_id": str},
    )[["partido_id", "fecha", "torneo", "categoria"]]
    return stats.merge(fechas, on="partido_id", how="left")


def _excluir_no_selecciones(stats: pd.DataFrame) -> pd.DataFrame:
    """Elimina el PARTIDO ENTERO cuando uno de los equipos está excluido.

    Borrar solo la fila del club dejaría la del rival huérfana (oponente
    inexistente); borramos por partido_id para mantener la coherencia.
    """
    excluidos = _load_excluidos()
    if not excluidos:
        return stats
    malos = stats.loc[stats["equipo_nombre"].isin(excluidos), "partido_id"].unique()
    return stats[~stats["partido_id"].isin(malos)].reset_index(drop=True)


def load_dataset(
    stats_path: Path | None = None,
    tel_path: Path | None = None,
    pred_path: Path | None = None,
    legacy: bool = False,
) -> Dataset:
    stats = _read_csv(stats_path or config.STATS_CSV)
    tel = _read_csv(tel_path or config.TELEMETRIA_CSV)
    pred = _read_csv(pred_path or config.PARTIDOS_CSV)

    # La primera columna de pred puede haber quedado con BOM en otros lectores;
    # con utf-8-sig ya viene limpia, pero forzamos el nombre por robustez.
    pred = pred.rename(columns={pred.columns[0]: "partido_id"})

    # --- Limpieza de nombres de equipo ---
    for col in ("equipo_a", "equipo_b"):
        if col in pred.columns:
            pred[col] = _limpia_nombre(pred[col])
    if "equipo_nombre" in stats.columns:
        stats["equipo_nombre"] = _limpia_nombre(stats["equipo_nombre"])
    for col in ("home_team", "away_team"):
        if col in tel.columns:
            tel[col] = _limpia_nombre(tel[col])

    # --- Purga de clubes / no-selecciones (partido entero) ---
    # legacy=True conserva el dataset original (necesario para la regresión
    # contra el golden del R, que se generó con esos equipos dentro).
    if not legacy:
        stats = _excluir_no_selecciones(stats)

    # --- Verificación de encoding (como los stopifnot del R) ---
    nombres_stats = set(stats["equipo_nombre"].dropna())
    for esperado in ("Curaçao", "Türkiye", "Côte d'Ivoire"):
        norm = unicodedata.normalize("NFC", esperado)
        assert norm in nombres_stats, f"Encoding: '{esperado}' no encontrado en stats"

    metricas = _clean_stats(stats, legacy=legacy)

    # Fecha/torneo por partido (backfill); habilita recencia y backtest temporal.
    if not legacy and config.PARTIDO_FECHAS_CSV.exists():
        stats = _merge_fechas(stats)
        stats = _excluir_fecha_futura(stats)

    _clean_tel(tel)

    return Dataset(stats=stats, tel=tel, pred=pred, metricas_equipo=metricas, legacy=legacy)


def _clean_stats(stats: pd.DataFrame, legacy: bool = False) -> list[str]:
    """Limpieza de stats in-place. Devuelve la lista de métricas presentes."""
    # 2.1 NA->0 en eventos raros
    for c in config.COLS_RARAS_STATS:
        if c in stats.columns:
            stats[c] = pd.to_numeric(stats[c], errors="coerce").fillna(0.0)

    # 2.2 Derivar oponente y goles_op mediante self-join por partido_id
    stats["goles"] = pd.to_numeric(stats["goles"], errors="coerce")
    op = stats[["partido_id", "equipo_nombre", "goles"]].rename(
        columns={"equipo_nombre": "oponente", "goles": "goles_op"}
    )
    merged = stats.merge(op, on="partido_id", how="inner")  # cartesiano por grupo
    merged = merged[merged["equipo_nombre"] != merged["oponente"]].reset_index(drop=True)
    stats_cols = list(stats.columns) + ["oponente", "goles_op"]
    # reasignamos las columnas al DataFrame original mutándolo
    stats.drop(stats.index, inplace=True)
    for c in stats_cols:
        stats[c] = merged[c].values

    # 2.5 Métricas presentes (orden canónico) + tipado numérico
    metricas = [m for m in config.METRICAS_EQUIPO if m in stats.columns]
    _to_numeric(stats, metricas)

    # 2.5b Marcar filas SIN stats reales (partidos de baja cobertura en SofaScore).
    # La imputación 2.6 las rellenaría con medianas → "clones" que el bootstrap
    # muestrearía como partidos reales, comprimiendo varianza y rompiendo las
    # correlaciones entre métricas. El pool las excluye; fuerza/ELO (solo goles
    # reales) las conserva. Se calcula ANTES de imputar.
    # legacy: todas "completas" → el pool no filtra nada (reproduce el R).
    core = [c for c in ("ball_possession", "total_shots", "passes", "corner_kicks")
            if c in stats.columns]
    if legacy or not core:
        stats["stats_completas"] = True
    else:
        stats["stats_completas"] = stats[core].notna().any(axis=1)

    # 2.6 Imputar NAs con la mediana del propio equipo (fallback: mediana global)
    for m in metricas:
        global_med = stats[m].median(skipna=True)
        team_med = stats.groupby("equipo_nombre")[m].transform("median")
        team_med = team_med.fillna(global_med)
        stats[m] = stats[m].fillna(team_med)

    return metricas


def _clean_tel(tel: pd.DataFrame) -> None:
    """Limpieza de telemetría in-place (NA->0 en métricas de jugador)."""
    cols_raras_tel = [
        "penaltySave", "penaltyMiss", "penaltyConceded", "penaltyWon",
        "penaltyFaced", "errorLeadToAGoal", "errorLeadToAShot", "ownGoals",
        "goalsPrevented", "penaltyShootoutGoal", "penaltyShootoutMiss",
        "penaltyShootoutSave", "hitWoodwork", "clearanceOffLine",
        "lastManTackle", "crossNotClaimed", "bigChanceCreated",
        "bigChanceMissed", "expectedGoals", "expectedGoalsOnTarget",
        "expectedAssists",
    ]
    for c in cols_raras_tel:
        if c in tel.columns:
            tel[c] = pd.to_numeric(tel[c], errors="coerce").fillna(0.0)
