"""
Binarization algorithms for microscopy image analysis.

This module contains various binarization techniques optimized for different
microscopy modalities and image characteristics.
"""

import os
import logging

# Suppress numba debug messages
os.environ['NUMBA_LOGGER_LEVEL'] = 'WARNING'
logging.getLogger('numba.core.ssa').setLevel(logging.WARNING)
logging.getLogger('numba.core.byteflow').setLevel(logging.WARNING)
logging.getLogger('numba.core.interpreter').setLevel(logging.WARNING)

from enum import Enum
import numpy as np
import numba as nb
from scipy import ndimage
from scipy.ndimage import binary_fill_holes
from skimage.filters import threshold_otsu, threshold_local, sobel
# Note: Using scipy.ndimage exclusively for morphological operations to match original PyAMA behavior


class BinarizationMethod(Enum):
    """Available binarization methods (for testing and comparison only)."""
    LOGARITHMIC_STD = "log_std"
    OTSU = "otsu"
    ADAPTIVE_THRESHOLD = "adaptive"
    EDGE_BASED = "edge"
    LOCAL_THRESHOLD = "local"


def logarithmic_std_binarization(stack: np.ndarray, mask_size: int = 3, 
                                progress_callback: callable = None) -> np.ndarray:
    """
    Binarize phase contrast stack using logarithmic standard deviation method.
    
    This method uses local variance to detect texture changes typical of cell boundaries
    in phase contrast microscopy. Based on the original PyAMA implementation.
    
    Args:
        stack: Input phase contrast stack (frames x height x width) or single frame (height x width)
        mask_size: Size of local window for variance calculation
        progress_callback: Optional callback function(frame_idx, n_frames, message) for progress updates
        
    Returns:
        np.ndarray: Binarized stack/frame (boolean array)
    """
    # Handle both 2D and 3D inputs
    if stack.ndim == 2:
        return _binarize_frame(stack, mask_size)
    elif stack.ndim == 3:
        n_frames, height, width = stack.shape
        binarized_stack = np.empty((n_frames, height, width), dtype=np.bool_)
        
        for frame_idx in range(n_frames):
            # Process frame
            binarized_stack[frame_idx] = _binarize_frame(stack[frame_idx], mask_size)
            
            # Progress callback
            if progress_callback and frame_idx % 10 == 0:
                progress_callback(frame_idx, n_frames, "Binarizing")
                
        return binarized_stack
    else:
        raise ValueError(f"Expected 2D or 3D array, got {stack.ndim}D")


def _binarize_frame(frame: np.ndarray, mask_size: int = 3) -> np.ndarray:
    """
    Binarize a single frame using logarithmic standard deviation method.
    
    Args:
        frame: Input phase contrast frame (height x width)
        mask_size: Size of local window for variance calculation
        
    Returns:
        np.ndarray: Binarized frame (boolean array)
    """
    # Convert to float64 for numerical stability
    img = frame.astype(np.float64)
    
    # Calculate local variance using generic filter
    std_log = ndimage.generic_filter(img, _window_std, size=mask_size)
    
    # Apply logarithmic transformation with normalization
    # Only apply to positive variance values
    valid_mask = std_log > 0
    std_log[valid_mask] = (np.log(std_log[valid_mask]) - np.log(mask_size**2 - 1)) / 2
    std_log[~valid_mask] = 0  # Set invalid values to 0
    
    # Histogram-based adaptive thresholding
    # Find histogram mode (peak) and calculate threshold as mode + 3*sigma
    counts, edges = np.histogram(std_log[valid_mask], bins=200)
    bins = (edges[:-1] + edges[1:]) / 2
    hist_max = bins[np.argmax(counts)]  # Mode of histogram
    
    # Calculate standard deviation of values below the mode
    below_mode = std_log[(std_log <= hist_max) & valid_mask]
    if len(below_mode) > 0:
        sigma = np.std(below_mode)
        threshold = hist_max + 3 * sigma
    else:
        # Fallback if no values below mode
        threshold = np.percentile(std_log[valid_mask], 75) if np.any(valid_mask) else 0
    
    # Apply threshold
    img_bin = std_log >= threshold
    
    # Morphological post-processing (following original PyAMA approach)
    # 1. Dilation with 3x3 structure
    struct3 = np.ones((3, 3), dtype=bool)
    img_bin = ndimage.binary_dilation(img_bin, structure=struct3)
    
    # 2. Fill holes
    img_bin = binary_fill_holes(img_bin)
    
    # 3. Opening with 5x5 structure (2 iterations) - using scipy.ndimage to match original
    struct5 = np.ones((5, 5), dtype=bool)
    struct5[[0, 0, -1, -1], [0, -1, 0, -1]] = False  # Remove corners like original
    img_bin &= ndimage.binary_opening(img_bin, iterations=2, structure=struct5)
    
    # 4. Final erosion - using scipy.ndimage to match original
    img_bin = ndimage.binary_erosion(img_bin, border_value=1)
    
    return img_bin.astype(np.bool_)


def otsu_binarization(frame: np.ndarray, mask_size: int = 3, **kwargs) -> np.ndarray:
    """
    Binarize using Otsu's method with optional morphological post-processing.
    
    NOTE: This method is available for testing and comparison only.
    Production code uses logarithmic_std_binarization exclusively.
    
    Args:
        frame: Input image frame
        mask_size: Size of morphological mask for post-processing
        **kwargs: Additional parameters (gaussian_sigma)
        
    Returns:
        np.ndarray: Binarized frame (boolean array)
    """
    gaussian_sigma = kwargs.get('gaussian_sigma', 1.0)
    
    # Convert to float for processing
    frame_float = frame.astype(np.float64)
    
    # Apply Gaussian filter to reduce noise
    frame_smooth = ndimage.gaussian_filter(frame_float, sigma=gaussian_sigma)
    
    # Otsu thresholding
    threshold = threshold_otsu(frame_smooth)
    binary = frame_smooth > threshold
    
    # Morphological opening to remove small objects and smooth boundaries
    if mask_size > 0:
        struct = np.ones((mask_size, mask_size), dtype=bool)
        binary = ndimage.binary_opening(binary, structure=struct)
    
    return binary.astype(np.bool_)


def adaptive_threshold_binarization(frame: np.ndarray, mask_size: int = 15, **kwargs) -> np.ndarray:
    """
    Binarize using adaptive thresholding for images with varying illumination.
    
    NOTE: This method is available for testing and comparison only.
    Production code uses logarithmic_std_binarization exclusively.
    
    Args:
        frame: Input image frame
        mask_size: Size of local neighborhood (should be odd)
        **kwargs: Additional parameters (method, offset)
        
    Returns:
        np.ndarray: Binarized frame (boolean array)
    """
    method = kwargs.get('method', 'gaussian')  # 'gaussian' or 'mean'
    offset = kwargs.get('offset', 0)
    
    # Ensure mask_size is odd
    if mask_size % 2 == 0:
        mask_size += 1
    
    # Convert to float for processing
    frame_float = frame.astype(np.float64)
    
    # Apply adaptive threshold
    threshold_map = threshold_local(frame_float, block_size=mask_size, method=method, offset=offset)
    binary = frame_float > threshold_map
    
    return binary.astype(np.bool_)


def edge_based_binarization(frame: np.ndarray, mask_size: int = 3, **kwargs) -> np.ndarray:
    """
    Binarize based on edge detection, useful for phase contrast where edges are prominent.
    
    NOTE: This method is available for testing and comparison only.
    Production code uses logarithmic_std_binarization exclusively.
    
    Args:
        frame: Input image frame  
        mask_size: Size of morphological mask for post-processing
        **kwargs: Additional parameters (edge_threshold_percentile, gaussian_sigma)
        
    Returns:
        np.ndarray: Binarized frame (boolean array)
    """
    edge_threshold_percentile = kwargs.get('edge_threshold_percentile', 70)
    gaussian_sigma = kwargs.get('gaussian_sigma', 1.0)
    
    # Convert to float for processing
    frame_float = frame.astype(np.float64)
    
    # Apply Gaussian filter to reduce noise
    frame_smooth = ndimage.gaussian_filter(frame_float, sigma=gaussian_sigma)
    
    # Compute edge magnitude using Sobel
    edges = sobel(frame_smooth)
    
    # Threshold edges
    threshold = np.percentile(edges, edge_threshold_percentile)
    binary = edges > threshold
    
    # Morphological post-processing
    if mask_size > 0:
        struct = np.ones((mask_size, mask_size), dtype=bool)
        # Fill holes and smooth
        binary = binary_fill_holes(binary)
        binary = ndimage.binary_opening(binary, structure=struct)
    
    return binary.astype(np.bool_)


def local_threshold_binarization(frame: np.ndarray, mask_size: int = 15, **kwargs) -> np.ndarray:
    """
    Binarize using local statistics (mean + k*std) in sliding windows.
    
    NOTE: This method is available for testing and comparison only.
    Production code uses logarithmic_std_binarization exclusively.
    
    Args:
        frame: Input image frame
        mask_size: Size of local window for statistics
        **kwargs: Additional parameters (k_factor)
        
    Returns:
        np.ndarray: Binarized frame (boolean array)
    """
    k_factor = kwargs.get('k_factor', 0.5)
    
    # Convert to float for processing
    frame_float = frame.astype(np.float64)
    
    # Calculate local mean and std
    local_mean = ndimage.uniform_filter(frame_float, size=mask_size)
    local_var = ndimage.uniform_filter(frame_float**2, size=mask_size) - local_mean**2
    local_std = np.sqrt(np.maximum(local_var, 0))  # Ensure non-negative
    
    # Threshold: local_mean + k * local_std
    threshold_map = local_mean + k_factor * local_std
    binary = frame_float > threshold_map
    
    return binary.astype(np.bool_)


def get_binarization_function(method: BinarizationMethod):
    """
    Get the binarization function for the specified method.
    
    NOTE: This function is available for testing and comparison only.
    Production code imports logarithmic_std_binarization directly.
    
    Args:
        method: Binarization method enum
        
    Returns:
        callable: Binarization function
    """
    method_map = {
        BinarizationMethod.LOGARITHMIC_STD: logarithmic_std_binarization,
        BinarizationMethod.OTSU: otsu_binarization,
        BinarizationMethod.ADAPTIVE_THRESHOLD: adaptive_threshold_binarization,
        BinarizationMethod.EDGE_BASED: edge_based_binarization,
        BinarizationMethod.LOCAL_THRESHOLD: local_threshold_binarization,
    }
    
    return method_map.get(method, logarithmic_std_binarization)


def compare_binarization_methods(frame: np.ndarray, mask_size: int = 3, 
                               methods: list | None = None, **kwargs) -> dict:
    """
    Compare multiple binarization methods on the same frame.
    
    NOTE: This function is available for testing and comparison only.
    Production code uses logarithmic_std_binarization exclusively.
    
    Args:
        frame: Input image frame
        mask_size: Size parameter for morphological operations
        methods: List of BinarizationMethod enums to test (None = all methods)
        **kwargs: Additional parameters passed to binarization functions
        
    Returns:
        dict: Dictionary mapping method names to binary results
    """
    if methods is None:
        methods = list(BinarizationMethod)
    
    results = {}
    
    for method in methods:
        try:
            binarization_func = get_binarization_function(method)
            binary_result = binarization_func(frame, mask_size, **kwargs)
            results[method.value] = binary_result
        except Exception as e:
            print(f"Error with method {method.value}: {str(e)}")
            # Create empty result for failed methods
            results[method.value] = np.zeros_like(frame, dtype=np.bool_)
    
    return results














@nb.njit
def _window_std(img_window):
    """
    Calculate unnormalized variance of image window.
    
    This is optimized with numba for speed. Returns variance (not std dev)
    to avoid expensive square root operation.
    
    Args:
        img_window: Flattened window of pixels
        
    Returns:
        float: Unnormalized variance
    """
    mean_val = np.mean(img_window)
    return np.sum((img_window - mean_val) ** 2)