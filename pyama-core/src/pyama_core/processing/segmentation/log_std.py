"""Log-STD based segmentation (functional API).

Pipeline (per frame):
- compute_logstd(frame, mask_size) -> log_std_image
- threshold_by_histogram(log_std_image) -> threshold
- threshold and clean morphology -> binary mask

This implementation follows the functional style used in
`processing/background/schwarzfischer.py` and is optimized for
performance and memory usage:
- Uses `scipy.ndimage.uniform_filter` to compute window statistics in O(1) per
  pixel (independent of window size).
- Processes 3D inputs frame-by-frame to keep peak memory low.
- Provides a progress callback for long-running operations
"""

import numpy as np
from scipy.ndimage import (
    uniform_filter,
    binary_fill_holes,
    binary_opening,
    binary_closing,
)
from typing import Callable


def _compute_logstd_2d(image: np.ndarray, size: int = 1) -> np.ndarray:
    """Compute per-pixel log standard deviation for a single 2D frame.

    Uses uniform filtering to compute the mean and mean-of-squares efficiently.
    If the unbiased variance would be zero (constant window), the log-STD is
    left at 0.
    """
    if image.ndim != 2 or image.dtype != np.float32:
        raise ValueError("frame must be a 2D float32 array")

    mask_size = size * 2 + 1
    mean = uniform_filter(image, size=mask_size)
    mean_sq = uniform_filter(image * image, size=mask_size)
    var = mean_sq - mean * mean
    logstd = np.zeros_like(image)
    positive = var > 0
    logstd[positive] = 0.5 * np.log(var[positive])

    return logstd


def _threshold_by_histogram(values: np.ndarray, n_bins: int = 200) -> float:
    """Compute histogram-based threshold.

    - Find the modal bin center (histogram peak) as `hist_max`.
    - Compute sigma as std of values <= hist_max.
    - Threshold = hist_max + 3 * sigma.
    """
    if values.ndim != 2 or values.dtype != np.float32:
        raise ValueError("values must be a 2D float32 array")

    flat = values.ravel()
    counts, edges = np.histogram(flat, bins=n_bins)
    bins = (edges[:-1] + edges[1:]) * 0.5
    hist_max = bins[int(np.argmax(counts))]
    background_vals = flat[flat <= hist_max]
    sigma = np.std(background_vals) if background_vals.size else 0

    return hist_max + 3 * sigma


def _morph_cleanup(mask: np.ndarray, size: int = 7, iterations: int = 3) -> np.ndarray:
    """Apply morphology to remove noise and fill holes (2D mask)."""
    if mask.ndim != 2 or mask.dtype != bool:
        raise ValueError("mask must be a 2D boolean array")

    struct = np.ones((size, size))
    out = binary_fill_holes(mask)
    out = binary_opening(out, iterations=iterations, structure=struct)
    out = binary_closing(out, iterations=iterations, structure=struct)

    return out


def segment(
    image: np.ndarray,
    out: np.ndarray,
    progress_callback: Callable | None = None,
) -> None:
    """Segment a 3D stack using log-STD thresholding.

    This function requires a 3D input with shape (T, H, W) to keep the API
    consistent with other modules (e.g. `background.schwarzfischer`). The
    uniform filter always uses the default border mode (`reflect`).

    Parameters
    - image: 3D (T, H, W) ndarray
    - out: preallocated output ndarray to write boolean mask into (must be same
      shape as `image` and dtype=bool)
    - progress_callback: Optional callback for progress updates

    Returns:
    - None

    Raises:
    - ValueError: if `image` and `out` are not 3D arrays or have different shapes
    """
    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")

    if out.shape != image.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    image = image.astype(np.float32, copy=False)

    for t in range(image.shape[0]):
        logstd = _compute_logstd_2d(image[t])
        thresh = _threshold_by_histogram(logstd)
        binary = logstd > thresh
        out[t] = _morph_cleanup(binary)
        if progress_callback is not None:
            progress_callback(t, image.shape[0], "Segmentation")
