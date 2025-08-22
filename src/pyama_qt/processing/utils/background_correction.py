"""
Background correction algorithms for fluorescence microscopy image analysis.

This module contains the Schwarzfischer et al. background correction algorithm
optimized for fluorescence channels with cellular segmentation masks.

Based on:
"Efficient fluorescence image normalization for time lapse movies"
https://push-zb.helmholtz-muenchen.de/frontdoor.php?source_opus=6773

Based on "background_correction.py"
of commit f46236d89b18ec8833e54bbdfe748f3e5bce6924
in repository https://gitlab.physik.uni-muenchen.de/lsr-pyama/schwarzfischer
"""

from typing import Callable

import numpy as np
import numpy.ma as ma
import scipy.interpolate as scint
import scipy.ndimage as snd


def _make_tiles(n: int, div: int, name: str = "center") -> np.ndarray:
    """Create overlapping tiles for background interpolation.

    Each pair of neighboring tiles is overlapped by a third tile, resulting in a total tile number
    of `2 * div - 1` tiles for each direction.
    Due to integer rounding, the sizes may slightly vary between tiles.

    Args:
        n: Size of dimension to tile
        div: Number of non-overlapping divisions
        name: Name for the center coordinate field

    Returns:
        Structured array with tile centers and slices
    """
    borders = np.rint(np.linspace(0, n, 2 * div - 1)).astype(np.uint16)
    tiles = np.empty(len(borders) - 2, dtype=[(name, float), ("slice", object)])
    for i, (b1, b2) in enumerate(zip(borders[:-2], borders[2:])):
        tiles[i] = (b1 + b2) / 2, slice(b1, b2)
    return tiles


def background_schwarzfischer(
    fluor_chan: np.ndarray,
    bin_chan: np.ndarray,
    div_horiz: int = 7,
    div_vert: int = 5,
    progress_callback: Callable | None = None,
) -> np.ndarray:
    """Perform background correction according to Schwarzfischer et al.

    Arguments:
        fluor_chan: (frames x height x width) numpy array; the fluorescence channel to be corrected
        bin_chan: boolean numpy array of same shape as fluor_chan; segmentation map (background=False, cell=True)
        div_horiz: int; number of (non-overlapping) tiles in horizontal direction
        div_vert: int; number of (non-overlapping) tiles in vertical direction
        progress_callback: Optional callback function(frame_idx, n_frames, message) for progress updates

    Returns:
        Background-corrected fluorescence channel as numpy array (dtype single) of same shape as fluor_chan
    """
    n_frames, height, width = fluor_chan.shape

    # Allocate arrays with appropriate dtype (matching original PyAMA logic)
    if np.can_cast(fluor_chan, np.float16):
        dtype_interp = np.float16
    elif np.can_cast(fluor_chan, np.float32):
        dtype_interp = np.float32
    else:
        dtype_interp = np.float64
    dtype_interp = np.dtype(dtype_interp)

    # Arrays to store interpolated backgrounds and means
    bg_interp = np.empty((n_frames, height, width), dtype=dtype_interp)
    bg_mean = np.empty((n_frames, 1, 1), dtype=dtype_interp)

    # Construct tiles for background interpolation
    # Each pair of neighboring tiles is overlapped by a third tile, resulting in a total tile number
    # of `2 * div_i - 1` tiles for each direction `i` in {`horiz`, `vert`}.
    # Due to integer rounding, the sizes may slightly vary between tiles.
    tiles_vert = _make_tiles(height, div_vert)
    tiles_horiz = _make_tiles(width, div_horiz)
    supp = np.empty((tiles_horiz.size, tiles_vert.size))

    # Interpolate background as cubic spline with each tile's median as support point at the tile center
    for t in range(n_frames):
        if progress_callback:
            progress_callback(t, n_frames, "Interpolating background")

        masked_frame = ma.masked_array(fluor_chan[t, ...], mask=bin_chan[t, ...])

        for iy, (y, sy) in enumerate(tiles_vert):
            for ix, (x, sx) in enumerate(tiles_horiz):
                supp[ix, iy] = ma.median(masked_frame[sy, sx])

        bg_spline = scint.RectBivariateSpline(
            x=tiles_horiz["center"], y=tiles_vert["center"], z=supp
        )
        patch = bg_spline(x=range(width), y=range(height)).T
        bg_interp[t, ...] = patch
        bg_mean[t, ...] = patch.mean()

    # Correct for background using Schwarzfischer's formula:
    #   corrected_image = (raw_image - interpolated_background) / gain
    # wherein, in opposite to Schwarzfischer, the gain is approximated as
    #   median(interpolated_background / mean_background)

    # Calculate gain (median of normalized backgrounds)
    # This is a per-pixel temporal median
    normalized_bg = bg_interp / bg_mean  # Shape: (n_frames, height, width)
    gain = np.median(normalized_bg, axis=0, keepdims=True)  # Shape: (1, height, width)

    # Apply correction
    corrected = (fluor_chan.astype(dtype_interp) - bg_interp) / gain

    if progress_callback:
        progress_callback(n_frames - 1, n_frames, "Background correction complete")

    return corrected


# Keep the original function name for compatibility
def schwarzfischer_background_correction(
    fluor_stack: np.ndarray,
    bin_stack: np.ndarray,
    div_horiz: int = 7,
    div_vert: int = 5,
    progress_callback: Callable | None = None,
    output_array: np.ndarray | None = None,
) -> np.ndarray:
    """Wrapper for background_schwarzfischer with output array support.

    This function provides compatibility with the PyAMA-Qt interface while
    using the exact original PyAMA algorithm.

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
    # Call the original algorithm
    corrected = background_schwarzfischer(
        fluor_stack, bin_stack, div_horiz, div_vert, progress_callback
    )

    # Handle output array if provided
    if output_array is not None:
        output_array[:] = corrected
        return output_array
    else:
        return corrected


def background_morphological_opening(
	fluor_stack: np.ndarray,
	bin_stack: np.ndarray,
	footprint_size: int = 25,
	progress_callback: Callable | None = None,
) -> np.ndarray:
	"""
	Background correction using grayscale morphological opening per frame.

	Args:
		fluor_stack: (frames, height, width) fluorescence data
		bin_stack: boolean segmentation (True=cell). Currently unused but reserved for later masking refinements
		footprint_size: side length of square structuring element
		progress_callback: optional progress callback

	Returns:
		Corrected stack of same shape as input
	"""
	if fluor_stack.ndim != 3:
		raise ValueError("fluor_stack must be 3D (t, h, w)")

	n_frames, height, width = fluor_stack.shape
	selem = np.ones((footprint_size, footprint_size), dtype=bool)
	corrected = np.empty_like(fluor_stack, dtype=np.float32)

	for t in range(n_frames):
		if progress_callback:
			progress_callback(t, n_frames, "Estimating background (morph open)")
		frame = fluor_stack[t].astype(np.float32, copy=False)
		# Estimate smooth background by morphological opening
		bg = snd.grey_opening(frame, footprint=selem)
		# Subtractive correction; clip to minimum zero
		corr = frame - bg
		corr[corr < 0] = 0
		corrected[t] = corr

	if progress_callback:
		progress_callback(n_frames - 1, n_frames, "Background correction complete")
	return corrected
