"""
ND2 file loading utilities for microscopy data.
"""

import numpy as np
from pathlib import Path
from typing_extensions import TypedDict
from typing import Optional
import nd2
import xarray as xr


class ND2Metadata(TypedDict):
    """Type definition for essential ND2 metadata"""

    filepath: str  # Full path to ND2 file
    filename: str  # Just the filename
    n_frames: int  # Number of time points
    height: int  # Image height in pixels
    width: int  # Image width in pixels
    n_fov: int  # Number of fields of view
    channels: list[str]  # Channel names
    n_channels: int  # Number of channels
    pixel_microns: float  # Pixel size in microns
    native_dtype: str  # Original data type from ND2


def create_nd2_xarray(nd2_path: str | Path) -> xr.DataArray:
    """
    Create an xarray DataArray for the ND2 file that can be reused.
    
    Args:
        nd2_path: Path to ND2 file
    
    Returns:
        xarray DataArray with lazy loading via dask
    """
    return nd2.imread(str(nd2_path), xarray=True, dask=True)


def get_nd2_frame(
    xarr: xr.DataArray, fov: int, channel: int, frame: int
) -> np.ndarray:
    """
    Get a single 2D frame from a pre-loaded ND2 xarray.

    Args:
        xarr: Pre-loaded xarray DataArray from create_nd2_xarray()
        fov: Field of view index
        channel: Channel index
        frame: Time frame index

    Returns:
        2D numpy array of the requested frame
    """

    # Build selection dict based on available dimensions
    selection = {}

    if "T" in xarr.dims:
        selection["T"] = frame
    if "P" in xarr.dims:
        selection["P"] = fov
    if "C" in xarr.dims:
        selection["C"] = channel
    if "Z" in xarr.dims:
        selection["Z"] = 0  # Default to first Z plane

    # Select the specific frame and compute to numpy
    # This returns a 2D numpy array directly
    return xarr.isel(**selection).compute().values



def load_nd2_metadata(nd2_path: str | Path) -> ND2Metadata:
    """
    Load essential ND2 file metadata for processing and visualization.

    Args:
        nd2_path: Path to ND2 file

    Returns:
        Dictionary containing essential metadata only
    """
    try:
        nd2_path = Path(nd2_path)

        with nd2.ND2File(str(nd2_path)) as f:
            # Get essential metadata only
            metadata: ND2Metadata = {
                "filepath": str(nd2_path),
                "filename": nd2_path.name,
                # Core dimensions
                "n_frames": f.sizes.get("T", 1),
                "height": f.sizes.get("Y", 0),
                "width": f.sizes.get("X", 0),
                "n_fov": f.sizes.get("P", 1),
                # Channel info - extract channel names from Channel objects
                "channels": [ch.channel.name for ch in (f.metadata.channels or [])],
                "n_channels": f.sizes.get("C", 1),
                # Physical units
                "pixel_microns": f.voxel_size().x if f.voxel_size() else 1.0,
                # Data type
                "native_dtype": str(f.dtype),
            }

            return metadata

    except Exception as e:
        raise RuntimeError(f"Failed to load ND2 metadata: {str(e)}")
