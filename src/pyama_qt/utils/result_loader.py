"""
Processing results discovery and loading utilities.
"""

from pathlib import Path
from typing_extensions import TypedDict

from pyama_qt.utils.logging_config import get_logger


class ProcessingResults(TypedDict, total=False):
    """Type definition for processing results structure"""

    # Metadata
    project_path: Path
    nd2_file: str
    n_fov: int

    # Data paths by FOV
    fov_data: dict[int, dict[str, Path]]  # {fov_idx: {data_type: path}}


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
