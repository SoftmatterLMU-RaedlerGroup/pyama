"""
Trace calculation algorithms for microscopy image analysis.
"""

from typing import Callable, Any

import numpy as np
import pandas as pd
from pyama_core.processing import track_cells
from pyama_core.analysis.features import FEATURE_EXTRACTORS, ExtractionContext


def extract_position(ctx: ExtractionContext) -> tuple[float, float]:
    y_coords, x_coords = np.where(ctx.cell_mask)
    if len(x_coords) == 0:
        return (np.nan, np.nan)
    position_x = float(np.mean(x_coords))
    position_y = float(np.mean(y_coords))
    return (position_x, position_y)


def extract_cell_features(
    fluor_frame: np.ndarray, label_frame: np.ndarray
) -> dict[int, dict[str, Any]]:
    if fluor_frame.shape != label_frame.shape:
        raise ValueError("Fluorescence and label frames must have the same shape")

    cell_ids = np.unique(label_frame)
    cell_ids = cell_ids[cell_ids > 0]

    results = {}
    for cell_id in cell_ids:
        cell_mask = label_frame == cell_id
        ctx = ExtractionContext(fluor_frame=fluor_frame, cell_mask=cell_mask)
        cell_features = {}
        for feature_name, extractor_func in FEATURE_EXTRACTORS.items():
            cell_features[feature_name] = extractor_func(ctx)
        cell_features["position"] = extract_position(ctx)
        results[int(cell_id)] = cell_features

    return results


def extract_traces_with_tracking(
    fluor_stack: np.ndarray,
    binary_stack: np.ndarray,
    progress_callback: Callable | None = None,
) -> pd.DataFrame:
    label_stack = track_cells(binary_stack, progress_callback=progress_callback)
    return extract_traces_from_tracking(fluor_stack, label_stack, progress_callback)


def extract_traces_from_tracking(
    fluor_stack: np.ndarray,
    label_stack: np.ndarray,
    progress_callback: Callable | None = None,
) -> pd.DataFrame:
    if fluor_stack.shape != label_stack.shape:
        raise ValueError("Fluorescence and label stacks must have the same shape")

    n_frames = fluor_stack.shape[0]
    all_cell_ids = set()
    for frame_idx in range(n_frames):
        frame_ids = np.unique(label_stack[frame_idx])
        all_cell_ids.update(frame_ids[frame_ids > 0])
    all_cell_ids = sorted(all_cell_ids)

    feature_names = list(FEATURE_EXTRACTORS.keys())
    index = pd.MultiIndex.from_product(
        [all_cell_ids, range(n_frames)], names=["cell_id", "frame"]
    )
    columns = ["exist", "good", "position_x", "position_y"] + feature_names
    df = pd.DataFrame(index=index, columns=columns)
    df["exist"] = False
    df["good"] = True
    df["position_x"] = np.nan
    df["position_y"] = np.nan
    for feature in feature_names:
        df[feature] = np.nan

    for frame_idx in range(n_frames):
        frame_properties = extract_cell_features(
            fluor_stack[frame_idx], label_stack[frame_idx]
        )
        if progress_callback and frame_idx % 30 == 0:
            progress_callback(frame_idx, n_frames, "Extracting features")
        for cell_id, props in frame_properties.items():
            df.loc[(cell_id, frame_idx), "exist"] = True
            df.loc[(cell_id, frame_idx), "position_x"] = props["position"][0]
            df.loc[(cell_id, frame_idx), "position_y"] = props["position"][1]
            for feature in feature_names:
                df.loc[(cell_id, frame_idx), feature] = props[feature]

    return df


def filter_traces_by_length(
    traces_df: pd.DataFrame, min_length: int = 3
) -> pd.DataFrame:
    valid_counts = traces_df.groupby(level="cell_id")["exist"].sum()
    valid_cells = valid_counts[valid_counts >= min_length].index
    return traces_df.loc[valid_cells]


def filter_traces_by_vitality(traces_df: pd.DataFrame) -> pd.DataFrame:
    return traces_df


def filter_traces(traces_df: pd.DataFrame, min_length: int = 3) -> pd.DataFrame:
    filtered_df = filter_traces_by_length(traces_df, min_length)
    filtered_df = filter_traces_by_vitality(filtered_df)
    filtered_df = filtered_df[filtered_df["exist"]].drop(columns=["exist"])
    return filtered_df


