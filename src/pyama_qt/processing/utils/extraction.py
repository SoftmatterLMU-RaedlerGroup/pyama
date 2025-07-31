"""
Property extraction algorithms for microscopy image analysis.

This module extracts fluorescence intensity and morphological properties
from labeled cell regions in fluorescence images.
"""

import numpy as np


def extract_cell_properties(fluor_frame: np.ndarray, label_frame: np.ndarray) -> dict[int, dict[str, float]]:
    """Extract properties from each labeled cell in a single frame.
    
    This matches the original PyAMA implementation which calculates:
    - Total fluorescence intensity (sum)
    - Cell area in pixels
    - Centroid coordinates
    
    Args:
        fluor_frame: Fluorescence image (height x width)
        label_frame: Labeled segmentation mask with unique integer IDs per cell
        
    Returns:
        Dictionary mapping cell IDs to their properties:
        {cell_id: {'intensity_total': float, 'area': int, 
                   'centroid_x': float, 'centroid_y': float}}
    """
    if fluor_frame.shape != label_frame.shape:
        raise ValueError("Fluorescence and label frames must have the same shape")
    
    # Get unique cell IDs (excluding background=0)
    cell_ids = np.unique(label_frame)
    cell_ids = cell_ids[cell_ids > 0]  # Remove background
    
    properties = {}
    
    for cell_id in cell_ids:
        # Create mask for this cell
        cell_mask = label_frame == cell_id
        
        # Extract fluorescence values for this cell
        cell_pixels = fluor_frame[cell_mask]
        
        # Calculate properties matching original PyAMA
        # Total intensity is the sum of all pixel values (line 491 in old code)
        intensity_total = float(np.sum(cell_pixels))
        area = int(np.sum(cell_mask))
        
        # Calculate centroid
        y_coords, x_coords = np.where(cell_mask)
        centroid_x = float(np.mean(x_coords))
        centroid_y = float(np.mean(y_coords))
        
        properties[int(cell_id)] = {
            'intensity_total': intensity_total,
            'area': area,
            'centroid_x': centroid_x,
            'centroid_y': centroid_y
        }
    
    return properties