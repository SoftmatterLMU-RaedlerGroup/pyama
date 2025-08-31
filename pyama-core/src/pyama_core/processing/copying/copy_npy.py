"""
Utility for copying channels from ND2 files into NPY files with progress reporting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from numpy.lib.format import open_memmap

from pyama_core.io.nd2_loader import get_nd2_frame, load_nd2


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

    # Prefer deriving dimensions directly from the ND2 xarray
    # to reduce reliance on precomputed metadata.
    # Use the unified loader to get the xarray view
    da, _ = load_nd2(nd2_path)
    sizes = getattr(da, "sizes", {})
    n_frames = int(sizes.get("T", 1))
    height = int(sizes.get("Y", 0))
    width = int(sizes.get("X", 0))

    # Defensive fallback if sizes are unavailable
    if height == 0 or width == 0:
        # Attempt to compute a single frame to inspect shape
        test = (
            da.isel(**{k: 0 for k in da.dims if k in ("T", "P", "C", "Z")})
            .compute()
            .values
        )
        if test.ndim >= 2:
            height, width = int(test.shape[-2]), int(test.shape[-1])

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

    pc_memmap = open_memmap(
        pc_path, mode="w+", dtype=np.uint16, shape=(n_frames, height, width)
    )
    fl_memmap = None
    if fl_path is not None:
        fl_memmap = open_memmap(
            fl_path, mode="w+", dtype=np.uint16, shape=(n_frames, height, width)
        )

    for frame_idx in range(n_frames):
        pc_frame = get_nd2_frame(da, fov_index, pc_channel_idx, frame_idx)
        pc_memmap[frame_idx] = _convert_to_uint16(pc_frame)

        if fl_memmap is not None and fl_channel_idx is not None:
            fl_frame = get_nd2_frame(da, fov_index, int(fl_channel_idx), frame_idx)
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
