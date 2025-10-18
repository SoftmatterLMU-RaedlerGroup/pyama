"""Feature map helpers used during merge operations."""

from __future__ import annotations

from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from pyama_core.processing.extraction.trace import Result

from .types import FeatureMaps


def build_feature_maps(rows: List[dict], feature_names: List[str]) -> FeatureMaps:
    """Build feature maps filtered by 'good' rows."""
    feature_maps: Dict[str, Dict[Tuple[float, int], float]] = {
        feature_name: {} for feature_name in feature_names
    }
    times_set: set[float] = set()
    cells_set: set[int] = set()

    for row in rows:
        if "good" in row and not row["good"]:
            continue
        time = row.get("time")
        cell = row.get("cell")
        if time is None or cell is None:
            continue

        key = (float(time), int(cell))
        times_set.add(float(time))
        cells_set.add(int(cell))

        for feature_name in feature_names:
            if feature_name in row:
                value = row[feature_name]
                if value is not None:
                    feature_maps[feature_name][key] = float(value)

    return FeatureMaps(
        features=feature_maps,
        times=sorted(times_set),
        cells=sorted(cells_set),
    )


def extract_channel_dataframe(df: pd.DataFrame, channel: int) -> pd.DataFrame:
    """Return a dataframe containing features for a single channel."""
    suffix = f"_ch_{channel}"
    base_fields = ["fov"] + [field.name for field in dataclass_fields(Result)]
    base_cols = [col for col in base_fields if col in df.columns]
    feature_cols = [col for col in df.columns if col.endswith(suffix)]
    rename_map = {col: col[: -len(suffix)] for col in feature_cols}

    selected_cols = base_cols + feature_cols
    if not selected_cols:
        return pd.DataFrame()

    channel_df = df[selected_cols].copy()
    if rename_map:
        channel_df.rename(columns=rename_map, inplace=True)
    return channel_df


def get_all_times(feature_maps_by_fov: Dict[int, FeatureMaps], fovs: Iterable[int]) -> List[float]:
    """Collect sorted unique time points across FOVs."""
    times: set[float] = set()
    for fov in fovs:
        feature_maps = feature_maps_by_fov.get(fov)
        if feature_maps:
            times.update(feature_maps.times)
    return sorted(times)


def write_feature_csv(
    out_path: Path,
    times: List[float],
    fovs: Iterable[int],
    feature_name: str,
    feature_maps_by_fov: Dict[int, FeatureMaps],
    channel: int,
    time_units: str | None = None,
) -> None:
    """Write a feature CSV mirroring the Qt merge output."""
    all_cells: set[int] = set()
    fov_list = list(fovs)
    for fov in fov_list:
        feature_maps = feature_maps_by_fov.get(fov)
        if feature_maps:
            all_cells.update(feature_maps.cells)

    sorted_cells = sorted(all_cells)
    columns = ["time"]
    for fov in fov_list:
        for cell in sorted_cells:
            columns.append(f"fov_{fov:03d}_cell_{cell}")

    rows = []
    for time in times:
        row = [time]
        for fov in fov_list:
            feature_maps = feature_maps_by_fov.get(fov)
            for cell in sorted_cells:
                value = None
                if feature_maps and feature_name in feature_maps.features:
                    value = feature_maps.features[feature_name].get((time, cell))
                row.append(value)
        rows.append(row)

    df = pd.DataFrame(rows, columns=columns)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if time_units:
        with out_path.open("w", encoding="utf-8") as handle:
            handle.write(f"# Time units: {time_units}\n")
            df.to_csv(handle, index=False, float_format="%.6f")
    else:
        df.to_csv(out_path, index=False, float_format="%.6f")
