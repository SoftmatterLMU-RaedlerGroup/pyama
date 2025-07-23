"""
Binarization algorithms for microscopy image analysis.

This module contains various binarization techniques optimized for different
microscopy modalities and image characteristics.
"""

from enum import Enum
from typing import Optional, Dict, Any
import numpy as np
import numba as nb
from scipy import ndimage
from scipy.ndimage import binary_fill_holes
from skimage.filters import threshold_otsu, threshold_local, sobel
from skimage.morphology import binary_opening, binary_dilation, binary_erosion


class BinarizationMethod(Enum):
    """Available binarization methods."""
    LOGARITHMIC_STD = "log_std"
    OTSU = "otsu"
    ADAPTIVE_THRESHOLD = "adaptive"
    EDGE_BASED = "edge"
    LOCAL_THRESHOLD = "local"


def logarithmic_std_binarization(frame: np.ndarray, mask_size: int = 3, **kwargs) -> np.ndarray:
    """
    Binarize using logarithmic standard deviation method optimized for phase contrast.
    
    This method uses local variance to detect texture changes typical of cell boundaries
    in phase contrast microscopy. Based on the original PyAMA implementation.
    
    Args:
        frame: Input phase contrast frame
        mask_size: Size of local window for variance calculation
        **kwargs: Additional parameters (unused)
        
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
    img_bin = binary_dilation(img_bin, structure=struct3)
    
    # 2. Fill holes
    img_bin = binary_fill_holes(img_bin)
    
    # 3. Opening with 5x5 structure (2 iterations)
    struct5 = np.ones((5, 5), dtype=bool)
    img_bin = binary_opening(img_bin, structure=struct5, iterations=2)
    
    # 4. Final erosion
    img_bin = binary_erosion(img_bin, structure=struct3, border_value=1)
    
    return img_bin.astype(np.bool_)


def otsu_binarization(frame: np.ndarray, mask_size: int = 3, **kwargs) -> np.ndarray:
    """
    Binarize using Otsu's method with optional morphological post-processing.
    
    Good for images with bimodal intensity distributions. May not work well
    for phase contrast due to poor intensity contrast.
    
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
        binary = binary_opening(binary, structure=struct)
    
    return binary.astype(np.bool_)


def adaptive_threshold_binarization(frame: np.ndarray, mask_size: int = 15, **kwargs) -> np.ndarray:
    """
    Binarize using adaptive thresholding for images with varying illumination.
    
    Computes local thresholds for different regions of the image, making it
    robust to uneven illumination common in microscopy.
    
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
    
    Uses Sobel edge detection followed by thresholding to identify cell boundaries.
    Good for phase contrast where texture/edge information is more reliable than intensity.
    
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
        binary = binary_opening(binary, structure=struct)
    
    return binary.astype(np.bool_)


def local_threshold_binarization(frame: np.ndarray, mask_size: int = 15, **kwargs) -> np.ndarray:
    """
    Binarize using local statistics (mean + k*std) in sliding windows.
    
    Similar to adaptive thresholding but uses local mean + k*standard_deviation
    as threshold. Good for images with local intensity variations.
    
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
                               methods: Optional[list] = None, **kwargs) -> Dict[str, np.ndarray]:
    """
    Compare multiple binarization methods on the same frame.
    
    Useful for testing and evaluating different algorithms on your data.
    
    Args:
        frame: Input image frame
        mask_size: Size parameter for morphological operations
        methods: List of BinarizationMethod enums to test (None = all methods)
        **kwargs: Additional parameters passed to binarization functions
        
    Returns:
        Dict[str, np.ndarray]: Dictionary mapping method names to binary results
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