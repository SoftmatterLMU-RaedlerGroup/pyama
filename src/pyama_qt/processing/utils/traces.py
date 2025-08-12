"""
Trace calculation algorithms for microscopy image analysis.

This module combines cell tracking and property extraction to generate
time-series traces from fluorescence microscopy data.
"""

from typing import Callable, Dict, Any

import numpy as np
import pandas as pd
from .tracking import track_cells
from pyama_qt.core.cell_feature import FEATURE_EXTRACTORS, ExtractionContext


def extract_position(ctx: ExtractionContext) -> tuple[float, float]:
    """
    Extract position coordinates for a single cell.
    
    Args:
        ctx: Extraction context containing cell_mask
        
    Returns:
        Tuple of (position_x, position_y)
    """
    y_coords, x_coords = np.where(ctx.cell_mask)
    if len(x_coords) == 0:
        return (np.nan, np.nan)
    position_x = float(np.mean(x_coords))
    position_y = float(np.mean(y_coords))
    return (position_x, position_y)


def extract_cell_features(fluor_frame: np.ndarray, label_frame: np.ndarray) -> Dict[int, Dict[str, Any]]:
    """
    Extract all defined features from each labeled cell in a frame.
    
    Args:
        fluor_frame: Fluorescence image (height x width)
        label_frame: Labeled segmentation mask with unique integer IDs per cell
        
    Returns:
        Dictionary mapping cell IDs to all their extracted features:
        {cell_id: {'intensity_total': float, 'area': int, 'position': (x, y)}}
    """
    if fluor_frame.shape != label_frame.shape:
        raise ValueError("Fluorescence and label frames must have the same shape")
    
    # Get unique cell IDs (excluding background=0)
    cell_ids = np.unique(label_frame)
    cell_ids = cell_ids[cell_ids > 0]  # Remove background
    
    results = {}
    
    for cell_id in cell_ids:
        # Create mask for this cell
        cell_mask = label_frame == cell_id
        
        # Create extraction context with all available information
        ctx = ExtractionContext(
            fluor_frame=fluor_frame,
            cell_mask=cell_mask
        )
        
        # Extract all features using the mapping
        cell_features = {}
        for feature_name, extractor_func in FEATURE_EXTRACTORS.items():
            cell_features[feature_name] = extractor_func(ctx)
        
        # Also extract position (not in FEATURE_EXTRACTORS since it's local to traces)
        cell_features['position'] = extract_position(ctx)
        
        results[int(cell_id)] = cell_features
    
    return results


def extract_traces_with_tracking(fluor_stack: np.ndarray, binary_stack: np.ndarray,
                               progress_callback: Callable | None = None) -> pd.DataFrame:
    """Extract traces by first tracking cells, then extracting properties.
    
    This matches the original PyAMA implementation which only extracts total intensity.
    
    Args:
        fluor_stack: Fluorescence image stack (frames x height x width)
        binary_stack: Binary segmentation stack (frames x height x width)
        progress_callback: Optional callback function(frame_idx, n_frames, message) for progress updates
        
    Returns:
        DataFrame with MultiIndex (cell_id, frame) and columns:
        - exist: bool, whether cell exists in frame
        - good: bool, whether cell is not anomalous
        - position_x, position_y: float, cell position
        - feature columns from FEATURE_EXTRACTORS
    """
    # Step 1: Track cells to get consistent labels
    label_stack = track_cells(binary_stack, progress_callback=progress_callback)
    
    # Step 2: Extract traces using tracked labels
    return extract_traces_from_tracking(fluor_stack, label_stack, progress_callback)


def extract_traces_from_tracking(fluor_stack: np.ndarray, label_stack: np.ndarray,
                               progress_callback: Callable | None = None) -> pd.DataFrame:
    """Extract traces from fluorescence stack using pre-tracked labels.
    
    Args:
        fluor_stack: Fluorescence image stack (frames x height x width)
        label_stack: Pre-tracked labeled segmentation stack with consistent cell IDs
        progress_callback: Optional callback function(frame_idx, n_frames, message) for progress updates
        
    Returns:
        DataFrame with MultiIndex (cell_id, frame) and columns:
        - exist: bool, whether cell exists in frame
        - good: bool, whether cell is not anomalous
        - position_x, position_y: float, cell position
        - feature columns from FEATURE_EXTRACTORS
    """
    if fluor_stack.shape != label_stack.shape:
        raise ValueError("Fluorescence and label stacks must have the same shape")
    
    n_frames = fluor_stack.shape[0]
    
    # Collect all cell IDs across all frames
    all_cell_ids = set()
    for frame_idx in range(n_frames):
        frame_ids = np.unique(label_stack[frame_idx])
        all_cell_ids.update(frame_ids[frame_ids > 0])
    all_cell_ids = sorted(all_cell_ids)  # Sort for consistent ordering
    
    # Get feature names from FEATURE_EXTRACTORS
    feature_names = list(FEATURE_EXTRACTORS.keys())
    
    # Pre-allocate DataFrame with known dimensions
    # Create multi-index for (cell_id, frame)
    index = pd.MultiIndex.from_product([all_cell_ids, range(n_frames)], 
                                       names=['cell_id', 'frame'])
    
    # Initialize columns
    columns = ['exist', 'good', 'position_x', 'position_y'] + feature_names
    df = pd.DataFrame(index=index, columns=columns)
    
    # Set default values
    df['exist'] = False
    df['good'] = True  # Default to good, can be updated based on quality checks
    df['position_x'] = np.nan
    df['position_y'] = np.nan
    for feature in feature_names:
        df[feature] = np.nan
    
    # Extract properties frame by frame and fill DataFrame
    for frame_idx in range(n_frames):
        frame_properties = extract_cell_features(
            fluor_stack[frame_idx], 
            label_stack[frame_idx]
        )
        
        # Progress callback
        if progress_callback and frame_idx % 30 == 0:
            progress_callback(frame_idx, n_frames, "Extracting features")
        
        # Fill data for cells present in this frame
        for cell_id, props in frame_properties.items():
            df.loc[(cell_id, frame_idx), 'exist'] = True
            df.loc[(cell_id, frame_idx), 'position_x'] = props['position'][0]
            df.loc[(cell_id, frame_idx), 'position_y'] = props['position'][1]
            for feature in feature_names:
                df.loc[(cell_id, frame_idx), feature] = props[feature]
    
    return df


def filter_traces_by_length(traces_df: pd.DataFrame, min_length: int = 3) -> pd.DataFrame:
    """Filter traces to keep only cells with sufficient data points.
    
    Args:
        traces_df: DataFrame with MultiIndex (cell_id, frame) containing traces
        min_length: Minimum number of frames where cell exists
        
    Returns:
        DataFrame with only cells meeting the minimum length requirement
    """
    # Count valid points per cell using the exist column
    valid_counts = traces_df.groupby(level='cell_id')['exist'].sum()
    
    # Get cell IDs that meet the minimum length requirement
    valid_cells = valid_counts[valid_counts >= min_length].index
    
    # Filter the DataFrame to keep only valid cells
    return traces_df.loc[valid_cells]


def filter_traces_by_vitality(traces_df: pd.DataFrame) -> pd.DataFrame:
    """Filter traces to remove anomalous/dead cells based on vitality.
    
    Args:
        traces_df: DataFrame with MultiIndex (cell_id, frame) containing traces
        
    Returns:
        DataFrame with anomalous cells filtered out
    """
    # TODO: Implement vitality-based filtering
    # For now, returns the DataFrame unchanged
    return traces_df


def filter_traces(traces_df: pd.DataFrame, min_length: int = 3) -> pd.DataFrame:
    """Master filter function that applies all filters and cleans up the DataFrame.
    
    Args:
        traces_df: DataFrame with MultiIndex (cell_id, frame) containing traces
        min_length: Minimum number of frames where cell must exist
        
    Returns:
        Filtered and cleaned DataFrame with non-existent frames removed and 
        'exist' column dropped
    """
    # Apply length filter
    filtered_df = filter_traces_by_length(traces_df, min_length)
    
    # Apply vitality filter
    filtered_df = filter_traces_by_vitality(filtered_df)
    
    # Clean up: remove rows where cell doesn't exist and drop the exist column
    filtered_df = filtered_df[filtered_df['exist']].drop(columns=['exist'])
    
    return filtered_df