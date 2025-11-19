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

from dataclasses import fields as dataclass_fields
from typing import Callable, Any

import numpy as np
import pandas as pd

from pyama_core.processing.extraction.features import (
    ExtractionContext,
    get_feature_extractor,
    list_features,
)
from pyama_core.types.processing import (
    FeatureResult,
    Result,
    ResultWithFeatures,
)


def _extract_position_and_bbox(
    ctx: ExtractionContext,
) -> tuple[float, float, float, float, float, float]:
    """Extract centroid position and bounding box for a single cell mask.

    Parameters:
    - ctx: Extraction context containing cell mask

    Returns:
    - (position_x, position_y, bbox_x0, bbox_y0, bbox_x1, bbox_y1) coordinates, or (nan, nan, nan, nan, nan, nan) if empty mask
    """
    # Fast bounding-box-based centroid approximation.
    # Find rows and columns that contain mask pixels and compute the
    # center of the bounding box. This avoids scanning all masked
    # coordinates and is much faster for large masks.
    mask = ctx.mask
    row_inds = np.where(mask.any(axis=1))[0]
    col_inds = np.where(mask.any(axis=0))[0]
    if row_inds.size == 0 or col_inds.size == 0:
        return (np.nan, np.nan, np.nan, np.nan, np.nan, np.nan)
    # Use bounding box center as position (x: columns, y: rows)
    x0, x1 = col_inds[0], col_inds[-1]
    y0, y1 = row_inds[0], row_inds[-1]
    position_x = float((x0 + x1) / 2.0)
    position_y = float((y0 + y1) / 2.0)
    return (position_x, position_y, float(x0), float(y0), float(x1), float(y1))


def _extract_single_frame(
    image: np.ndarray,
    seg_labeled: np.ndarray,
    frame: int,
    time: float,
    background: np.ndarray,
    feature_names: list[str] | None = None,
    background_weight: float = 0.0,
    erosion_size: int = 0,
) -> list[ResultWithFeatures]:
    """Extract features for all cells in a single frame.

    Parameters:
    - image: 2D fluorescence image
    - seg_labeled: 2D labeled image with cell IDs
    - frame: frame index
    - time: time of the frame
    - background: 2D background image for correction (always provided)
    - feature_names: Optional list of feature names to extract
    - background_weight: Weight for background subtraction (default: 0.0)
    - erosion_size: Number of pixels to erode the mask (default: 0, no erosion)
    Returns:
    - List of ResultWithFeatures for all cells in the frame
    """
    cells = np.unique(seg_labeled)
    cells = cells[cells > 0]

    # Prefetch extractors once per frame for efficiency
    if feature_names is None:
        feature_names = list_features()  # Use all features if not specified
    extractors: dict[str, Callable[[ExtractionContext], float]] = {
        name: get_feature_extractor(name) for name in feature_names
    }

    results: list[ResultWithFeatures] = []
    # Background is always provided as an array
    
    for c in cells:
        mask = seg_labeled == c
        
        # Skip empty masks
        if not mask.any():
            continue
        
        ctx = ExtractionContext(
            image=image, mask=mask, background=background, background_weight=background_weight, erosion_size=erosion_size
        )

        features: FeatureResult = {}
        for name, extractor in extractors.items():
            features[name] = float(extractor(ctx))

        position_x, position_y, bbox_x0, bbox_y0, bbox_x1, bbox_y1 = (
            _extract_position_and_bbox(ctx)
        )
        results.append(
            ResultWithFeatures(
                cell=int(c),
                frame=int(frame),
                time=float(time),
                good=True,
                position_x=position_x,
                position_y=position_y,
                bbox_x0=bbox_x0,
                bbox_y0=bbox_y0,
                bbox_x1=bbox_x1,
                bbox_y1=bbox_y1,
                features=features,
            )
        )

    return results


def _extract_all(
    image: np.ndarray,
    seg_labeled: np.ndarray,
    times: np.ndarray,
    background: np.ndarray,
    progress_callback: Callable | None = None,
    feature_names: list[str] | None = None,
    cancel_event=None,
    background_weight: float = 0.0,
    erosion_size: int = 0,
) -> pd.DataFrame:
    """Build trace DataFrame from fluorescence and label stacks.

    Creates a flat DataFrame where each row corresponds to a
    (cell, time) observation, with columns derived from the
    ResultWithFeatures dataclass plus feature columns.

    Parameters:
    - image: 3D (T, H, W) fluorescence stack
    - seg_labeled: 3D (T, H, W) labeled stack with tracked cell IDs
    - times: 1D (T) time array in seconds
    - background: 3D (T, H, W) background stack for correction (always provided)
    - progress_callback: Optional callback for progress updates
    - feature_names: Optional list of feature names to extract
    - cancel_event: Optional threading.Event for cancellation support
    - background_weight: Weight for background subtraction (default: 0.0)
    - erosion_size: Number of pixels to erode the mask (default: 0, no erosion)

    Returns:
    - DataFrame with columns [cell, frame, time, exist, good, position_x,
      position_y, <feature columns>]
    """
    # Build rows directly from the dataclass without a MultiIndex.
    # Strategy: determine index fields first, then base fields, then features.
    # This ensures the resulting DataFrame columns are ordered as the user requested.
    base_fields = [f.name for f in dataclass_fields(Result)]
    if feature_names is None:
        feature_names = list_features()  # Use all features if not specified

    T, H, W = image.shape
    # Precompute column names in the requested ordering: index, base, features
    col_names = base_fields + feature_names
    cols: dict[str, list[Any]] = {name: [] for name in col_names}

    for t in range(T):
        # Check for cancellation before processing each frame
        if cancel_event and cancel_event.is_set():
            import logging

            logger = logging.getLogger(__name__)
            logger.info("Feature extraction cancelled at frame %d", t)
            return pd.DataFrame(columns=col_names)
        # Background is always an array
        bg_frame = background[t]
        frame_result = _extract_single_frame(
            image[t], seg_labeled[t], t, float(times[t]), bg_frame, feature_names, background_weight, erosion_size
        )
        if progress_callback is not None:
            progress_callback(t, T, "Extracting features")

        # Extend in the requested order to minimize peak memory
        for name in base_fields:
            cols[name].extend([getattr(res, name) for res in frame_result])
        for fname in feature_names:
            cols[fname].extend(
                [res.features.get(fname, np.nan) for res in frame_result]
            )

    df = pd.DataFrame(cols, columns=col_names)
    return df


def _filter_by_length(df: pd.DataFrame, min_length: int = 30) -> pd.DataFrame:
    """Filter traces by minimum number of existing frames.

    Parameters:
    - df: Trace DataFrame with cell column
    - min_length: Minimum number of frames a cell must exist

    Returns:
    - Filtered DataFrame containing only cells with sufficient length
    """
    # Use groupby to count frames per cell, then filter
    cell_counts = df.groupby("cell").size()
    valid_cells = cell_counts.index[cell_counts >= min_length]
    return df[df["cell"].isin(valid_cells)]


def _filter_by_border(
    df: pd.DataFrame, width: int, height: int, border_width: int = 50
) -> pd.DataFrame:
    """Filter out cells that are too close to the border.

    A cell is removed if any part of its mask is within ``border_width`` pixels of the
    image border in any frame. This uses the bounding box of the mask rather than
    just the centroid position.
    """
    # Get all cells that are ever too close to the border
    # Check if the bounding box extends within border_width of any edge
    border_cells = df[
        (df["bbox_x0"] < border_width)  # Left edge too close
        | (df["bbox_x1"] > width - border_width)  # Right edge too close
        | (df["bbox_y0"] < border_width)  # Top edge too close
        | (df["bbox_y1"] > height - border_width)  # Bottom edge too close
    ]["cell"].unique()

    # Return a dataframe where these cells are removed
    return df[~df["cell"].isin(border_cells)]


def extract_trace(
    image: np.ndarray,
    seg_labeled: np.ndarray,
    times: np.ndarray,
    background: np.ndarray,
    progress_callback: Callable | None = None,
    features: list[str] | None = None,
    cancel_event=None,
    background_weight: float = 0.0,
    erosion_size: int = 0,
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
    - background: 3D (T, H, W) background stack for correction (always required)
    - progress_callback: Optional function(frame, total, message) for progress
    - features: Optional list of feature names to extract
    - cancel_event: Optional threading.Event for cancellation support
    - background_weight: Weight for background subtraction (default: 0.0)
    - erosion_size: Number of pixels to erode the segmentation mask before
      feature extraction (default: 0, no erosion). This helps exclude edge
      pixels that may not belong to the cell when computing intensity sums.

    Returns:
    - Filtered flat DataFrame containing frame, position coordinates and
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

    if background.ndim != 3:
        raise ValueError("background must be 3D array")
    
    if background.shape != image.shape:
        raise ValueError("background must have the same shape as image")

    image = image.astype(np.float32, copy=False)
    background = background.astype(np.float32, copy=False)
    seg_labeled = seg_labeled.astype(np.uint16, copy=False)
    times = times.astype(float, copy=False)

    T, H, W = image.shape

    # Perform tracking then build raw traces
    df = _extract_all(
        image, seg_labeled, times, background, progress_callback, features, cancel_event, background_weight, erosion_size
    )

    # Apply filtering and cleanup
    df = _filter_by_length(df)
    df = _filter_by_border(df, W, H)

    return df
