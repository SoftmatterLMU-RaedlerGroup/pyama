"""
Binarization algorithms for microscopy image analysis.
"""

import os
import logging
from typing import Callable

import numpy as np
import numba as nb
import scipy.ndimage as smg

os.environ["NUMBA_LOGGER_LEVEL"] = "WARNING"
logging.getLogger("numba.core.ssa").setLevel(logging.WARNING)
logging.getLogger("numba.core.byteflow").setLevel(logging.WARNING)
logging.getLogger("numba.core.interpreter").setLevel(logging.WARNING)

STRUCT3 = np.ones((3, 3), dtype=bool)
STRUCT5 = np.ones((5, 5), dtype=bool)
STRUCT5[[0, 0, -1, -1], [0, -1, 0, -1]] = False


@nb.njit
def window_std(img):
    return np.sum((img - np.mean(img)) ** 2)


@nb.njit
def generic_filter(img, fun, size=3, reflect=False):
    if size % 2 != 1:
        raise ValueError("'size' must be an odd integer")
    height, width = img.shape
    s2 = size // 2

    img_temp = np.empty((height + 2 * s2, width + 2 * s2), dtype=np.float64)
    img_temp[s2:-s2, s2:-s2] = img
    if reflect:
        img_temp[:s2, s2:-s2] = img[s2 - 1 :: -1, :]
        img_temp[-s2:, s2:-s2] = img[: -s2 - 1 : -1, :]
        img_temp[:, :s2] = img_temp[:, 2 * s2 - 1 : s2 - 1 : -1]
        img_temp[:, -s2:] = img_temp[:, -s2 - 1 : -2 * s2 - 1 : -1]
    else:
        img_temp[:s2, s2:-s2] = img[s2:0:-1, :]
        img_temp[-s2:, s2:-s2] = img[-2 : -s2 - 2 : -1, :]
        img_temp[:, :s2] = img_temp[:, 2 * s2 : s2 : -1]
        img_temp[:, -s2:] = img_temp[:, -s2 - 2 : -2 * s2 - 2 : -1]

    filtered_img = np.empty_like(img, dtype=np.float64)
    for y in range(height):
        for x in range(width):
            filtered_img[y, x] = fun(img_temp[y : y + 2 * s2 + 1, x : x + 2 * s2 + 1])

    return filtered_img


def binarize_frame(img, mask_size=3):
    std_log = generic_filter(img, window_std, size=mask_size)
    std_log[std_log > 0] = (np.log(std_log[std_log > 0]) - np.log(mask_size**2 - 1)) / 2

    counts, edges = np.histogram(std_log, bins=200)
    bins = (edges[:-1] + edges[1:]) / 2
    hist_max = bins[np.argmax(counts)]
    sigma = np.std(std_log[std_log <= hist_max])

    img_bin = std_log >= hist_max + 3 * sigma
    img_bin = smg.binary_dilation(img_bin, structure=STRUCT3)
    img_bin = smg.binary_fill_holes(img_bin)
    img_bin &= smg.binary_opening(img_bin, iterations=2, structure=STRUCT5)
    img_bin = smg.binary_erosion(img_bin, border_value=1)

    return img_bin


def logarithmic_std_binarization(
    data: np.ndarray, mask_size: int = 3, progress_callback: Callable | None = None
) -> np.ndarray:
    if data.ndim == 2:
        data = data[np.newaxis, ...]
        single_frame = True
    else:
        single_frame = False

    n_frames, height, width = data.shape
    binarized = np.zeros((n_frames, height, width), dtype=np.bool_)

    for frame_idx in range(n_frames):
        if progress_callback:
            progress_callback(frame_idx, n_frames, "Binarizing")

        frame = data[frame_idx]
        if frame.dtype != np.float64:
            frame = frame.astype(np.float64)
        binarized[frame_idx] = binarize_frame(frame, mask_size)

    if single_frame:
        return binarized[0]
    return binarized


def global_otsu_binarization(
    data: np.ndarray, progress_callback: Callable | None = None
) -> np.ndarray:
    if data.ndim == 2:
        data = data[np.newaxis, ...]
        single_frame = True
    else:
        single_frame = False

    n_frames, height, width = data.shape
    binary = np.zeros((n_frames, height, width), dtype=np.bool_)

    for i in range(n_frames):
        if progress_callback:
            progress_callback(i, n_frames, "Binarizing (Otsu)")
        frame = data[i].astype(np.float64, copy=False)
        flat = frame.ravel()
        flat = flat[np.isfinite(flat)]
        if flat.size == 0:
            binary[i] = False
            continue
        counts, bin_edges = np.histogram(flat, bins=256)
        bin_mids = (bin_edges[:-1] + bin_edges[1:]) / 2
        total = flat.size
        weight_b = np.cumsum(counts)
        weight_f = total - weight_b
        valid = (weight_b > 0) & (weight_f > 0)
        if not np.any(valid):
            thresh = bin_mids[np.argmax(counts)]
        else:
            mean_total = np.sum(counts * bin_mids) / total
            mean_b = np.cumsum(counts * bin_mids)
            mean_f = (mean_total * total - mean_b) / np.maximum(weight_f, 1)
            mean_b = mean_b / np.maximum(weight_b, 1)
            between_var = weight_b * weight_f * (mean_b - mean_f) ** 2
            between_var[~valid] = -1
            idx = int(np.argmax(between_var))
            thresh = bin_mids[idx]
        binary[i] = frame >= thresh

    return binary[0] if single_frame else binary


def cellpose_binarization(
    data: np.ndarray,
    model: str = "cyto",
    diameter: float | None = None,
    progress_callback: Callable | None = None,
) -> np.ndarray:
    raise NotImplementedError(
        "Cellpose segmentation is not implemented yet. Select another method or extend this stub."
    )


