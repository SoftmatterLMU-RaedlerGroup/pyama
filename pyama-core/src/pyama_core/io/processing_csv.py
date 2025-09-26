"""
Processing CSV format definitions for PyAMA sample data.

This module defines utilities for handling CSV files consumed by the
processing module. The format includes FOV information, cell tracking data,
and extracted features.

Format: fov, cell, time, position data, and dynamic feature columns
"""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields
from pathlib import Path

import pandas as pd

from pyama_core.processing.extraction.trace import Result


@dataclass(frozen=True)
class ProcessingCSVRow(Result):
    """Row structure for processing CSV files with dynamic feature columns."""

    fov: int


_PROCESSING_ROW_FIELDS = tuple(
    field.name for field in dataclass_fields(ProcessingCSVRow)
)


def load_processing_csv(csv_path: Path) -> pd.DataFrame:
    """Load trace data from a processing CSV file."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:  # pragma: no cover - pandas error propagation
        raise ValueError(f"Failed to read CSV file: {exc}") from exc

    if df.empty:
        raise ValueError(f"CSV file is empty: {csv_path}")

    if "good" not in df.columns:
        df["good"] = True

    return df


def filter_good_traces(df: pd.DataFrame) -> pd.DataFrame:
    """Return only traces flagged as good."""
    if "good" not in df.columns:
        return df
    return df[df["good"]].copy()


def get_cell_count(csv_path: Path) -> int:
    """Get the number of unique cells in a processing CSV file."""
    try:
        df = load_processing_csv(csv_path)
        return df["cell"].nunique()
    except Exception:
        return 0


def parse_trace_data(csv_path: Path) -> dict:
    """Parse trace data from a processing CSV file into a dictionary."""
    df = load_processing_csv(csv_path)

    result = {"cell_ids": [], "features": {}, "positions": {}, "good_cells": set()}

    if "cell" not in df.columns:
        return result

    cell_ids = df["cell"].unique()
    result["cell_ids"] = sorted([int(cid) for cid in cell_ids])

    if "good" in df.columns:
        good_cells = df[df["good"]]["cell"].unique()
        result["good_cells"] = {int(cid) for cid in good_cells}

    if "position_x" in df.columns and "position_y" in df.columns:
        for cell_id in cell_ids:
            cell_df = df[df["cell"] == cell_id]
            if cell_df.empty:
                continue
            positions = {}
            for _, row in cell_df.iterrows():
                try:
                    time_point = int(row["time"])
                    positions[time_point] = (
                        float(row["position_x"]),
                        float(row["position_y"]),
                    )
                except (ValueError, TypeError):
                    continue
            if positions:
                result["positions"][int(cell_id)] = positions

    basic_cols = set(_PROCESSING_ROW_FIELDS)
    feature_cols = [col for col in df.columns if col not in basic_cols]

    for feature in feature_cols:
        feature_map: dict[int, list[float]] = {}
        for cell_id in cell_ids:
            cell_df = df[df["cell"] == cell_id].sort_values("time")
            if cell_df.empty:
                continue
            values = []
            for _, row in cell_df.iterrows():
                try:
                    values.append(float(row[feature]))
                except (ValueError, TypeError):
                    values.append(float("nan"))
            feature_map[int(cell_id)] = values
        result["features"][feature] = feature_map

    return result


def validate_processing_csv(df: pd.DataFrame) -> bool:
    """Validate that the DataFrame has the expected processing CSV format."""
    required_cols = list(_PROCESSING_ROW_FIELDS)
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return False

    for col in required_cols:
        if col in df.columns:
            try:
                pd.to_numeric(df[col], errors="raise")
            except (ValueError, TypeError):
                return False

    for col in ["fov", "cell"]:
        if col in df.columns:
            numeric_series = pd.to_numeric(df[col], errors="coerce")
            if (
                numeric_series.isnull().any()
                or not (numeric_series == numeric_series.astype(int)).all()
            ):
                return False

    return True


def get_fov_metadata(csv_path: Path) -> dict:
    """Extract metadata from a processing CSV file."""
    df = load_processing_csv(csv_path)

    metadata = {"file_path": csv_path}

    if "fov" in df.columns and len(df) > 0:
        fov_values = df["fov"].dropna().unique()
        metadata["fov_index"] = int(fov_values[0]) if len(fov_values) == 1 else 0

    if "cell" in df.columns:
        metadata["cell_count"] = df["cell"].nunique()

    if "time" in df.columns:
        metadata["time_count"] = df["time"].nunique()

    return metadata
