"""
Core data loading utilities shared between processing and visualization apps.
"""

import numpy as np
from pathlib import Path
from typing_extensions import TypedDict
import nd2

from pyama_qt.core.logging_config import get_logger


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


class ProcessingResults(TypedDict, total=False):
    """Type definition for processing results structure"""

    # Metadata
    project_path: Path
    nd2_file: str
    n_fov: int

    # Data paths by FOV
    fov_data: dict[int, dict[str, Path]]  # {fov_idx: {data_type: path}}


def get_nd2_frame(
    nd2_path: str | Path, fov: int, channel: int, frame: int
) -> np.ndarray:
    """
    Get a single 2D frame from the ND2 file using lazy loading.

    Args:
        nd2_path: Path to ND2 file
        fov: Field of view index
        channel: Channel index
        frame: Time frame index

    Returns:
        2D numpy array of the requested frame
    """
    # Use xarray with dask for efficient lazy loading
    xarr = nd2.imread(str(nd2_path), xarray=True, dask=True)

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


def discover_processing_results(output_dir: Path) -> ProcessingResults:
    """
    Discover and catalog processing results in an output directory.

    This function looks for processing output files based on naming patterns.

    Args:
        output_dir: Path to processing output directory

    Returns:
        ProcessingResults structure with paths to all data files
    """
    logger = get_logger(__name__)
    logger.info(f"Starting discovery of processing results in: {output_dir}")

    if not output_dir.exists():
        logger.error(f"Output directory not found: {output_dir}")
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    # Find FOV directories
    logger.debug(f"Scanning for FOV directories in: {output_dir}")
    all_dirs = list(output_dir.iterdir())
    logger.debug(f"Found {len(all_dirs)} items in directory")

    # Log all directory names for debugging
    for item in all_dirs:
        if item.is_dir():
            logger.debug(f"  Directory: {item.name}")
        else:
            logger.debug(f"  File: {item.name}")

    fov_dirs = [d for d in all_dirs if d.is_dir() and d.name.startswith("fov_")]
    logger.info(f"Found {len(fov_dirs)} FOV directories")

    if not fov_dirs:
        logger.error(
            f"No FOV directories found in {output_dir}. Expected directories starting with 'fov_'"
        )
        raise ValueError(f"No FOV directories found in {output_dir}")

    # Build catalog of available data
    fov_data = {}

    for fov_dir in sorted(fov_dirs):
        # Extract FOV index from directory name (e.g., fov_0001 -> 1)
        fov_idx = int(fov_dir.name.split("_")[1])
        logger.debug(f"Processing FOV directory: {fov_dir.name} (index: {fov_idx})")

        # Find data files in this FOV directory
        data_files = {}

        # Collect all numpy files
        npy_files = list(fov_dir.glob("*.npy"))
        logger.debug(f"  Found {len(npy_files)} NPY files in {fov_dir.name}")

        for npy_file in npy_files:
            # Extract data type from filename
            # Expected format: basename_fov####_datatype.npy
            stem = npy_file.stem

            # Try to extract the data type after the FOV number
            if f"_fov{fov_idx:04d}_" in stem:
                # Split by the FOV pattern and take what comes after
                parts = stem.split(f"_fov{fov_idx:04d}_")
                if len(parts) > 1:
                    key = parts[1]
                else:
                    # Fallback: use the part before FOV
                    key = stem.split("_fov")[0]
                    if "_" in key:
                        key_parts = key.split("_")
                        key = "_".join(key_parts[1:]) if len(key_parts) > 1 else key
            else:
                # Fallback for non-standard naming
                key = stem.split("_fov")[0]
                if "_" in key:
                    key_parts = key.split("_")
                    key = "_".join(key_parts[1:]) if len(key_parts) > 1 else key

            data_files[key] = npy_file
            logger.debug(f"    Added NPY file: {npy_file.name} as '{key}'")

        # Collect CSV files - prefer inspected traces if available
        traces_files = list(fov_dir.glob("*traces*.csv"))
        logger.debug(f"  Found {len(traces_files)} CSV trace files in {fov_dir.name}")

        if traces_files:
            # Check if there's an inspected version
            inspected = [f for f in traces_files if "traces_inspected.csv" in f.name]
            if inspected:
                data_files["traces"] = inspected[0]
                logger.debug(f"    Added inspected traces: {inspected[0].name}")
            else:
                # Fall back to regular traces file
                regular = [
                    f
                    for f in traces_files
                    if "traces.csv" in f.name and "inspected" not in f.name
                ]
                if regular:
                    data_files["traces"] = regular[0]
                    logger.debug(f"    Added regular traces: {regular[0].name}")

        fov_data[fov_idx] = data_files
        logger.info(f"  FOV {fov_idx}: Found {len(data_files)} data files")

    # Try to find original ND2 file reference
    nd2_file = ""
    if fov_data:
        # Look for ND2 filename in any data file name
        first_fov_files = list(fov_data.values())[0]
        for file_path in first_fov_files.values():
            # Extract base name from filename pattern: basename_fov0000_suffix.ext
            parts = file_path.stem.split("_fov")
            if len(parts) > 0:
                nd2_file = parts[0] + ".nd2"
                break

    result = ProcessingResults(
        project_path=output_dir,
        nd2_file=nd2_file,
        n_fov=len(fov_data),
        fov_data=fov_data,
    )

    logger.info(f"Discovery complete: Found {len(fov_data)} FOVs with data")
    logger.info(f"ND2 file reference: {nd2_file if nd2_file else 'Not found'}")

    return result
