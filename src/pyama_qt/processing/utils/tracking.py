"""
Cell tracking algorithms for microscopy image analysis.

This module provides cell tracking functionality that assigns consistent
cell IDs across multiple frames using binary segmentation masks.
"""

import numpy as np

# Size filtering constants from original PyAMA
IGNORE_SIZE = 300
MIN_SIZE = 1000
MAX_SIZE = 10000


def track_cells_simple(binary_stack: np.ndarray, 
                      ignore_size: int = IGNORE_SIZE,
                      min_size: int = MIN_SIZE, 
                      max_size: int = MAX_SIZE,
                      progress_callback: callable = None) -> np.ndarray:
    """Simple cell tracking by assigning consistent IDs across frames with size filtering.
    
    This implementation assigns cell IDs based on spatial overlap between 
    consecutive frames and filters cells by size according to PyAMA conventions.
    
    Args:
        binary_stack: Binary segmentation stack (frames x height x width)
        ignore_size: Maximum size for cells to be ignored (default: 300 pixels)
        min_size: Minimum valid cell size (default: 1000 pixels)
        max_size: Maximum valid cell size (default: 10000 pixels)
        progress_callback: Optional callback function(frame_idx, n_frames, message) for progress updates
        
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
        
        # Progress callback
        if progress_callback and frame_idx % 10 == 0:
            progress_callback(frame_idx, n_frames, "Tracking cells")
        
        if frame_idx == 0:
            # First frame: assign new IDs with size filtering
            current_labels = np.zeros_like(frame_labels)
            
            for obj_id in range(1, n_objects + 1):
                obj_mask = frame_labels == obj_id
                area = np.sum(obj_mask)
                
                # Apply size filters matching original PyAMA
                if area <= ignore_size:
                    # Too small - ignore completely
                    continue
                elif area < min_size:
                    # Below minimum size - skip
                    continue
                elif max_size and area > max_size:
                    # Above maximum size - skip
                    continue
                else:
                    # Valid cell - assign ID
                    current_labels[obj_mask] = next_cell_id
                    next_cell_id += 1
            
            labeled_stack[0] = current_labels
        else:
            # Track cells from previous frame
            prev_labels = labeled_stack[frame_idx - 1]
            current_labels = np.zeros_like(frame_labels)
            
            for obj_id in range(1, n_objects + 1):
                obj_mask = frame_labels == obj_id
                area = np.sum(obj_mask)
                
                # Apply size filters
                if area <= ignore_size:
                    continue
                elif area < min_size:
                    continue
                elif max_size and area > max_size:
                    continue
                
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