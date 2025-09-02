"""Background correction utilities (functional API).

Pipeline:
- mask_image(image, mask) -> masked_image
- tile_image(masked_image, tile_size) -> tiles
- interpolate_tiles(tiles, method) -> background (per frame)
- correct_bg(image, interpolation) -> corrected_image
"""

import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.ndimage import maximum_filter
from dataclasses import dataclass
from typing import Callable


@dataclass
class TileSupport:
    centers_x: np.ndarray
    centers_y: np.ndarray
    support: np.ndarray
    shape: tuple[int, int]


def _mask_image(
    image: np.ndarray,
    mask: np.ndarray,
    size: int = 10,
) -> np.ndarray:
    """Apply `mask` to a single 2D `image`. Masked regions are set to NaN.

    Parameters
    - image: 2D input image array (H, W)
    - mask: 2D boolean mask where True indicates foreground (will be masked out)
    - size: size of the local window for maximum filtering (default: 1).

    Returns
    - masked image (np.ndarray) with dtype float32
    """
    mask_size = 2 * int(size) + 1
    mask = maximum_filter(mask, size=mask_size) > 0

    out = np.full_like(image, np.nan, dtype=np.float32)
    np.copyto(out, image, where=~mask)

    return out


def _tile_image(
    masked_image: np.ndarray,
    tile_size: tuple[int, int] = (256, 256),
) -> TileSupport:
    """Compute overlapping tiles and per-tile medians for a single 2D frame.

    Parameters
    - masked_image: 2D array shaped (H, W) where masked pixels are NaN.
    - tile_size: (tile_height, tile_width) in pixels; tiles overlap by 50%.

    Returns
    - TileSupport dataclass with fields:
      - centers_x, centers_y (float16): coordinates of tile centers in pixel units
      - support (float16 ndarray): medians with shape (n_tiles_y, n_tiles_x)
      - shape (height, width): original frame spatial shape
    """
    height, width = masked_image.shape
    tile_h, tile_w = max(int(tile_size[0]), 1), max(int(tile_size[1]), 1)

    def _div(n: int, ts: int) -> int:
        return max(int(np.ceil(n / ts)) + 1, 2)

    vert_divs, horiz_divs = _div(height, tile_h), _div(width, tile_w)
    bin_edges_y = np.rint(np.linspace(0, height, 2 * vert_divs - 1)).astype(int)
    bin_edges_x = np.rint(np.linspace(0, width, 2 * horiz_divs - 1)).astype(int)
    slices_y = [
        slice(bin_edges_y[i], bin_edges_y[i + 2]) for i in range(bin_edges_y.size - 2)
    ]
    slices_x = [
        slice(bin_edges_x[i], bin_edges_x[i + 2]) for i in range(bin_edges_x.size - 2)
    ]
    centers_y = (bin_edges_y[:-2] + bin_edges_y[2:]) * 0.5
    centers_x = (bin_edges_x[:-2] + bin_edges_x[2:]) * 0.5

    support = np.full((len(slices_y), len(slices_x)), np.nan, dtype=np.float32)
    for y_idx, slice_y in enumerate(slices_y):
        for x_idx, slice_x in enumerate(slices_x):
            support[y_idx, x_idx] = np.nanmedian(masked_image[slice_y, slice_x])

    fallback = np.nanmedian(masked_image)
    support[np.isnan(support)] = fallback

    return TileSupport(
        centers_x=centers_x,
        centers_y=centers_y,
        support=support,
        shape=(height, width),
    )


def _interpolate_tiles(tiles: TileSupport) -> np.ndarray:
    """Interpolate per-tile medians to a 2D background image (float32)."""
    centers_x = tiles.centers_x
    centers_y = tiles.centers_y
    tile_support = tiles.support
    height, width = tiles.shape

    x_coords = np.arange(width)
    y_coords = np.arange(height)

    spline = RectBivariateSpline(centers_x, centers_y, tile_support.T)
    return spline(x_coords, y_coords).astype(np.float32, copy=False).T


def _correct_from_interpolation(
    image: np.ndarray,
    interpolation: np.ndarray,
) -> np.ndarray:
    """Background-correct a single 2D `image` given 2D `interpolation`."""
    corrected = image - interpolation
    return corrected


def correct_bg(
    image: np.ndarray,
    mask: np.ndarray,
    out: np.ndarray,
    progress_callback: Callable | None = None,
) -> None:
    """Loop over frames and write background-corrected frames into `out`.

    This calls the 2D helpers per-frame. `out` must be preallocated with the
    same shape as `image` (T, H, W).
    """
    if image.ndim != 3 or mask.ndim != 3 or out.ndim != 3:
        raise ValueError("image, mask, and out must be 3D arrays with shape (T, H, W)")

    if image.shape != mask.shape or image.shape != out.shape:
        raise ValueError("image, mask, and out must have identical shapes")

    image = image.astype(np.float32, copy=False)
    mask = mask.astype(bool, copy=False)
    out = out.astype(np.float32, copy=False)

    for t in range(image.shape[0]):
        masked = _mask_image(image[t], mask[t])
        tiles = _tile_image(masked)
        interp = _interpolate_tiles(tiles)
        out[t] = _correct_from_interpolation(image[t], interp)
        if progress_callback is not None:
            progress_callback(t, image.shape[0], "Background correction")
