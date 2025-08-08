"""
Trace calculation algorithms for microscopy image analysis.

This module combines cell tracking and property extraction to generate
time-series traces from fluorescence microscopy data.
"""

from typing import Callable

import numpy as np
from .tracking import track_cells
from .extraction import extract_cell_properties


def extract_traces_with_tracking(fluor_stack: np.ndarray, binary_stack: np.ndarray,
                               progress_callback: Callable | None = None) -> dict[int, dict[str, list[float]]]:
    """Extract traces by first tracking cells, then extracting properties.
    
    This matches the original PyAMA implementation which only extracts total intensity.
    
    Args:
        fluor_stack: Fluorescence image stack (frames x height x width)
        binary_stack: Binary segmentation stack (frames x height x width)
        progress_callback: Optional callback function(frame_idx, n_frames, message) for progress updates
        
    Returns:
        Dictionary mapping cell IDs to their time-series traces:
        {cell_id: {'intensity_total': [values], 'area': [values], 
                   'centroid_x': [values], 'centroid_y': [values]}}
    """
    # Step 1: Track cells to get consistent labels
    label_stack = track_cells(binary_stack, progress_callback=progress_callback)
    
    # Step 2: Extract traces using tracked labels
    return extract_traces_from_tracking(fluor_stack, label_stack, progress_callback)


def extract_traces_from_tracking(fluor_stack: np.ndarray, label_stack: np.ndarray,
                               progress_callback: Callable | None = None) -> dict[int, dict[str, list[float]]]:
    """Extract traces from fluorescence stack using pre-tracked labels.
    
    Args:
        fluor_stack: Fluorescence image stack (frames x height x width)
        label_stack: Pre-tracked labeled segmentation stack with consistent cell IDs
        progress_callback: Optional callback function(frame_idx, n_frames, message) for progress updates
        
    Returns:
        Dictionary mapping cell IDs to their time-series traces:
        {cell_id: {'intensity_total': [values], 'area': [values], 
                   'centroid_x': [values], 'centroid_y': [values]}}
    """
    if fluor_stack.shape != label_stack.shape:
        raise ValueError("Fluorescence and label stacks must have the same shape")
    
    n_frames = fluor_stack.shape[0]
    traces = {}
    
    # Collect all cell IDs across all frames
    all_cell_ids = set()
    for frame_idx in range(n_frames):
        frame_ids = np.unique(label_stack[frame_idx])
        all_cell_ids.update(frame_ids[frame_ids > 0])
    
    # Initialize traces for all cells
    for cell_id in all_cell_ids:
        traces[int(cell_id)] = {
            'intensity_total': [],
            'area': [],
            'centroid_x': [],
            'centroid_y': []
        }
    
    # Extract properties frame by frame
    for frame_idx in range(n_frames):
        frame_properties = extract_cell_properties(
            fluor_stack[frame_idx], 
            label_stack[frame_idx]
        )
        
        # Progress callback
        if progress_callback and frame_idx % 30 == 0:
            progress_callback(frame_idx, n_frames, "Extracting features")
        
        # Add data to traces (or NaN if cell not present in this frame)
        for cell_id in all_cell_ids:
            if cell_id in frame_properties:
                props = frame_properties[cell_id]
                traces[int(cell_id)]['intensity_total'].append(props['intensity_total'])
                traces[int(cell_id)]['area'].append(props['area'])
                traces[int(cell_id)]['centroid_x'].append(props['centroid_x'])
                traces[int(cell_id)]['centroid_y'].append(props['centroid_y'])
            else:
                # Cell not present in this frame
                traces[int(cell_id)]['intensity_total'].append(np.nan)
                traces[int(cell_id)]['area'].append(np.nan)
                traces[int(cell_id)]['centroid_x'].append(np.nan)
                traces[int(cell_id)]['centroid_y'].append(np.nan)
    
    return traces


def filter_traces_by_length(traces: dict[int, dict[str, list[float]]], min_length: int = 3) -> dict[int, dict[str, list[float]]]:
    """Filter traces to keep only cells with sufficient data points.
    
    Args:
        traces: Input traces dictionary
        min_length: Minimum number of non-NaN data points required
        
    Returns:
        Filtered traces dictionary
    """
    filtered_traces = {}
    
    for cell_id, cell_traces in traces.items():
        # Count non-NaN values in intensity_total trace
        valid_points = sum(1 for x in cell_traces['intensity_total'] if not np.isnan(x))
        
        if valid_points >= min_length:
            filtered_traces[cell_id] = cell_traces
    
    return filtered_traces