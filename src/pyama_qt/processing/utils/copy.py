"""
Utility for copying channels from ND2 files into NPY files with progress reporting.

This module encapsulates the core copy logic so services can delegate the heavy
lifting and focus on orchestration, cancellation, and UI updates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from pyama_qt.utils.nd2_loader import get_nd2_frame, create_nd2_xarray
from numpy.lib.format import open_memmap


def _convert_to_uint16(frame: np.ndarray) -> np.ndarray:
    """Convert input frame to uint16.

    - If input is uint8, scale to full 16-bit range by multiplying by 257
    - If input is uint16 or int16, cast to uint16
    - Otherwise, perform a direct conversion which may lose precision
    """
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
    """Copy phase contrast and optional fluorescence channels from an ND2 file to NPY files.

    Args:
        nd2_path: Path to the ND2 file.
        fov_index: Field of view index to extract.
        data_info: Dictionary with required keys: 'metadata', 'pc_channel', optional 'fl_channel', 'filename'.
        output_dir: Root output directory; function creates an FOV subdirectory inside it.
        progress_callback: Optional callable(frame_idx, n_frames, message) to report progress.

    Returns:
        Mapping of output type to created file path. Keys include 'phase_contrast_raw' and optionally 'fluorescence_raw'.
    """
    metadata = data_info["metadata"]
    n_frames = int(metadata["n_frames"])  # type: ignore[index]
    height = int(metadata["height"])  # type: ignore[index]
    width = int(metadata["width"])  # type: ignore[index]
    pc_channel_idx = int(data_info["pc_channel"])  # type: ignore[index]
    fl_channel_idx = data_info.get("fl_channel")
    base_name = str(data_info["filename"]).replace(".nd2", "")  # type: ignore[index]

    # Prepare output directory
    fov_dir = output_dir / f"fov_{fov_index:04d}"
    fov_dir.mkdir(parents=True, exist_ok=True)

    # Output file paths
    pc_path = fov_dir / f"{base_name}_fov{fov_index:04d}_phase_contrast_raw.npy"
    fl_path = (
        fov_dir / f"{base_name}_fov{fov_index:04d}_fluorescence_raw.npy"
        if fl_channel_idx is not None
        else None
    )

    # Create memory-mapped arrays for efficient writing
    pc_memmap = open_memmap(
        pc_path, mode="w+", dtype=np.uint16, shape=(n_frames, height, width)
    )

    fl_memmap = None
    if fl_path is not None:
        fl_memmap = open_memmap(
            fl_path, mode="w+", dtype=np.uint16, shape=(n_frames, height, width)
        )

    # Create xarray once for efficient frame access
    xarr = create_nd2_xarray(nd2_path)
    
    # Read frames from ND2 and write to memmaps
    for frame_idx in range(n_frames):
        # Read phase contrast frame
        pc_frame = get_nd2_frame(xarr, fov_index, pc_channel_idx, frame_idx)
        pc_memmap[frame_idx] = _convert_to_uint16(pc_frame)

        # Read fluorescence frame if requested
        if fl_memmap is not None and fl_channel_idx is not None:
            fl_frame = get_nd2_frame(
                xarr, fov_index, int(fl_channel_idx), frame_idx
            )
            fl_memmap[frame_idx] = _convert_to_uint16(fl_frame)

        # Progress callback
        if progress_callback is not None:
            progress_callback(frame_idx, n_frames, "Copying")

    # Ensure data is flushed to disk and files are closed
    del pc_memmap
    if fl_memmap is not None:
        del fl_memmap

    outputs: dict[str, Path] = {"phase_contrast_raw": pc_path}
    if fl_path is not None:
        outputs["fluorescence_raw"] = fl_path

    # Final progress update (optional)
    if progress_callback is not None and n_frames > 0:
        progress_callback(n_frames - 1, n_frames, "Copy complete")

    return outputs
