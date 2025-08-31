"""Trace extraction for microscopy time-series analysis (functional API).

Pipeline:
- Track cells across time using IoU-based tracking
- Extract features for each cell in each frame
- Filter traces by length and quality criteria

This implementation follows the functional style used in other processing modules
and is designed for performance with time-series datasets:
- Processes stacks frame-by-frame to manage memory usage
- Uses vectorized operations for feature extraction
- Provides progress callbacks for long-running operations
- Filters traces to remove short-lived or low-quality cells
"""

from typing import Callable, Any

import numpy as np
import pandas as pd
from pyama_core.processing.tracking.iou import track_cell
from pyama_core.processing.extraction.feature import (
    FEATURE_EXTRACTORS,
    ExtractionContext,
)


def _extract_position(ctx: ExtractionContext) -> tuple[float, float]:
    """Extract centroid position for a single cell mask.

    Parameters:
    - ctx: Extraction context containing cell mask

    Returns:
    - (x, y) centroid coordinates, or (nan, nan) if empty mask
    """
    y_coords, x_coords = np.where(ctx.cell_mask)
    if len(x_coords) == 0:
        return (np.nan, np.nan)
    position_x = float(np.mean(x_coords))
    position_y = float(np.mean(y_coords))
    return (position_x, position_y)


def _extract_frame_features(
    fluor_frame: np.ndarray, label_frame: np.ndarray
) -> dict[int, dict[str, Any]]:
    """Extract features for all cells in a single frame.

    Parameters:
    - fluor_frame: 2D fluorescence image
    - label_frame: 2D labeled image with cell IDs

    Returns:
    - Dictionary mapping cell_id -> feature_dict
    """
    if fluor_frame.ndim != 2 or label_frame.ndim != 2:
        raise ValueError("fluor_frame and label_frame must be 2D arrays")

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
        cell_features["position"] = _extract_position(ctx)
        results[int(cell_id)] = cell_features

    return results


def _build_trace_dataframe(
    fluor_stack: np.ndarray,
    label_stack: np.ndarray,
    progress_callback: Callable | None = None,
) -> pd.DataFrame:
    """Build trace DataFrame from fluorescence and label stacks.

    Creates a multi-indexed DataFrame with (cell_id, frame) index and
    columns for existence, position, and extracted features.

    Parameters:
    - fluor_stack: 3D (T, H, W) fluorescence stack
    - label_stack: 3D (T, H, W) labeled stack with tracked cell IDs
    - progress_callback: Optional callback for progress updates

    Returns:
    - DataFrame with multi-index (cell_id, frame) and feature columns
    """
    if fluor_stack.ndim != 3 or label_stack.ndim != 3:
        raise ValueError("fluor_stack and label_stack must be 3D arrays")

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
        frame_properties = _extract_frame_features(
            fluor_stack[frame_idx], label_stack[frame_idx]
        )
        # Delegate throttling to the callback implementation; only check for
        # presence here.
        if progress_callback is not None:
            progress_callback(frame_idx, n_frames, "Extracting features")
        for cell_id, props in frame_properties.items():
            df.loc[(cell_id, frame_idx), "exist"] = True
            df.loc[(cell_id, frame_idx), "position_x"] = props["position"][0]
            df.loc[(cell_id, frame_idx), "position_y"] = props["position"][1]
            for feature in feature_names:
                df.loc[(cell_id, frame_idx), feature] = props[feature]

    return df


def _filter_by_length(traces_df: pd.DataFrame, min_length: int = 3) -> pd.DataFrame:
    """Filter traces by minimum number of existing frames.

    Parameters:
    - traces_df: Trace DataFrame with multi-index (cell_id, frame)
    - min_length: Minimum number of frames a cell must exist

    Returns:
    - Filtered DataFrame containing only cells with sufficient length
    """
    if not isinstance(traces_df, pd.DataFrame):
        raise ValueError("traces_df must be a pandas DataFrame")

    if "exist" not in traces_df.columns:
        raise ValueError("traces_df must have 'exist' column")

    valid_counts = traces_df.groupby(level="cell_id")["exist"].sum()
    valid_cells = valid_counts[valid_counts >= min_length].index
    return traces_df.loc[valid_cells]


def _filter_by_vitality(traces_df: pd.DataFrame) -> pd.DataFrame:
    """Filter traces by cell vitality criteria.

    Currently a pass-through function for future extension with
    biological quality filters.

    Parameters:
    - traces_df: Trace DataFrame with multi-index (cell_id, frame)

    Returns:
    - Filtered DataFrame (currently unchanged)
    """
    if not isinstance(traces_df, pd.DataFrame):
        raise ValueError("traces_df must be a pandas DataFrame")
    return traces_df


def _apply_trace_filters(traces_df: pd.DataFrame, min_length: int = 30) -> pd.DataFrame:
    """Apply all trace filtering criteria and clean up columns.

    Parameters:
    - traces_df: Raw trace DataFrame with multi-index (cell_id, frame)
    - min_length: Minimum number of frames a cell must exist

    Returns:
    - Filtered DataFrame with only existing frames and cleaned columns
    """
    filtered_df = _filter_by_length(traces_df, min_length)
    filtered_df = _filter_by_vitality(filtered_df)
    filtered_df = filtered_df[filtered_df["exist"]].drop(columns=["exist"])
    return filtered_df


# Note: helper extract_traces_with_tracking has been absorbed into extract_trace
# to keep API surface minimal.


# Note: previously exposed extract_traces_from_tracking has been removed to
# keep the public API focused on extract_trace(). If needed, this helper can
# be reintroduced with proper deprecation and testing.


def extract_trace(
    fluor_stack: np.ndarray,
    binary_stack: np.ndarray,
    progress_callback: Callable | None = None,
    min_length: int = 30,
) -> pd.DataFrame:
    """Extract and filter cell traces from microscopy time-series.

    This is the main public function that orchestrates the complete
    trace extraction pipeline:
    - Perform IoU-based cell tracking on binary masks
    - Extract features for each cell in each frame
    - Filter traces by length and quality criteria
    - Return cleaned DataFrame with only high-quality traces

    Parameters:
    - fluor_stack: 3D (T, H, W) fluorescence image stack
    - binary_stack: 3D (T, H, W) binary segmentation stack
    - progress_callback: Optional function(frame, total, message) for progress
    - min_length: Minimum number of frames a cell must exist (default: 30)

    Returns:
    - Filtered DataFrame with multi-index (cell_id, frame) containing
      position coordinates and extracted features for high-quality traces
    """
    if fluor_stack.ndim != 3 or binary_stack.ndim != 3:
        raise ValueError("fluor_stack and binary_stack must be 3D arrays")

    if fluor_stack.shape != binary_stack.shape:
        raise ValueError("fluor_stack and binary_stack must have the same shape")

    if min_length < 1:
        raise ValueError("min_length must be positive")

    # Perform tracking then build raw traces
    label_stack = track_cell(binary_stack, progress_callback=progress_callback)
    traces_df = _build_trace_dataframe(fluor_stack, label_stack, progress_callback)

    # Apply filtering and cleanup
    traces_df = _apply_trace_filters(traces_df, min_length)

    return traces_df
