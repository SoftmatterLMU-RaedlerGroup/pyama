"""
Processing results discovery and loading utilities.
"""

from pathlib import Path
from typing_extensions import TypedDict
import yaml


class ProcessingResults(TypedDict, total=False):
    project_path: Path
    nd2_file: str
    n_fov: int
    fov_data: dict[int, dict[str, Path]]
    has_project_file: bool
    processing_status: str


def _correct_file_path(yaml_path: Path, current_output_dir: Path) -> Path | None:
    """
    Correct file paths from YAML to work with the current directory structure.

    The YAML file contains absolute paths that may be invalid if the data folder
    has been moved. This function reconstructs the correct path based on:
    1. The current output directory (where the user is loading from)
    2. The relative structure from the YAML path

    Args:
        yaml_path: Original path from YAML file
        current_output_dir: Current directory where user is loading from

    Returns:
        Corrected path that should exist in the current structure, or None if invalid
    """
    try:
        # If the original path exists, use it
        if yaml_path.exists():
            return yaml_path

        # Extract the relative part of the path (FOV folder and filename)
        # Example: /old/path/data/fov_000/file.npy -> fov_000/file.npy
        path_parts = yaml_path.parts

        # Find the FOV directory in the path
        fov_dir_idx = None
        for i, part in enumerate(path_parts):
            if part.startswith("fov_"):
                fov_dir_idx = i
                break

        if fov_dir_idx is None:
            # No FOV directory found, just use the filename in current dir
            return current_output_dir / yaml_path.name

        # Reconstruct path from FOV directory onwards
        relative_parts = path_parts[fov_dir_idx:]
        corrected_path = current_output_dir
        for part in relative_parts:
            corrected_path = corrected_path / part

        return corrected_path

    except Exception:
        # Fallback: just use filename in current directory
        return current_output_dir / yaml_path.name


def discover_processing_results(output_dir: Path) -> ProcessingResults:
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    # Check for project files
    project_files = list(output_dir.glob("*.yaml")) + list(output_dir.glob("*.yml"))
    has_project_file = len(project_files) > 0

    # Try to load from processing_results.yaml if it exists
    yaml_file = output_dir / "processing_results.yaml"
    if yaml_file.exists():
        return _load_from_yaml(yaml_file, output_dir, has_project_file)

    # Fallback to directory-based discovery
    return _discover_from_directories(output_dir, has_project_file)


def _load_from_yaml(yaml_file: Path, output_dir: Path, has_project_file: bool) -> ProcessingResults:
    """Load processing results from YAML file."""
    try:
        with open(yaml_file, 'r') as f:
            yaml_data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Failed to load YAML file {yaml_file}: {e}")

    if "npy_paths" not in yaml_data:
        raise ValueError("YAML file missing 'npy_paths' section")

    fov_data: dict[int, dict[str, Path]] = {}
    npy_paths = yaml_data["npy_paths"]

    for fov_str, fov_files in npy_paths.items():
        fov_idx = int(fov_str)
        data_files: dict[str, Path] = {}

        for data_type, file_info in fov_files.items():
            if data_type == "traces_csv":
                # Handle traces CSV files - pick the first one or inspected version
                if file_info and len(file_info) > 0:
                    # file_info is a list of [channel, path] pairs
                    # For visualization, we'll use the first available traces file
                    yaml_path = Path(file_info[0][1])
                    corrected_path = _correct_file_path(yaml_path, output_dir)
                    if corrected_path and corrected_path.exists():
                        data_files["traces"] = corrected_path
            else:
                # Handle NPY files - they can be single or multi-channel
                if isinstance(file_info, list) and len(file_info) >= 2:
                    if isinstance(file_info[0], list):
                        # Multi-channel format: [[channel, path], [channel, path], ...]
                        for channel_info in file_info:
                            if len(channel_info) >= 2:
                                channel, yaml_file_path = channel_info[0], channel_info[1]
                                yaml_path = Path(yaml_file_path)
                                corrected_path = _correct_file_path(yaml_path, output_dir)
                                if corrected_path and corrected_path.exists():
                                    full_key = f"{data_type}_ch_{channel}"
                                    data_files[full_key] = corrected_path
                    else:
                        # Single channel format: [channel, path]
                        channel, yaml_file_path = file_info[0], file_info[1]
                        yaml_path = Path(yaml_file_path)
                        corrected_path = _correct_file_path(yaml_path, output_dir)
                        if corrected_path and corrected_path.exists():
                            full_key = f"{data_type}_ch_{channel}"
                            data_files[full_key] = corrected_path

        fov_data[fov_idx] = data_files

    # Extract ND2 filename from YAML or file paths
    nd2_file = ""
    if "nd2_file" in yaml_data:
        nd2_file = yaml_data["nd2_file"]
    elif fov_data:
        # Extract from first file path
        first_fov_files = list(fov_data.values())[0]
        for file_path in first_fov_files.values():
            parts = file_path.stem.split("_fov")
            if len(parts) > 0:
                nd2_file = parts[0] + ".nd2"
                break

    # Determine processing status
    processing_status = "unknown"
    if fov_data:
        fovs_with_traces = sum(1 for fov in fov_data.values() if "traces" in fov)
        if fovs_with_traces == len(fov_data):
            processing_status = "completed"
        elif fovs_with_traces > 0:
            processing_status = "partial"
        else:
            processing_status = "in_progress"

    return ProcessingResults(
        project_path=output_dir,
        nd2_file=nd2_file,
        n_fov=len(fov_data),
        fov_data=fov_data,
        has_project_file=has_project_file,
        processing_status=processing_status,
    )


def _discover_from_directories(output_dir: Path, has_project_file: bool) -> ProcessingResults:
    """Fallback directory-based discovery when no YAML file is available."""
    all_dirs = list(output_dir.iterdir())
    fov_dirs = [d for d in all_dirs if d.is_dir() and d.name.startswith("fov_")]
    if not fov_dirs:
        raise ValueError(f"No FOV directories found in {output_dir}")

    fov_data: dict[int, dict[str, Path]] = {}
    for fov_dir in sorted(fov_dirs):
        fov_idx = int(fov_dir.name.split("_")[1])
        data_files: dict[str, Path] = {}

        for npy_file in fov_dir.glob("*.npy"):
            stem = npy_file.stem
            # Extract data type from filename pattern
            fov_pattern = f"_fov_{fov_idx:03d}_"
            if fov_pattern in stem:
                parts = stem.split(fov_pattern)
                if len(parts) >= 2:
                    key = parts[1]
                else:
                    key = stem
            else:
                alt_pattern = f"_fov{fov_idx:03d}_"
                if alt_pattern in stem:
                    parts = stem.split(alt_pattern)
                    if len(parts) >= 2:
                        key = parts[1]
                    else:
                        key = stem
                else:
                    key = stem
            data_files[key] = npy_file

        traces_files = list(fov_dir.glob("*traces*.csv"))
        if traces_files:
            inspected = [f for f in traces_files if "traces_inspected.csv" in f.name]
            if inspected:
                data_files["traces"] = inspected[0]
            else:
                regular = [
                    f
                    for f in traces_files
                    if "traces.csv" in f.name and "inspected" not in f.name
                ]
                if regular:
                    data_files["traces"] = regular[0]

        fov_data[fov_idx] = data_files

    nd2_file = ""
    if fov_data:
        first_fov_files = list(fov_data.values())[0]
        for file_path in first_fov_files.values():
            parts = file_path.stem.split("_fov")
            if len(parts) > 0:
                nd2_file = parts[0] + ".nd2"
                break

    processing_status = "unknown"
    if fov_data:
        fovs_with_traces = sum(1 for fov in fov_data.values() if "traces" in fov)
        if fovs_with_traces == len(fov_data):
            processing_status = "completed"
        elif fovs_with_traces > 0:
            processing_status = "partial"
        else:
            processing_status = "in_progress"

    return ProcessingResults(
        project_path=output_dir,
        nd2_file=nd2_file,
        n_fov=len(fov_data),
        fov_data=fov_data,
        has_project_file=has_project_file,
        processing_status=processing_status,
    )
