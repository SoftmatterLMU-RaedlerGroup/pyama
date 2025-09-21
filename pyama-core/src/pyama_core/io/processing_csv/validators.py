"""Validation helpers for processing CSV data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .loader import load_processing_csv
from .schema import ProcessingCSVRow


def validate_processing_csv(df: pd.DataFrame) -> bool:
    """Validate that the DataFrame has the expected processing CSV format."""
    required_cols = list(ProcessingCSVRow.__annotations__.keys())
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


__all__ = ["get_fov_metadata", "validate_processing_csv"]
