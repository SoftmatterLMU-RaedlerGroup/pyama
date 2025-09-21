"""Loading utilities for processing CSV files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schema import ProcessingCSVRow


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


__all__ = [
    "filter_good_traces",
    "get_cell_count",
    "load_processing_csv",
]
