"""
Cell tracking algorithms for microscopy image analysis.

This module provides cell tracking functionality that assigns consistent
cell IDs across multiple frames using binary segmentation masks.
"""

import numpy as np


def track_cells_simple(binary_stack: np.ndarray) -> np.ndarray:
    """Simple cell tracking by assigning consistent IDs across frames.
    
    This is a minimal tracking implementation that assigns cell IDs based on
    spatial overlap between consecutive frames. For production use, consider
    more sophisticated tracking algorithms.
    
    Args:
        binary_stack: Binary segmentation stack (frames x height x width)
        
    Returns:
        Labeled stack with consistent cell IDs across frames (frames x height x width)
    """
    from scipy import ndimage
    
    n_frames, height, width = binary_stack.shape
    labeled_stack = np.zeros((n_frames, height, width), dtype=np.int32)
    
    next_cell_id = 1
    
    for frame_idx in range(n_frames):
        # Label connected components in current frame
        frame_labels, n_objects = ndimage.label(binary_stack[frame_idx])
        
        if frame_idx == 0:
            # First frame: assign new IDs
            labeled_stack[0] = frame_labels
            # Update next available ID
            if n_objects > 0:
                next_cell_id = n_objects + 1
        else:
            # Track cells from previous frame
            prev_labels = labeled_stack[frame_idx - 1]
            current_labels = np.zeros_like(frame_labels)
            
            for obj_id in range(1, n_objects + 1):
                obj_mask = frame_labels == obj_id
                
                # Find overlapping cells in previous frame
                overlapping_ids = prev_labels[obj_mask]
                overlapping_ids = overlapping_ids[overlapping_ids > 0]
                
                if len(overlapping_ids) > 0:
                    # Use the most common overlapping ID
                    best_match = np.bincount(overlapping_ids).argmax()
                    current_labels[obj_mask] = best_match
                else:
                    # New cell: assign new ID
                    current_labels[obj_mask] = next_cell_id
                    next_cell_id += 1
            
            labeled_stack[frame_idx] = current_labels
    
    return labeled_stack