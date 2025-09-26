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

from dataclasses import dataclass, fields as dataclass_fields
from typing import Callable, Any

import numpy as np
import pandas as pd
from pyama_core.processing.extraction.feature import (
    get_feature_extractor,
    list_features,
    ExtractionContext,
)

FeatureResult = dict[str, float]


@dataclass(frozen=True)
class ResultIndex:
    cell: int
    time: float


@dataclass(frozen=True)
class Result(ResultIndex):
    good: bool
    position_x: float
    position_y: float


@dataclass(frozen=True)
class ResultWithFeatures(Result):
    features: FeatureResult


def _extract_position(ctx: ExtractionContext) -> tuple[float, float]:
    """Extract centroid position for a single cell mask.

    Parameters:
    - ctx: Extraction context containing cell mask

    Returns:
    - (x, y) centroid coordinates, or (nan, nan) if empty mask
    """
    # Fast bounding-box-based centroid approximation.
    # Find rows and columns that contain mask pixels and compute the
    # center of the bounding box. This avoids scanning all masked
    # coordinates and is much faster for large masks.
    mask = ctx.mask
    row_inds = np.where(mask.any(axis=1))[0]
    col_inds = np.where(mask.any(axis=0))[0]
    if row_inds.size == 0 or col_inds.size == 0:
        return (np.nan, np.nan)
    # Use bounding box center as position (x: columns, y: rows)
    x0, x1 = col_inds[0], col_inds[-1]
    y0, y1 = row_inds[0], row_inds[-1]
    position_x = float((x0 + x1) / 2.0)
    position_y = float((y0 + y1) / 2.0)
    return (position_x, position_y)


def _extract_single_frame(
    image: np.ndarray,
    seg_labeled: np.ndarray,
    time: float,
) -> list[ResultWithFeatures]:
    """Extract features for all cells in a single frame.

    Parameters:
    - image: 2D fluorescence image
    - seg_labeled: 2D labeled image with cell IDs
    - time: time of the frame
    Returns:
    - Dictionary mapping cell_id -> feature_dict
    """
    cells = np.unique(seg_labeled)
    cells = cells[cells > 0]

    # Prefetch extractors once per frame for efficiency
    feature_names: list[str] = list_features()
    extractors: dict[str, Callable[[ExtractionContext], float]] = {
        name: get_feature_extractor(name) for name in feature_names
    }

    results: list[ResultWithFeatures] = []
    for c in cells:
        mask = seg_labeled == c
        ctx = ExtractionContext(image=image, mask=mask)

        features: FeatureResult = {}
        for name, extractor in extractors.items():
            features[name] = float(extractor(ctx))

        position_x, position_y = _extract_position(ctx)
        results.append(
            ResultWithFeatures(
                cell=int(c),
                time=float(time),
                good=True,
                position_x=position_x,
                position_y=position_y,
                features=features,
            )
        )

    return results


def _extract_all(
    image: np.ndarray,
    seg_labeled: np.ndarray,
    times: np.ndarray,
    progress_callback: Callable | None = None,
) -> pd.DataFrame:
    """Build trace DataFrame from fluorescence and label stacks.

    Creates a flat DataFrame where each row corresponds to a
    (cell, time) observation, with columns derived from the
    ResultWithFeatures dataclass plus feature columns.

    Parameters:
    - image: 3D (T, H, W) fluorescence stack
    - seg_labeled: 3D (T, H, W) labeled stack with tracked cell IDs
    - times: 1D (T) time array in seconds
    - progress_callback: Optional callback for progress updates

    Returns:
    - DataFrame with columns [cell, time, exist, good, position_x,
      position_y, <feature columns>]
    """
    # Build rows directly from the dataclass without a MultiIndex.
    # Strategy: determine index fields first, then base fields, then features.
    # This ensures the resulting DataFrame columns are ordered as the user requested.
    index_fields = [f.name for f in dataclass_fields(ResultIndex)]
    # Exclude index fields and the nested features dict from base fields
    exclude_names = set(index_fields) | {"features"}
    base_fields = [
        f.name
        for f in dataclass_fields(ResultWithFeatures)
        if f.name not in exclude_names
    ]
    feature_names = list_features()

    T, H, W = image.shape
    # Precompute column names in the requested ordering: index, base, features
    col_names = index_fields + base_fields + feature_names
    cols: dict[str, list[Any]] = {name: [] for name in col_names}

    for t in range(T):
        frame_result = _extract_single_frame(image[t], seg_labeled[t], times[t])
        if progress_callback is not None:
            progress_callback(t, T, "Extracting features")

        # Extend in the requested order to minimize peak memory
        for name in index_fields:
            cols[name].extend([getattr(res, name) for res in frame_result])
        for name in base_fields:
            cols[name].extend([getattr(res, name) for res in frame_result])
        for fname in feature_names:
            cols[fname].extend(
                [res.features.get(fname, np.nan) for res in frame_result]
            )

    df = pd.DataFrame(cols, columns=col_names)
    df.set_index(index_fields, inplace=True)
    return df


def _filter_by_length(df: pd.DataFrame, min_length: int = 30) -> pd.DataFrame:
    """Filter traces by minimum number of existing frames.

    Parameters:
    - df: Trace DataFrame with multi-index (cell, time)
    - min_length: Minimum number of frames a cell must exist

    Returns:
    - Filtered DataFrame containing only cells with sufficient length
    """
    # Use the MultiIndex level directly to avoid an expensive groupby
    # on a non-existent column. This computes per-cell counts once and
    # filters rows by whether their cell appears at least `min_length` times.
    cell_level = df.index.get_level_values("cell")
    counts = cell_level.value_counts()
    valid_cells = counts.index[counts >= min_length]
    return df[cell_level.isin(valid_cells)]


def extract_trace(
    image: np.ndarray,
    seg_labeled: np.ndarray,
    times: np.ndarray,
    progress_callback: Callable | None = None,
) -> pd.DataFrame:
    """Extract and filter cell traces from microscopy time-series.

    This is the main public function that orchestrates the complete
    trace extraction pipeline:
    - Perform IoU-based cell tracking on binary masks
    - Extract features for each cell in each frame
    - Filter traces by length and quality criteria
    - Return cleaned DataFrame with only high-quality traces

    Parameters:
    - image: 3D (T, H, W) fluorescence image stack
    - seg_labeled: 3D (T, H, W) labeled segmentation stack
    - times: 1D (T) time array in seconds
    - progress_callback: Optional function(frame, total, message) for progress

    Returns:
    - Filtered flat DataFrame containing position coordinates and
      extracted features for high-quality traces
    """
    if image.ndim != 3 or seg_labeled.ndim != 3:
        raise ValueError("image and seg_labeled must be 3D arrays")

    if image.shape != seg_labeled.shape:
        raise ValueError("image and seg_labeled must have the same shape")

    if times.ndim != 1:
        raise ValueError("time must be 1D array")

    if image.shape[0] != times.shape[0]:
        raise ValueError("image and time must have the same length")

    image = image.astype(np.float32, copy=False)
    seg_labeled = seg_labeled.astype(np.uint16, copy=False)
    times = times.astype(float, copy=False)

    # Perform tracking then build raw traces
    df = _extract_all(image, seg_labeled, times, progress_callback)

    # Apply filtering and cleanup
    df = _filter_by_length(df)

    return df
