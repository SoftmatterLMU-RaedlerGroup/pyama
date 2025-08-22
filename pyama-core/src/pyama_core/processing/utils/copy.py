"""
Utility for copying channels from ND2 files into NPY files with progress reporting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from numpy.lib.format import open_memmap

from pyama_core.utils.nd2_loader import get_nd2_frame, create_nd2_xarray


def _convert_to_uint16(frame: np.ndarray) -> np.ndarray:
    if frame.dtype == np.uint8:
        return frame.astype(np.uint16) * 257
    if frame.dtype in (np.uint16, np.int16):
        return frame.astype(np.uint16)
    return frame.astype(np.uint16)


def copy_channels_to_npy(
    nd2_path: str,
    fov_index: int,
    data_info: dict[str, object],
    output_dir: Path,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict[str, Path]:
    metadata = data_info["metadata"]
    n_frames = int(metadata["n_frames"])  # type: ignore[index]
    height = int(metadata["height"])  # type: ignore[index]
    width = int(metadata["width"])  # type: ignore[index]
    pc_channel_idx = int(data_info["pc_channel"])  # type: ignore[index]
    fl_channel_idx = data_info.get("fl_channel")
    base_name = str(data_info["filename"]).replace(".nd2", "")  # type: ignore[index]

    fov_dir = output_dir / f"fov_{fov_index:04d}"
    fov_dir.mkdir(parents=True, exist_ok=True)

    pc_path = fov_dir / f"{base_name}_fov{fov_index:04d}_phase_contrast_raw.npy"
    fl_path = (
        fov_dir / f"{base_name}_fov{fov_index:04d}_fluorescence_raw.npy"
        if fl_channel_idx is not None
        else None
    )

    pc_memmap = open_memmap(pc_path, mode="w+", dtype=np.uint16, shape=(n_frames, height, width))
    fl_memmap = None
    if fl_path is not None:
        fl_memmap = open_memmap(fl_path, mode="w+", dtype=np.uint16, shape=(n_frames, height, width))

    xarr = create_nd2_xarray(nd2_path)

    for frame_idx in range(n_frames):
        pc_frame = get_nd2_frame(xarr, fov_index, pc_channel_idx, frame_idx)
        pc_memmap[frame_idx] = _convert_to_uint16(pc_frame)

        if fl_memmap is not None and fl_channel_idx is not None:
            fl_frame = get_nd2_frame(xarr, fov_index, int(fl_channel_idx), frame_idx)
            fl_memmap[frame_idx] = _convert_to_uint16(fl_frame)

        if progress_callback is not None:
            progress_callback(frame_idx, n_frames, "Copying")

    del pc_memmap
    if fl_memmap is not None:
        del fl_memmap

    outputs: dict[str, Path] = {"phase_contrast_raw": pc_path}
    if fl_path is not None:
        outputs["fluorescence_raw"] = fl_path

    if progress_callback is not None and n_frames > 0:
        progress_callback(n_frames - 1, n_frames, "Copy complete")

    return outputs


