"""
Trace calculation algorithms for microscopy image analysis.

This module combines cell tracking and property extraction to generate
time-series traces from fluorescence microscopy data.
"""

import numpy as np
from .tracking import track_cells_simple
from .extraction import extract_cell_properties


def extract_traces_with_tracking(fluor_stack: np.ndarray, binary_stack: np.ndarray) -> dict[int, dict[str, list[float]]]:
    """Extract traces by first tracking cells, then extracting properties.
    
    Args:
        fluor_stack: Fluorescence image stack (frames x height x width)
        binary_stack: Binary segmentation stack (frames x height x width)
        
    Returns:
        Dictionary mapping cell IDs to their time-series traces:
        {cell_id: {'intensity_mean': [values], 'intensity_total': [values], 
                   'area': [values], 'centroid_x': [values], 'centroid_y': [values]}}
    """
    # Step 1: Track cells to get consistent labels
    label_stack = track_cells_simple(binary_stack)
    
    # Step 2: Extract traces using tracked labels
    return extract_traces_from_tracking(fluor_stack, label_stack)


def extract_traces_from_tracking(fluor_stack: np.ndarray, label_stack: np.ndarray) -> dict[int, dict[str, list[float]]]:
    """Extract traces from fluorescence stack using pre-tracked labels.
    
    Args:
        fluor_stack: Fluorescence image stack (frames x height x width)
        label_stack: Pre-tracked labeled segmentation stack with consistent cell IDs
        
    Returns:
        Dictionary mapping cell IDs to their time-series traces:
        {cell_id: {'intensity_mean': [values], 'intensity_total': [values], 
                   'area': [values], 'centroid_x': [values], 'centroid_y': [values]}}
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
            'intensity_mean': [],
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
        
        # Add data to traces (or NaN if cell not present in this frame)
        for cell_id in all_cell_ids:
            if cell_id in frame_properties:
                props = frame_properties[cell_id]
                traces[int(cell_id)]['intensity_mean'].append(props['intensity_mean'])
                traces[int(cell_id)]['intensity_total'].append(props['intensity_total'])
                traces[int(cell_id)]['area'].append(props['area'])
                traces[int(cell_id)]['centroid_x'].append(props['centroid_x'])
                traces[int(cell_id)]['centroid_y'].append(props['centroid_y'])
            else:
                # Cell not present in this frame
                traces[int(cell_id)]['intensity_mean'].append(np.nan)
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
        # Count non-NaN values in intensity_mean trace
        valid_points = sum(1 for x in cell_traces['intensity_mean'] if not np.isnan(x))
        
        if valid_points >= min_length:
            filtered_traces[cell_id] = cell_traces
    
    return filtered_traces