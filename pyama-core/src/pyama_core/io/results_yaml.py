"""
Processing results YAML management - discovery, loading, and writing utilities.
"""

from pathlib import Path
from typing import TypedDict, Dict, Any, List, Tuple
import yaml


class ProcessingResults(TypedDict, total=False):
    project_path: Path
    microscopy_file: str
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

    if "results_paths" not in yaml_data:
        raise ValueError("YAML file missing 'results_paths' section")

    results_paths = yaml_data["results_paths"]

    fov_data: dict[int, dict[str, Path]] = {}

    for fov_str, fov_files in results_paths.items():
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

    # Extract microscopy filename from YAML or file paths
    microscopy_file = ""
    if "microscopy_file" in yaml_data:
        microscopy_file = yaml_data["microscopy_file"]
    elif fov_data:
        # Extract from first file path
        first_fov_files = list(fov_data.values())[0]
        for file_path in first_fov_files.values():
            parts = file_path.stem.split("_fov")
            if len(parts) > 0:
                # Try to determine file extension from original file or default to common formats
                microscopy_file = parts[0]
                # Add appropriate extension - could be .nd2, .czi, etc.
                if not any(microscopy_file.endswith(ext) for ext in ['.nd2', '.czi']):
                    microscopy_file += ".nd2"  # Default to .nd2 for backward compatibility
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
        microscopy_file=microscopy_file,
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

    microscopy_file = ""
    if fov_data:
        first_fov_files = list(fov_data.values())[0]
        for file_path in first_fov_files.values():
            parts = file_path.stem.split("_fov")
            if len(parts) > 0:
                # Try to determine file extension from original file or default to common formats
                microscopy_file = parts[0]
                # Add appropriate extension - could be .nd2, .czi, etc.
                if not any(microscopy_file.endswith(ext) for ext in ['.nd2', '.czi']):
                    microscopy_file += ".nd2"  # Default to .nd2 for backward compatibility
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
        microscopy_file=microscopy_file,
        n_fov=len(fov_data),
        fov_data=fov_data,
        has_project_file=has_project_file,
        processing_status=processing_status,
    )


# Additional YAML management functions

def load_processing_results_yaml(yaml_path: Path) -> Dict[str, Any]:
    """Load raw YAML data from processing results file."""
    if not yaml_path.exists():
        return {}

    try:
        with yaml_path.open('r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise ValueError(f"Failed to load YAML file {yaml_path}: {e}")


def save_processing_results_yaml(yaml_path: Path, data: Dict[str, Any]) -> None:
    """Save data to processing results YAML file."""
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with yaml_path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, sort_keys=False)


def get_channels_from_yaml(yaml_data: Dict[str, Any]) -> List[int]:
    """Get list of fluorescence channels from YAML data."""
    channels_data = yaml_data.get("channels", {})
    return channels_data.get("fl", [])


def get_time_units_from_yaml(yaml_data: Dict[str, Any]) -> str | None:
    """Get time units from YAML data."""
    return yaml_data.get("time_units")


def get_microscopy_file_from_yaml(yaml_data: Dict[str, Any]) -> str | None:
    """Get original microscopy filename from YAML data."""
    return yaml_data.get("microscopy_file")


def get_trace_csv_path_from_yaml(yaml_data: Dict[str, Any], fov: int, channel: int) -> Path | None:
    """Get trace CSV path for specific FOV and channel from YAML data."""
    results_data = yaml_data.get("results_paths", {})
    fov_data = results_data.get(str(fov), {})
    traces_csv_list = fov_data.get("traces_csv", [])

    for entry in traces_csv_list:
        if len(entry) >= 2 and entry[0] == channel:
            return Path(entry[1])

    return None


def get_all_trace_csv_paths_from_yaml(yaml_data: Dict[str, Any]) -> Dict[Tuple[int, int], Path]:
    """Get all trace CSV paths as {(fov, channel): path} mapping from YAML data."""
    paths = {}
    results_data = yaml_data.get("results_paths", {})

    for fov_str, fov_data in results_data.items():
        try:
            fov = int(fov_str)
        except ValueError:
            continue

        traces_csv_list = fov_data.get("traces_csv", [])
        for entry in traces_csv_list:
            if len(entry) >= 2:
                channel, path_str = entry[0], entry[1]
                paths[(fov, channel)] = Path(path_str)

    return paths


def set_trace_csv_path_in_yaml(yaml_data: Dict[str, Any], fov: int, channel: int, path: Path) -> Dict[str, Any]:
    """Return new YAML data with updated trace CSV path for specific FOV and channel."""
    # Make a deep copy to avoid mutating the original
    new_data = yaml.safe_load(yaml.safe_dump(yaml_data))

    results_data = new_data.setdefault("results_paths", {})
    fov_data = results_data.setdefault(str(fov), {})
    traces_csv_list = fov_data.setdefault("traces_csv", [])

    # Find existing entry for this channel and update it
    for i, entry in enumerate(traces_csv_list):
        if len(entry) >= 2 and entry[0] == channel:
            traces_csv_list[i] = [channel, str(path)]
            return new_data

    # Add new entry if not found
    traces_csv_list.append([channel, str(path)])
    return new_data


def get_all_fovs_from_yaml(yaml_data: Dict[str, Any]) -> List[int]:
    """Get list of all FOVs from YAML data."""
    results_data = yaml_data.get("results_paths", {})

    fovs = []
    for fov_str in results_data.keys():
        try:
            fovs.append(int(fov_str))
        except ValueError:
            continue

    return sorted(fovs)