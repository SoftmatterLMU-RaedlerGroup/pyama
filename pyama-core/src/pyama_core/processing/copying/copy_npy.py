"""
Utility for copying channels from ND2 files into NPY files with progress reporting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from numpy.lib.format import open_memmap

from pyama_core.io.nd2_loader import get_nd2_frame, create_nd2_xarray


def _convert_to_uint16(frame: np.ndarray) -> np.ndarray:
    if frame.dtype == np.uint8:
        return frame.astype(np.uint16) * 257
    if frame.dtype in (np.uint16, np.int16):
        return frame.astype(np.uint16)
    return frame.astype(np.uint16)


def copy(
    nd2_path: str,
    fov_index: int,
    data_info: dict[str, object],
    output_dir: Path,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict[str, Path]:
    """Copy channels from an ND2 file into NPY memmaps.

    Parameters
    - nd2_path: path to the ND2 file
    - fov_index: field-of-view index to extract
    - data_info: dictionary containing keys `metadata`, `pc_channel`, optional
      `fl_channel`, and `filename` (as provided by discovery code)
    - output_dir: directory where `fov_XXXX` will be created
    - progress_callback: optional callback(frame_index, total_frames, message)

    Returns
    - dict mapping logical output names to Path objects
    """

    metadata = data_info.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("data_info must contain a 'metadata' dict")

    try:
        n_frames = int(metadata["n_frames"])  # type: ignore[index]
        height = int(metadata["height"])  # type: ignore[index]
        width = int(metadata["width"])  # type: ignore[index]
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("metadata must contain integer 'n_frames','height','width'") from exc

    try:
        pc_channel_idx = int(data_info["pc_channel"])  # type: ignore[index]
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("data_info must contain integer 'pc_channel'") from exc

    fl_channel_idx = data_info.get("fl_channel")
    base_name = str(data_info.get("filename", "")).replace(".nd2", "")

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

        # Report progress if a callback was provided. The callback may choose
        # to throttle how often it actually emits events.
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


