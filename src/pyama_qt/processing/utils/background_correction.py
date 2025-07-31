"""
Background correction algorithms for fluorescence microscopy image analysis.

This module contains the Schwarzfischer et al. background correction algorithm
optimized for fluorescence channels with cellular segmentation masks.

Based on:
"Efficient fluorescence image normalization for time lapse movies"
https://push-zb.helmholtz-muenchen.de/frontdoor.php?source_opus=6773
"""

import numpy as np
import numpy.ma as ma
import scipy.interpolate as scint


def _make_tiles(n: int, div: int, name: str = 'center') -> np.ndarray:
    """Create overlapping tiles for background interpolation.
    
    Args:
        n: Size of dimension to tile
        div: Number of non-overlapping divisions
        name: Name for the center coordinate field
        
    Returns:
        Structured array with tile centers and slices
    """
    borders = np.rint(np.linspace(0, n, 2*div-1)).astype(np.uint16)
    tiles = np.empty(len(borders)-2, dtype=[(name, float), ('slice', object)])
    for i, (b1, b2) in enumerate(zip(borders[:-2], borders[2:])):
        tiles[i] = (b1 + b2) / 2, slice(b1, b2)
    return tiles


def background_schwarzfischer(fluor_stack: np.ndarray, bin_stack: np.ndarray, 
                             div_horiz: int = 7, div_vert: int = 5,
                             progress_callback: callable = None,
                             output_array: np.ndarray = None) -> np.ndarray:
    """Perform background correction according to Schwarzfischer et al. with temporal gain.

    This algorithm divides each frame into overlapping tiles, calculates the
    median background intensity in each tile (excluding segmented cells), 
    interpolates a smooth background surface using cubic splines, and then
    corrects the original image by subtracting this background and normalizing
    by a temporal median gain factor.

    Args:
        fluor_stack: Fluorescence stack (frames x height x width)
        bin_stack: Boolean segmentation mask stack (background=False, cell=True)
        div_horiz: Number of non-overlapping tiles in horizontal direction
        div_vert: Number of non-overlapping tiles in vertical direction
        progress_callback: Optional callback function(frame_idx, n_frames, message) for progress updates
        output_array: Optional pre-allocated output array to write results to

    Returns:
        Background-corrected fluorescence stack (same shape as input)
    """
    n_frames, height, width = fluor_stack.shape

    # Allocate arrays with appropriate dtype
    if np.can_cast(fluor_stack.dtype, np.float32):
        dtype_interp = np.float32
    else:
        dtype_interp = np.float64
    
    # Construct tiles for background interpolation
    tiles_vert = _make_tiles(height, div_vert)
    tiles_horiz = _make_tiles(width, div_horiz)
    
    # Arrays to store interpolated backgrounds and means
    bg_interp_all = np.empty((n_frames, height, width), dtype=dtype_interp)
    bg_mean_all = np.empty((n_frames, 1, 1), dtype=dtype_interp)
    
    # First pass: Calculate interpolated backgrounds for all frames
    for frame_idx in range(n_frames):
        fluor_frame = fluor_stack[frame_idx]
        bin_frame = bin_stack[frame_idx]
        
        # Calculate support points for spline interpolation
        supp = np.empty((tiles_horiz.size, tiles_vert.size))
        masked_frame = ma.masked_array(fluor_frame, mask=bin_frame)
        
        for iy, (_, sy) in enumerate(tiles_vert):
            for ix, (_, sx) in enumerate(tiles_horiz):
                supp[ix, iy] = ma.median(masked_frame[sy, sx])
        
        # Interpolate background
        bg_spline = scint.RectBivariateSpline(
            x=tiles_horiz['center'], 
            y=tiles_vert['center'], 
            z=supp
        )
        bg_interp = bg_spline(x=range(width), y=range(height)).T.astype(dtype_interp)
        bg_interp_all[frame_idx] = bg_interp
        bg_mean_all[frame_idx] = bg_interp.mean()
        
        # Progress callback
        if progress_callback and frame_idx % 10 == 0:
            progress_callback(frame_idx, n_frames, "Interpolating backgrounds")
    
    # Calculate temporal median gain (matching original PyAMA)
    # Normalize each background by its mean, then take temporal median
    normalized_bg = bg_interp_all / bg_mean_all
    temporal_gain = np.median(normalized_bg, axis=0, keepdims=True)
    
    # Notify about applying correction
    if progress_callback:
        progress_callback(n_frames-1, n_frames, "Applying temporal correction")
    
    # Apply correction to all frames
    if output_array is None:
        corrected_stack = (fluor_stack.astype(dtype_interp) - bg_interp_all) / temporal_gain
        return corrected_stack
    else:
        # Write directly to provided output array
        output_array[:] = (fluor_stack.astype(dtype_interp) - bg_interp_all) / temporal_gain
        return output_array

