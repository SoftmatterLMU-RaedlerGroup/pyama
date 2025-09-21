"""Mapping utilities for converting processing CSV data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .loader import load_processing_csv
from .schema import ProcessingCSVRow


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
                    positions[time_point] = (float(row["position_x"]), float(row["position_y"]))
                except (ValueError, TypeError):
                    continue
            if positions:
                result["positions"][int(cell_id)] = positions

    basic_cols = set(ProcessingCSVRow.__annotations__.keys())
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


__all__ = ["parse_trace_data"]
