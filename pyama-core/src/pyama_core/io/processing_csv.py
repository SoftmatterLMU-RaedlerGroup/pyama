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
import logging

import pandas as pd

from pyama_core.processing.extraction.trace import Result

logger = logging.getLogger(__name__)


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


def get_cell_ids(df: pd.DataFrame) -> list[int]:
    """Get sorted list of unique cell IDs from DataFrame."""
    if "cell" not in df.columns:
        return []
    return sorted([int(cid) for cid in df["cell"].unique()])


def get_good_cell_ids(df: pd.DataFrame) -> set[int]:
    """Get set of cell IDs marked as good quality."""
    if "good" not in df.columns:
        return set()
    return {int(cid) for cid in df[df["good"]]["cell"].unique()}


def get_positions_for_cell(
    df: pd.DataFrame, cell_id: int
) -> dict[int, tuple[float, float]]:
    """Get positions (frame -> (x, y)) for a specific cell."""
    cell_df = df[df["cell"] == cell_id]
    if cell_df.empty or "frame" not in cell_df.columns:
        return {}

    positions = {}
    for _, row in cell_df.iterrows():
        try:
            frame = int(row["frame"])
            x = float(row["position_x"])
            y = float(row["position_y"])
            positions[frame] = (x, y)
        except (ValueError, TypeError, KeyError):
            continue
    return positions


def get_feature_values_for_cell(
    df: pd.DataFrame, cell_id: int, feature: str
) -> list[float]:
    """Get time series values for a specific feature and cell."""
    cell_df = df[df["cell"] == cell_id].sort_values("time")
    if cell_df.empty or feature not in cell_df.columns:
        return []

    values = []
    for _, row in cell_df.iterrows():
        try:
            values.append(float(row[feature]))
        except (ValueError, TypeError):
            values.append(float("nan"))
    return values


def get_available_features(df: pd.DataFrame) -> list[str]:
    """Get list of feature column names (excluding basic processing fields)."""
    basic_cols = set(_PROCESSING_ROW_FIELDS)
    return [col for col in df.columns if col not in basic_cols]


def get_feature_data_for_cell(df: pd.DataFrame, cell_id: int) -> dict[str, list[float]]:
    """Get all feature data for a specific cell."""
    features = get_available_features(df)
    return {
        feature: get_feature_values_for_cell(df, cell_id, feature)
        for feature in features
    }


def get_time_for_cell(df: pd.DataFrame, cell_id: int) -> list[float]:
    """Get time values for a specific cell (sorted by time)."""
    cell_df = df[df["cell"] == cell_id].sort_values("time")
    if cell_df.empty or "time" not in cell_df.columns:
        return []

    times = []
    for _, row in cell_df.iterrows():
        try:
            times.append(float(row["time"]))
        except (ValueError, TypeError):
            continue
    return times


# Legacy function for backward compatibility - can be removed once downstream is updated
def parse_trace_data(csv_path: Path) -> dict:
    """Parse trace data from a processing CSV file into a dictionary."""
    df = load_processing_csv(csv_path)

    if "cell" not in df.columns:
        return {"cells": [], "features": {}, "positions": {}, "good_cells": set()}

    cell_ids = get_cell_ids(df)
    good_cells = get_good_cell_ids(df)
    positions = {cell_id: get_positions_for_cell(df, cell_id) for cell_id in cell_ids}
    features = {
        feature: {
            cell_id: get_feature_values_for_cell(df, cell_id, feature)
            for cell_id in cell_ids
        }
        for feature in get_available_features(df)
    }

    return {
        "cells": cell_ids,
        "good_cells": good_cells,
        "positions": positions,
        "features": features,
    }


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

    for col in ["fov", "cell", "frame"]:
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

    if "frame" in df.columns:
        metadata["frame_count"] = df["frame"].nunique()

    return metadata
