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
    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")

    if image.shape != out.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    image = image.astype(np.uint16, copy=False)
    out = out.astype(np.uint16, copy=False)

    for t in range(image.shape[0]):
        out[t] = image[t]
        if progress_callback is not None:
            progress_callback(t, image.shape[0], "Copying")
