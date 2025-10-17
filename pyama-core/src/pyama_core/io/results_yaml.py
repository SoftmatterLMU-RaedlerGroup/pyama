"""
Processing results YAML management - discovery, loading, and writing utilities.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


@dataclass(slots=True)
class ProcessingResults(Mapping[str, Any]):
    project_path: Path
    n_fov: int
    fov_data: dict[int, dict[str, Path]]
    channels: dict[str, list[int]]
    time_units: str | None
    extra: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        core = self._core_mapping()
        if key in core:
            return core[key]
        if key in self.extra:
            return self.extra[key]
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        yielded = set()
        for key in self._core_mapping():
            yielded.add(key)
            yield key
        for key in self.extra:
            if key not in yielded:
                yield key

    def __len__(self) -> int:
        return len(set(self._core_mapping()) | set(self.extra))

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> dict[str, Any]:
        combined = dict(self._core_mapping())
        combined.update(self.extra)
        return combined

    def _core_mapping(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "n_fov": self.n_fov,
            "fov_data": self.fov_data,
            "channels": self.channels,
            "time_units": self.time_units,
        }


def discover_processing_results(output_dir: Path) -> ProcessingResults:
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    # Try to load from processing_results.yaml if it exists
    yaml_file = output_dir / "processing_results.yaml"
    if yaml_file.exists():
        return _load_from_yaml(yaml_file, output_dir)

    # Fallback to directory-based discovery
    return _discover_from_directories(output_dir)


def _correct_file_path(file_path: Path, current_output_dir: Path) -> Path | None:
    """
    Correct file paths from YAML to work with the current directory structure.

    The YAML file contains absolute paths that may be invalid if the data folder
    has been moved. This function reconstructs the correct path based on:
    1. The current output directory (where the user is loading from)
    2. The relative structure from the YAML path

    Args:
        file_path: Original path from YAML file
        current_output_dir: Current directory where user is loading from

    Returns:
        Corrected path that should exist in the current structure, or None if invalid
    """
    try:
        # If the original path exists, use it
        if file_path.exists():
            return file_path

        # Extract the relative part of the path (FOV folder and filename)
        path_parts = file_path.parts

        # Use last two parts (FOV directory and filename)
        relative_parts = path_parts[-2:]
        corrected_path = current_output_dir
        for part in relative_parts:
            corrected_path = corrected_path / part

        return corrected_path

    except Exception:
        # Fallback: just use filename in current directory
        return current_output_dir / file_path.name


def _load_from_yaml(yaml_file: Path, output_dir: Path) -> ProcessingResults:
    """Load processing results from YAML file."""
    try:
        with open(yaml_file, "r") as f:
            yaml_data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Failed to load YAML file {yaml_file}: {e}")

    results_section = yaml_data.get("results") or yaml_data.get("results_paths")
    if not yaml_data or results_section is None:
        raise ValueError("YAML file missing 'results' section")

    fov_data: dict[int, dict[str, Path]] = {}

    for fov_str, fov_files in results_section.items():
        try:
            fov_id = int(fov_str)
        except Exception:
            # Skip non-integer keys
            continue

        data_files: dict[str, Path] = {}

        for data_type, file_info in (fov_files or {}).items():
            if data_type == "traces":
                path = Path(file_info)
                corrected_path = _correct_file_path(path, output_dir)
                if corrected_path and corrected_path.exists():
                    inspected_path = corrected_path.with_name(
                        f"{corrected_path.stem}_inspected{corrected_path.suffix}"
                    )
                    data_files["traces"] = (
                        inspected_path if inspected_path.exists() else corrected_path
                    )
                continue

            if data_type == "traces_csv":
                # Handle traces CSV files for multiple channels
                if file_info and isinstance(file_info, list):
                    for channel_info in file_info:
                        if len(channel_info) >= 2:
                            channel, file_path = channel_info[0], Path(channel_info[1])
                            corrected_path = _correct_file_path(file_path, output_dir)
                            if corrected_path and corrected_path.exists():
                                # Check for an inspected version and prefer it
                                inspected_path = corrected_path.with_name(
                                    f"{corrected_path.stem}_inspected{corrected_path.suffix}"
                                )
                                if inspected_path.exists():
                                    data_files[f"traces_ch_{channel}"] = inspected_path
                                else:
                                    data_files[f"traces_ch_{channel}"] = corrected_path
            else:
                # Handle NPY files - they can be single or multi-channel
                if isinstance(file_info, list) and len(file_info) >= 1:
                    if isinstance(file_info[0], list):
                        # Multi-channel format: [[channel, path], [channel, path], ...]
                        # This handles both single-item [[channel, path]] and multi-item cases
                        for channel_info in file_info:
                            if len(channel_info) >= 2:
                                channel, file_path = (
                                    channel_info[0],
                                    Path(channel_info[1]),
                                )
                                corrected_path = _correct_file_path(
                                    file_path, output_dir
                                )
                                if corrected_path and corrected_path.exists():
                                    full_key = f"{data_type}_ch_{channel}"
                                    data_files[full_key] = corrected_path
                    elif len(file_info) >= 2:
                        # Single channel format: [channel, path]
                        channel, file_path = file_info[0], Path(file_info[1])
                        corrected_path = _correct_file_path(file_path, output_dir)
                        if corrected_path and corrected_path.exists():
                            full_key = f"{data_type}_ch_{channel}"
                            data_files[full_key] = corrected_path

        fov_data[fov_id] = data_files

    return ProcessingResults(
        project_path=output_dir,
        n_fov=len(fov_data),
        fov_data=fov_data,
        channels=yaml_data.get("channels", {}),
        time_units=yaml_data.get("time_units"),
        extra={
            k: v
            for k, v in yaml_data.items()
            if k not in {"results", "results_paths", "channels", "time_units"}
        },
    )


def _discover_from_directories(output_dir: Path) -> ProcessingResults:
    """Fallback directory-based discovery when no YAML file is available."""
    all_dirs = list(output_dir.iterdir())
    fov_dirs = [d for d in all_dirs if d.is_dir() and d.name.startswith("fov_")]
    if not fov_dirs:
        raise ValueError(f"No FOV directories found in {output_dir}")

    fov_data: dict[int, dict[str, Path]] = {}
    for fov_dir in sorted(fov_dirs):
        # Expecting directory names like 'fov_000'
        try:
            fov_id = int(fov_dir.name.split("_")[1])
        except Exception:
            # Skip directories that don't follow the pattern
            continue

        data_files: dict[str, Path] = {}

        for npy_file in fov_dir.glob("*.npy"):
            stem = npy_file.stem
            # Extract data type from filename pattern
            fov_pattern = f"_fov_{fov_id:03d}_"
            if fov_pattern in stem:
                parts = stem.split(fov_pattern)
                if len(parts) >= 2:
                    key = parts[1]
                else:
                    key = stem
            else:
                alt_pattern = f"_fov{fov_id:03d}_"
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

        fov_data[fov_id] = data_files

    return ProcessingResults(
        project_path=output_dir,
        n_fov=len(fov_data),
        fov_data=fov_data,
        channels={},  # No channel info available from directory discovery
        time_units=None,  # No time units available from directory discovery
    )


# YAML utility functions used elsewhere in the project


def load_processing_results_yaml(file_path: Path) -> ProcessingResults:
    """Load processing results from YAML file with path correction."""
    if not file_path.exists():
        return ProcessingResults(
            project_path=file_path.parent,
            n_fov=0,
            fov_data={},
            channels={},
            time_units=None,
        )

    return _load_from_yaml(file_path, file_path.parent)


def get_channels_from_yaml(processing_results: ProcessingResults) -> list[int]:
    """Get list of fluorescence channels from processing results."""
    channels_info = processing_results["channels"]
    if "fl" in channels_info and channels_info["fl"]:
        return [int(ch) for ch in channels_info["fl"]]
    if "fl_features" in channels_info and channels_info["fl_features"]:
        return sorted(int(ch) for ch in channels_info["fl_features"].keys())
    return []


def get_time_units_from_yaml(processing_results: ProcessingResults) -> str | None:
    """Get time units from processing results."""
    return processing_results["time_units"]


def get_trace_csv_path_from_yaml(
    processing_results: ProcessingResults, fov: int, channel: int
) -> Path | None:
    """Get trace CSV path for specific FOV and channel from processing results."""
    fov_data = processing_results["fov_data"].get(fov, {})

    # Look for traces file in fov_data
    if "traces" in fov_data:
        return fov_data["traces"]

    # Look for channel-specific traces file
    traces_key = f"traces_ch_{channel}"
    if traces_key in fov_data:
        return fov_data[traces_key]

    return None
