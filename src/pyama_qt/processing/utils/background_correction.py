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


def background_schwarzfischer(fluor_frame: np.ndarray, bin_frame: np.ndarray, 
                             div_horiz: int = 7, div_vert: int = 5) -> np.ndarray:
    """Perform background correction on a single frame according to Schwarzfischer et al.

    This algorithm divides the frame into overlapping tiles, calculates the
    median background intensity in each tile (excluding segmented cells), 
    interpolates a smooth background surface using cubic splines, and then
    corrects the original image by subtracting this background and normalizing
    by a gain factor.

    Args:
        fluor_frame: Single fluorescence frame (height x width)
        bin_frame: Boolean segmentation mask (background=False, cell=True)
        div_horiz: Number of non-overlapping tiles in horizontal direction
        div_vert: Number of non-overlapping tiles in vertical direction

    Returns:
        Background-corrected fluorescence frame (same shape as input)
    """
    height, width = fluor_frame.shape

    # Allocate arrays with appropriate dtype
    if np.can_cast(fluor_frame, np.float32):
        dtype_interp = np.float32
    else:
        dtype_interp = np.float64
    
    # Construct tiles for background interpolation
    # Each pair of neighboring tiles is overlapped by a third tile, resulting in a total tile number
    # of `2 * div_i - 1` tiles for each direction `i` in {`horiz`, `vert`}.
    # Due to integer rounding, the sizes may slightly vary between tiles.
    tiles_vert = _make_tiles(height, div_vert)
    tiles_horiz = _make_tiles(width, div_horiz)
    supp = np.empty((tiles_horiz.size, tiles_vert.size))

    # Interpolate background as cubic spline with each tile's median as support point at the tile center
    masked_frame = ma.masked_array(fluor_frame, mask=bin_frame)
    for iy, (_, sy) in enumerate(tiles_vert):
        for ix, (_, sx) in enumerate(tiles_horiz):
            supp[ix, iy] = ma.median(masked_frame[sy, sx])
    
    bg_spline = scint.RectBivariateSpline(x=tiles_horiz['center'], y=tiles_vert['center'], z=supp)
    bg_interp = bg_spline(x=range(width), y=range(height)).T.astype(dtype_interp)
    bg_mean = bg_interp.mean()

    # Correct for background using Schwarzfischer's formula:
    #   corrected_image = (raw_image - interpolated_background) / gain
    # wherein, in opposite to Schwarzfischer, the gain is approximated as
    #   median(interpolated_background / mean_background)
    gain = np.median(bg_interp / bg_mean)
    corrected = (fluor_frame.astype(dtype_interp) - bg_interp) / gain

    return corrected


