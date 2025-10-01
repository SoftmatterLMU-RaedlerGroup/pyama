"""
Unified microscopy file loading utilities for ND2 and CZI data.
"""

from dataclasses import dataclass
import numpy as np
from pathlib import Path
from bioio import BioImage


@dataclass
class MicroscopyMetadata:
    """Metadata for microscopy files (ND2, CZI, etc.)."""

    file_path: Path
    base_name: str
    file_type: str  # 'nd2', 'czi', etc.
    height: int
    width: int
    n_frames: int
    n_fovs: int
    n_channels: int
    timepoints: list[float]
    channel_names: list[str]
    dtype: str


def load_microscopy_file(
    file_path: Path,
) -> tuple[BioImage, MicroscopyMetadata]:
    """Load a microscopy file (ND2, CZI, etc.) and return the BioImage object and extracted metadata.

    Args:
        file_path: Path to the microscopy file (.nd2, .czi, etc.)

    Returns:
        tuple: (BioImage, MicroscopyMetadata)
        Timepoints are returned in microseconds when available; otherwise a best-effort
        numeric list is provided.
    """
    file_path = Path(file_path)
    file_extension = file_path.suffix.lower()
    base_name = file_path.stem
    file_type = file_extension.lstrip(".")

    try:
        # Use bioio to load the microscopy file
        img = BioImage(str(file_path))

        # Get xarray data with dask backing for lazy loading
        da = img.xarray_dask_data

        # Extract dimensions from bioio
        dims = img.dims
        height = dims.Y if hasattr(dims, "Y") else 0
        width = dims.X if hasattr(dims, "X") else 0
        n_frames = dims.T if hasattr(dims, "T") else 1
        n_fovs = len(img.scenes)  # Use scenes to get FOV count
        n_channels = dims.C if hasattr(dims, "C") else 1

        # Extract channel names from coordinates if available
        ch_coord = da.coords.get("C") if hasattr(da, "coords") else None
        if ch_coord is not None:
            try:
                channel_names = [str(v) for v in ch_coord.values.tolist()]
            except Exception:
                channel_names = [str(v) for v in np.asarray(ch_coord.values).tolist()]
        else:
            channel_names = [f"C{i}" for i in range(n_channels)]

        # Extract timepoints from coordinates if available
        timepoints: list[float] = []
        t_coord = da.coords.get("T") if hasattr(da, "coords") else None
        if t_coord is not None:
            t_values = np.asarray(t_coord.values)
            try:
                timepoints = t_values.astype(float).tolist()
            except Exception:
                timepoints = [float(i) for i in range(n_frames)]
        else:
            timepoints = [float(i) for i in range(n_frames)]

        metadata = MicroscopyMetadata(
            file_path=file_path,
            base_name=base_name,
            file_type=file_type,
            height=height,
            width=width,
            n_frames=n_frames,
            n_fovs=n_fovs,
            n_channels=n_channels,
            timepoints=timepoints,
            channel_names=channel_names,
            dtype=str(da.dtype),
        )
        return img, metadata
    except Exception as e:
        raise RuntimeError(f"Failed to load {file_type.upper()} file: {str(e)}")


def get_microscopy_frame(img: BioImage, f: int, c: int, t: int) -> np.ndarray:
    """Return a frame or slice from a microscopy BioImage.

    Args:
        img: BioImage object.
        f: FOV index.
        c: Channel index.
        t: Time index.

    Returns:
        np.ndarray: The selected frame(s) as a numpy array.
    """
    img.set_scene(f)
    da = img.xarray_dask_data

    indexers = {}
    if "Z" in da.dims:
        indexers["Z"] = 0
    if "C" in da.dims:
        indexers["C"] = c
    if "T" in da.dims:
        indexers["T"] = t
    sub = da.isel(**indexers).compute()
    arr = sub.values

    return arr


def get_microscopy_channel_stack(img: BioImage, f: int, t: int) -> np.ndarray:
    """Return a channel stack (C, H, W) from a microscopy BioImage.

    Args:
        img: BioImage object.
        f: FOV index.
        t: Time index.

    Returns:
        np.ndarray: The channel stack as a numpy array.
    """
    # Get the number of channels from img.dims (not da.dims)
    n_channels = int(img.dims.C) if hasattr(img.dims, "C") else 1

    # Process channels one by one to avoid memory issues
    channel_frames = []
    for c in range(n_channels):
        frame = get_microscopy_frame(img, f, c, t)
        channel_frames.append(frame)

    # Stack all channel frames together
    arr = np.stack(channel_frames, axis=0)

    return arr


def get_microscopy_time_stack(img: BioImage, f: int, c: int) -> np.ndarray:
    """Return a time stack (T, H, W) from a microscopy BioImage.

    Args:
        img: BioImage object.
        f: FOV index.
        c: Channel index.

    Returns:
        np.ndarray: The time stack as a numpy array.
    """
    # Get the number of time points from img.dims (not da.dims)
    n_timepoints = int(img.dims.T) if hasattr(img.dims, "T") else 1

    # Process time points one by one to avoid memory issues
    time_frames = []
    for t in range(n_timepoints):
        frame = get_microscopy_frame(img, f, c, t)
        time_frames.append(frame)

    # Stack all time frames together
    arr = np.stack(time_frames, axis=0)

    return arr
