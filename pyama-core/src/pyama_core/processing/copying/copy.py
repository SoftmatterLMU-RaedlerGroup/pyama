"""
Utility for copying channels from ND2 files into NPY files with progress reporting.
"""

from pathlib import Path
from typing import Callable

import numpy as np
from numpy.lib.format import open_memmap

from pyama_core.io.nikon import load_nd2
from pyama_core.io.nikon import ND2Metadata


def copy_npy(
    metadata: ND2Metadata,
    f: int,
    channels: list[int],
    output_dir: Path,
    progress_callback: Callable | None = None,
) -> dict[int, Path]:
    """Copy channels from an ND2 file into NPY memmaps.

    Parameters
    - metadata: metadata from the ND2 file
    - f: field-of-view index to extract
    - channels: list of channel indices
    - output_dir: directory where `fov_XXXX` will be created
    - progress_callback: optional callback(frame_index, total_frames, message)

    Returns
    - dict mapping channel indices to NPY path
    """

    da, _ = load_nd2(metadata.nd2_path)
    fov_dir = output_dir / f"fov_{f:04d}"
    fov_dir.mkdir(parents=True, exist_ok=True)
    basename = metadata.basename
    T, H, W = metadata.n_frames, metadata.height, metadata.width

    results: dict[int, Path] = {}
    for ch in channels:
        ch_path = fov_dir / f"{basename}_fov_{f:04d}_{metadata.channels[ch]}_raw.npy"
        ch_memmap = open_memmap(ch_path, mode="w+", dtype=np.uint16, shape=(T, H, W))

        for t in range(T):
            ch_memmap[t] = da.isel(P=f, C=ch, T=t).compute().values
        ch_memmap.close()

        if progress_callback is not None:
            progress_callback(t, T, f"Copying {metadata.channels[ch]}")

        results[ch] = ch_path

    return results
