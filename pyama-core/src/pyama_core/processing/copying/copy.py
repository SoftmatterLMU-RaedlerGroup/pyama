"""
Utility for copying channels from ND2 files into NPY files with progress reporting.
"""

from pathlib import Path
from typing import Callable

import numpy as np
from numpy.lib.format import open_memmap

from pyama_core.io.nd2_loader import get_nd2_frame, load_nd2


def copy_npy(
    nd2_path: str,
    fov: int,
    channels: list[tuple[int, str]],
    output_dir: Path,
    progress_callback: Callable | None = None,
) -> dict[int, tuple[str, Path]]:
    """Copy channels from an ND2 file into NPY memmaps.

    Parameters
    - nd2_path: path to the ND2 file
    - fov: field-of-view index to extract
    - channels: list of (channel_index, channel_name) tuples
    - output_dir: directory where `fov_XXXX` will be created
    - progress_callback: optional callback(frame_index, total_frames, message)

    Returns
    - dict mapping channel indices to (name, path) tuples
    """

    da, metadata = load_nd2(nd2_path)
    fov_dir = output_dir / f"fov_{fov:04d}"
    fov_dir.mkdir(parents=True, exist_ok=True)
    base_name = metadata.filename.replace(".nd2", "")
    T, H, W = metadata.n_frames, metadata.height, metadata.width

    copied_all: dict[int, tuple[str, Path]] = {}
    for ch in channels:
        ch_idx, ch_name = ch
        ch_path = fov_dir / f"{base_name}_fov_{fov:04d}_{ch_name}_raw.npy"
        ch_memmap = open_memmap(ch_path, mode="w+", dtype=np.uint16, shape=(T, H, W))
        
        for t in range(T):
            ch_memmap[t] = get_nd2_frame(da, fov, ch_idx, t)
        ch_memmap.close()

        if progress_callback is not None:
            progress_callback(t, T, f"Copying {ch_name}")

        copied_all[ch_idx] = (ch_name, ch_path)

    return copied_all
