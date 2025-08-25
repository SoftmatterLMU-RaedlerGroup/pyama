"""
ND2 file loading utilities for microscopy data.
"""

import numpy as np
from pathlib import Path
from typing_extensions import TypedDict
import nd2
import xarray as xr


class ND2Metadata(TypedDict):
    filepath: str
    filename: str
    n_frames: int
    height: int
    width: int
    n_fov: int
    channels: list[str]
    n_channels: int
    pixel_microns: float
    native_dtype: str


def create_nd2_xarray(nd2_path: str | Path) -> xr.DataArray:
    return nd2.imread(str(nd2_path), xarray=True, dask=True)


def get_nd2_frame(
    xarr: xr.DataArray, fov: int, channel: int, frame: int
) -> np.ndarray:
    selection = {}
    if "T" in xarr.dims:
        selection["T"] = frame
    if "P" in xarr.dims:
        selection["P"] = fov
    if "C" in xarr.dims:
        selection["C"] = channel
    if "Z" in xarr.dims:
        selection["Z"] = 0
    return xarr.isel(**selection).compute().values


def load_nd2_metadata(nd2_path: str | Path) -> ND2Metadata:
    try:
        nd2_path = Path(nd2_path)
        with nd2.ND2File(str(nd2_path)) as f:
            metadata: ND2Metadata = {
                "filepath": str(nd2_path),
                "filename": nd2_path.name,
                "n_frames": f.sizes.get("T", 1),
                "height": f.sizes.get("Y", 0),
                "width": f.sizes.get("X", 0),
                "n_fov": f.sizes.get("P", 1),
                "channels": [ch.channel.name for ch in (f.metadata.channels or [])],
                "n_channels": f.sizes.get("C", 1),
                "pixel_microns": f.voxel_size().x if f.voxel_size() else 1.0,
                "native_dtype": str(f.dtype),
            }
            return metadata
    except Exception as e:
        raise RuntimeError(f"Failed to load ND2 metadata: {str(e)}")


