"""
Background correction algorithms for fluorescence microscopy image analysis.
"""

from typing import Callable

import numpy as np
import numpy.ma as ma
import scipy.interpolate as scint
import scipy.ndimage as snd


def _make_tiles(n: int, div: int, name: str = "center") -> np.ndarray:
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
    n_frames, height, width = fluor_chan.shape

    if np.can_cast(fluor_chan, np.float16):
        dtype_interp = np.float16
    elif np.can_cast(fluor_chan, np.float32):
        dtype_interp = np.float32
    else:
        dtype_interp = np.float64
    dtype_interp = np.dtype(dtype_interp)

    bg_interp = np.empty((n_frames, height, width), dtype=dtype_interp)
    bg_mean = np.empty((n_frames, 1, 1), dtype=dtype_interp)

    tiles_vert = _make_tiles(height, div_vert)
    tiles_horiz = _make_tiles(width, div_horiz)
    supp = np.empty((tiles_horiz.size, tiles_vert.size))

    for t in range(n_frames):
        if progress_callback:
            progress_callback(t, n_frames, "Interpolating background")

        masked_frame = ma.masked_array(fluor_chan[t, ...], mask=bin_chan[t, ...])

        for iy, (y, sy) in enumerate(tiles_vert):
            for ix, (x, sx) in enumerate(tiles_horiz):
                supp[ix, iy] = ma.median(masked_frame[sy, sx])

        bg_spline = scint.RectBivariateSpline(x=tiles_horiz["center"], y=tiles_vert["center"], z=supp)
        patch = bg_spline(x=range(width), y=range(height)).T
        bg_interp[t, ...] = patch
        bg_mean[t, ...] = patch.mean()

    normalized_bg = bg_interp / bg_mean
    gain = np.median(normalized_bg, axis=0, keepdims=True)
    corrected = (fluor_chan.astype(dtype_interp) - bg_interp) / gain

    if progress_callback:
        progress_callback(n_frames - 1, n_frames, "Background correction complete")

    return corrected


def schwarzfischer_background_correction(
    fluor_stack: np.ndarray,
    bin_stack: np.ndarray,
    div_horiz: int = 7,
    div_vert: int = 5,
    progress_callback: Callable | None = None,
    output_array: np.ndarray | None = None,
) -> np.ndarray:
    corrected = background_schwarzfischer(
        fluor_stack, bin_stack, div_horiz, div_vert, progress_callback
    )
    if output_array is not None:
        output_array[:] = corrected
        return output_array
    return corrected


def background_morphological_opening(
    fluor_stack: np.ndarray,
    bin_stack: np.ndarray,
    footprint_size: int = 25,
    progress_callback: Callable | None = None,
) -> np.ndarray:
    if fluor_stack.ndim != 3:
        raise ValueError("fluor_stack must be 3D (t, h, w)")

    n_frames, height, width = fluor_stack.shape
    selem = np.ones((footprint_size, footprint_size), dtype=bool)
    corrected = np.empty_like(fluor_stack, dtype=np.float32)

    for t in range(n_frames):
        if progress_callback:
            progress_callback(t, n_frames, "Estimating background (morph open)")
        frame = fluor_stack[t].astype(np.float32, copy=False)
        bg = snd.grey_opening(frame, footprint=selem)
        corr = frame - bg
        corr[corr < 0] = 0
        corrected[t] = corr

    if progress_callback:
        progress_callback(n_frames - 1, n_frames, "Background correction complete")
    return corrected


