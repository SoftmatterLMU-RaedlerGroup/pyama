"""
Utility for copying channels from ND2 files into NPY files with progress reporting.
"""

from typing import Callable

import numpy as np


def copy_npy(
    image: np.ndarray,
    out: np.ndarray,
    progress_callback: Callable | None = None,
) -> None:
    """Copy image into out."""
    import logging

    logger = logging.getLogger(__name__)

    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")

    if image.shape != out.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    image = image.astype(np.uint16, copy=False)
    out = out.astype(np.uint16, copy=False)

    logger.info(f"copy_npy: Starting copy of {image.shape} array")

    for t in range(image.shape[0]):
        out[t] = image[t]
        if t % 100 == 0:  # Log every 100 frames to avoid too much output
            logger.debug(f"copy_npy: Copied frame {t}/{image.shape[0]}")
        if progress_callback is not None:
            progress_callback(t, image.shape[0], "Copying")

    logger.info(f"copy_npy: Completed copy of {image.shape[0]} frames")
