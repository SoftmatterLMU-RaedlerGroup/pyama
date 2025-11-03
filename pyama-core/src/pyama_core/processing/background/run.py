"""Background estimation via tiled interpolation (functional API).

Pipeline per frame:
- mask image by foreground to estimate background from background pixels
- compute overlapping tile medians across the frame
- interpolate a smooth background from tile medians
- output the interpolated background (correction is saved for later)

The public entrypoint ``estimate_background`` loops over frames and writes the
interpolated background into the provided output array.
"""

import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.ndimage import binary_dilation
from dataclasses import dataclass
from typing import Callable


@dataclass
class TileSupport:
    """Support data for tiled background interpolation.

    Attributes:
        centers_x: 1D array of tile center ``x`` coordinates (pixels).
        centers_y: 1D array of tile center ``y`` coordinates (pixels).
        support: 2D array ``(n_tiles_y, n_tiles_x)`` of tile medians.
        shape: Spatial ``(H, W)`` shape of the original frame.
    """

    centers_x: np.ndarray
    centers_y: np.ndarray
    support: np.ndarray
    shape: tuple[int, int]


def _mask_image(
    image: np.ndarray,
    mask: np.ndarray,
    dilation_size: int = 21,
) -> np.ndarray:
    """Mask foreground in a 2D image using a dilated mask.

    Creates a dilated copy of the boolean ``mask`` with a square structuring element
    of size ``dilation_size x dilation_size`` to expand foreground, then copies pixels
    from ``image`` where the (dilated) mask is False and sets masked pixels to ``NaN``.
    
    The original mask is not modified - dilation is applied to a copy.

    Args:
        image: 2D float-like array ``(H, W)``.
        mask: 2D boolean array ``(H, W)``; True marks foreground. This mask
            is not modified.
        dilation_size: Size of the square structuring element for dilation.

    Returns:
        ``float32`` array with foreground set to ``NaN``.
    """
    # Create structuring element for dilation
    dilation_struct = np.ones((dilation_size, dilation_size), dtype=bool)
    # Create dilated mask copy without modifying the original
    dilated_mask = binary_dilation(mask, structure=dilation_struct)

    out = np.full_like(image, np.nan, dtype=np.float32)
    np.copyto(out, image, where=~dilated_mask)

    return out


def _tile_image(
    masked_image: np.ndarray,
    tile_size: tuple[int, int] = (256, 256),
) -> TileSupport:
    """Compute overlapping tiles and per-tile medians for a 2D frame.

    Tiles overlap by ~50% in each dimension. NaN pixels are ignored when
    computing medians and replaced by the global median as a fallback.

    Args:
        masked_image: 2D array ``(H, W)`` with masked pixels as ``NaN``.
        tile_size: ``(tile_height, tile_width)`` in pixels.

    Returns:
        ``TileSupport`` with tile center coordinates, median support, and shape.
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
    for y_id, slice_y in enumerate(slices_y):
        for x_id, slice_x in enumerate(slices_x):
            support[y_id, x_id] = np.nanmedian(masked_image[slice_y, slice_x])

    fallback = np.nanmedian(masked_image)
    support[np.isnan(support)] = fallback

    return TileSupport(
        centers_x=centers_x,
        centers_y=centers_y,
        support=support,
        shape=(height, width),
    )


def _interpolate_tiles(tiles: TileSupport) -> np.ndarray:
    """Interpolate tile medians to a smooth 2D background image.

    Args:
        tiles: Tile support containing centers and per-tile medians.

    Returns:
        ``float32`` background image of shape ``tiles.shape``.
    """
    centers_x = tiles.centers_x
    centers_y = tiles.centers_y
    tile_support = tiles.support
    height, width = tiles.shape

    x_coords = np.arange(width)
    y_coords = np.arange(height)

    spline = RectBivariateSpline(centers_x, centers_y, tile_support.T)
    return spline(x_coords, y_coords).astype(np.float32, copy=False).T


def estimate_background(
    image: np.ndarray,
    mask: np.ndarray,
    out: np.ndarray,
    progress_callback: Callable | None = None,
    cancel_event=None,
) -> None:
    """Estimate background for a 3D stack frame-by-frame using tiled interpolation.

    For each frame, applies a dilated foreground mask, computes overlapping
    tile medians, and interpolates a smooth background surface. Writes the
    interpolated background into ``out`` in-place. The correction step (subtraction)
    can be applied later by subtracting the background from the original image.

    Args:
        image: 3D float-like array ``(T, H, W)`` of fluorescence data.
        mask: 3D boolean array ``(T, H, W)``; True marks foreground regions.
        out: Preallocated ``float32`` array ``(T, H, W)`` for background interpolation output.
        progress_callback: Optional callable ``(t, total, msg)`` for progress reporting.
        cancel_event: Optional threading.Event for cancellation support.

    Returns:
        None. Background interpolation is written to ``out``.

    Raises:
        ValueError: If inputs are not 3D or shapes do not match.
    """
    if image.ndim != 3 or mask.ndim != 3 or out.ndim != 3:
        raise ValueError("image, mask, and out must be 3D arrays with shape (T, H, W)")

    if image.shape != mask.shape or image.shape != out.shape:
        raise ValueError("image, mask, and out must have identical shapes")

    image = image.astype(np.float32, copy=False)
    mask = mask.astype(bool, copy=False)
    out = out.astype(np.float32, copy=False)

    for t in range(image.shape[0]):
        # Check for cancellation before processing each frame
        if cancel_event and cancel_event.is_set():
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Background estimation cancelled at frame {t}")
            return

        masked = _mask_image(image[t], mask[t])
        tiles = _tile_image(masked)
        interp = _interpolate_tiles(tiles)
        out[t] = interp
        if progress_callback is not None:
            progress_callback(t, image.shape[0], "Background estimation")
