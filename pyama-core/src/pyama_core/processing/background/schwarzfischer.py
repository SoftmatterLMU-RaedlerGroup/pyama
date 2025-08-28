"""Background correction utilities (functional API).

Pipeline:
- mask_image(image, mask) -> masked_image
- tile_image(masked_image, tile_size) -> tiles
- interpolate_tiles(tiles, method) -> background (per frame)
- correct(image, interpolation) -> corrected_image
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import RectBivariateSpline
from dataclasses import dataclass


def _mask_image(image: np.ndarray, mask: np.ndarray, fill_value: float | None = np.nan) -> np.ndarray:
    """Apply `mask` to `image`. Masked-out regions are set to `fill_value`.

    Parameters
    - image: input image array
    - mask: boolean mask where True indicates foreground (keep)
    - fill_value: value to fill masked-out regions (default: nan)

    Returns
    - masked image (np.ndarray)
    
    Optimizations:
    - Avoid creating more than one full-size temporary when possible.
    - Reuse a dtype-converted view of `image` and write masked-out values in-place
      into a single output array to reduce peak memory.
    """
    # Require 3D inputs (T, H, W)
    if image.ndim != 3 or mask.ndim != 3:
        raise ValueError("image and mask must be 3D arrays with shape (T, H, W)")
    if image.shape != mask.shape:
        raise ValueError("image and mask must have identical shapes")

    # Ensure boolean mask (may copy a small boolean view)
    m = np.asarray(mask, dtype=bool)

    # Convert image to target dtype; if it already matches this will be a view.
    img = image.astype(np.float16, copy=False)

    # If the input is already float16 and the mask keeps most values, we can try
    # to avoid allocating a second full array by modifying a copy-on-write view.
    # Strategy: allocate one output array and fill masked-out positions.
    out = np.empty_like(img, dtype=np.float16)

    # Copy kept values into output (this will allocate once) then fill the rest.
    # Using boolean indexing copies only selected elements but still writes into
    # the single preallocated output buffer.
    out[...] = fill_value  # initialize with fill_value (scalar)
    out[m] = img[m]
    return out


@dataclass
class TileSupport:
    centers_x: np.ndarray
    centers_y: np.ndarray
    support: np.ndarray
    shape: tuple[int, int]


def _tile_image(masked_image: np.ndarray, tile_size: tuple[int, int]) -> TileSupport:
    """Compute overlapping tiles and per-frame tile medians (supports).

    Parameters
    - masked_image: 3D array shaped (T, H, W) where masked pixels are NaN.
    - tile_size: (tile_height, tile_width) in pixels; tiles overlap by 50%.

    Returns
    - TileSupport dataclass with fields:
      - centers_x, centers_y (float32): coordinates of tile centers in pixel units
      - support (float16 ndarray): per-frame medians with shape (T, n_tiles_y, n_tiles_x)
      - shape (height, width): original frame spatial shape

    Notes
    - Any tiles with all-NaN pixels per frame are filled in-place with a per-frame
      fallback (median if frame contains NaNs, otherwise mean).
    - `centers_x/centers_y` are kept as float32 for interpolation precision; `support`
      is stored as float16 to reduce memory.
    """
    if masked_image.ndim != 3:
        raise ValueError("masked_image must be 3D (T,H,W)")

    num_frames, height, width = masked_image.shape
    tile_h, tile_w = max(int(tile_size[0]), 1), max(int(tile_size[1]), 1)

    def _div(n: int, ts: int) -> int:
        return max(int(np.ceil(n / ts)) + 1, 2)

    vert_divs, horiz_divs = _div(height, tile_h), _div(width, tile_w)
    bin_edges_y = np.rint(np.linspace(0, height, 2 * vert_divs - 1)).astype(np.int32)
    bin_edges_x = np.rint(np.linspace(0, width, 2 * horiz_divs - 1)).astype(np.int32)
    slices_y = [slice(bin_edges_y[i], bin_edges_y[i + 2]) for i in range(bin_edges_y.size - 2)]
    slices_x = [slice(bin_edges_x[i], bin_edges_x[i + 2]) for i in range(bin_edges_x.size - 2)]
    centers_y = ((bin_edges_y[:-2] + bin_edges_y[2:]) * 0.5).astype(np.float32)
    centers_x = ((bin_edges_x[:-2] + bin_edges_x[2:]) * 0.5).astype(np.float32)

    # Pre-fill support with NaNs so we can fill only missing tiles in-place
    support = np.full((num_frames, len(slices_y), len(slices_x)), np.nan, dtype=np.float16)
    for y_idx, slice_y in enumerate(slices_y):
        for x_idx, slice_x in enumerate(slices_x):
            # Compute per-frame median for this tile (returns shape (num_frames,))
            medians_per_frame = np.nanmedian(masked_image[:, slice_y, slice_x], axis=(1, 2))
            support[:, y_idx, x_idx] = medians_per_frame.astype(np.float16)

    # Replace any NaNs per-frame with a fallback computed from the full frame.
    # Do this in-place to avoid allocating another full-size array.
    for frame_idx in range(num_frames):
        missing_tiles = np.isnan(support[frame_idx])
        if missing_tiles.any():
            fallback_value = (
                float(np.nanmedian(masked_image[frame_idx]))
                if np.isnan(masked_image[frame_idx]).any()
                else float(np.mean(masked_image[frame_idx]))
            )
            # fill only the missing tile entries
            support[frame_idx][missing_tiles] = np.float16(fallback_value)

    return TileSupport(centers_x=centers_x, centers_y=centers_y, support=support, shape=(height, width))


def _interpolate_tiles(tiles: TileSupport, method: str = "bilinear") -> np.ndarray:
    """Interpolate per-tile medians to a per-frame background image.

    This implementation minimizes temporaries by reusing a working float buffer
    for per-frame tile support (SciPy expects double precision).
    """
    centers_x = tiles.centers_x
    centers_y = tiles.centers_y
    tile_support = tiles.support  # shape (T, n_tiles_y, n_tiles_x)
    height, width = tiles.shape

    # Basic validation of TileSupport contents
    if tile_support.ndim != 3:
        raise ValueError("tiles.support must be a 3D array with shape (T, n_tiles_y, n_tiles_x)")
    if centers_x.ndim != 1 or centers_y.ndim != 1:
        raise ValueError("tiles.centers_x and tiles.centers_y must be 1D coordinate arrays")

    required_k = 1 if method == "bilinear" else 3
    kx = min(required_k, max(int(centers_x.size) - 1, 1))
    ky = min(required_k, max(int(centers_y.size) - 1, 1))

    num_frames, n_tiles_y, n_tiles_x = tile_support.shape

    # allocate output and reusable work buffer (float64) for SciPy
    background = np.empty((num_frames, height, width), dtype=np.float16)
    work_z = np.empty((n_tiles_x, n_tiles_y), dtype=float)

    x_coords = np.arange(width, dtype=float)
    y_coords = np.arange(height, dtype=float)

    # SciPy expects z shaped like (x, y) or (nx, ny) depending on call; we used
    # transposed data historically, so maintain that ordering by transposing when
    # copying into the work buffer.
    for frame_idx in range(num_frames):
        # copy and upcast to the work buffer without creating a temporary
        work_z[...] = tile_support[frame_idx].T
        spline = RectBivariateSpline(centers_x, centers_y, work_z, kx=kx, ky=ky, s=0.0)
        patch = spline(x_coords, y_coords).T
        background[frame_idx] = patch.astype(np.float16, copy=False)

    return background


def _correct_from_interpolation(image: np.ndarray, interpolation: np.ndarray) -> np.ndarray:
    """Background-correct `image` given per-frame `interpolation` (background).

    Optimizations and clarity:
    - Work in float16 storage where possible, but upcast once to float32 for
      numeric reductions and arithmetic to minimize repeated conversions.
    - Reuse upcasted buffers to reduce temporaries.
    """
    # Keep storage as float16 where possible
    image_f16 = image.astype(np.float16, copy=False)
    interp_f16 = interpolation.astype(np.float16, copy=False)

    # Assume inputs are 3D arrays (T, H, W)
    if image_f16.ndim != 3 or interp_f16.ndim != 3:
        raise ValueError("image and interpolation must be 3D arrays with shape (T, H, W)")

    frames = image_f16
    if frames.shape != interp_f16.shape:
        raise ValueError("image and interpolation must have the same shape")

    # Upcast once to float32 for calculations
    eps = np.float32(1e-6)
    interp_f32 = interp_f16.astype(np.float32, copy=False)
    frames_f32 = frames.astype(np.float32, copy=False)

    # Compute per-frame mean of background for normalization
    mean_bg_per_frame = interp_f32.reshape(interp_f32.shape[0], -1).mean(axis=1).astype(np.float32)

    # Normalize background per-frame and compute gain map (median across frames)
    norm_bg = interp_f32 / (mean_bg_per_frame[:, None, None] + eps)
    gain_map = np.median(norm_bg, axis=0).astype(np.float32)

    # Apply correction: (frame - background) / gain
    corrected_f32 = (frames_f32 - interp_f32) / (gain_map[None, ...] + eps)
    corrected_f16 = corrected_f32.astype(np.float16)

    return corrected_f16


def correct(image: np.ndarray, mask: np.ndarray, tile_size: tuple[int, int], method: str = "bilinear") -> np.ndarray:
    """Convenience function chaining the steps to return a corrected image.

    This chains masking, tiling, interpolation and correction.
    """
    # Invert mask so foreground (cells=True) are excluded from background stats
    masked = _mask_image(image, ~mask)
    tiles = _tile_image(masked, tile_size)
    interp = _interpolate_tiles(tiles, method=method)
    corrected = _correct_from_interpolation(image, interp)
    return corrected


__all__ = ["correct"]


