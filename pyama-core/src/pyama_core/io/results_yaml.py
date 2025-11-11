"""
Processing results YAML management - discovery, loading, and writing utilities.
"""

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from pyama_core.io.types import ProcessingResults
from pyama_core.processing.types import (
    ChannelSelection,
    Channels,
    ProcessingContext,
    ensure_results_entry,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PUBLIC API - LOADING FUNCTIONS
# =============================================================================


def load_processing_results_yaml(file_path: Path) -> ProcessingResults:
    """Load processing results from YAML file with path correction."""
    if not file_path.exists():
        return ProcessingResults(
            project_path=file_path.parent,
            n_fov=0,
            fov_data={},
            channels=Channels().to_raw(),
            time_units=None,
        )

    # Load and parse YAML file
    output_dir = file_path.parent
    try:
        with open(file_path, "r") as f:
            yaml_data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Failed to load YAML file {file_path}: {e}")

    results_section = yaml_data.get("results")
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
                if file_info is None:
                    continue
                path = Path(file_info)
                corrected_path = _correct_file_path(path, output_dir)
                if corrected_path and corrected_path.exists():
                    # Always store the original path from YAML
                    data_files["traces"] = corrected_path
                continue

            # Handle NPY files - they can be single or multi-channel
            if isinstance(file_info, list) and len(file_info) >= 1:
                if isinstance(file_info[0], list):
                    # Multi-channel format: [[channel, path], [channel, path], ...]
                    # This handles both single-item [[channel, path]] and multi-item cases
                    for channel_info in file_info:
                        if len(channel_info) >= 2 and channel_info[1] is not None:
                            channel, file_path = (
                                channel_info[0],
                                Path(channel_info[1]),
                            )
                            corrected_path = _correct_file_path(file_path, output_dir)
                            if corrected_path and corrected_path.exists():
                                full_key = f"{data_type}_ch_{channel}"
                                data_files[full_key] = corrected_path
                elif len(file_info) >= 2 and file_info[1] is not None:
                    # Single channel format: [channel, path]
                    channel, file_path = file_info[0], Path(file_info[1])
                    corrected_path = _correct_file_path(file_path, output_dir)
                    if corrected_path and corrected_path.exists():
                        full_key = f"{data_type}_ch_{channel}"
                        data_files[full_key] = corrected_path

        fov_data[fov_id] = data_files

    channels_block = yaml_data.get("channels")
    if channels_block is None:
        channels_block = {}
    try:
        channels_serialized = Channels.from_serialized(channels_block).to_raw()
    except ValueError as exc:
        raise ValueError(
            "Invalid 'channels' section in processing_results.yaml"
        ) from exc

    return ProcessingResults(
        project_path=output_dir,
        n_fov=len(fov_data),
        fov_data=fov_data,
        channels=channels_serialized,
        time_units=yaml_data.get("time_units"),
        extra={
            k: v
            for k, v in yaml_data.items()
            if k not in {"results", "channels", "time_units"}
        },
    )


# =============================================================================
# PUBLIC API - QUERY FUNCTIONS
# =============================================================================


def get_channels_from_yaml(processing_results: ProcessingResults) -> list[int]:
    """Get list of fluorescence channels from processing results."""
    channels_info = processing_results["channels"]
    if channels_info is None:
        return []
    if not isinstance(channels_info, Mapping):
        raise ValueError("Processing results 'channels' section must be a mapping")
    return Channels.from_serialized(channels_info).get_fl_channels()


def get_time_units_from_yaml(processing_results: ProcessingResults) -> str | None:
    """Get time units from processing results."""
    return processing_results["time_units"]


def get_trace_csv_path_from_yaml(
    processing_results: ProcessingResults, fov: int
) -> Path | None:
    """Get trace CSV path for specific FOV from processing results.

    Returns the original trace CSV path from YAML (one per FOV) containing all channels.
    Does NOT check for inspected files - use trace_paths.resolve_trace_path() for that.

    Args:
        processing_results: Processing results object
        fov: FOV ID

    Returns:
        Path to trace CSV file, or None if not found
    """
    fov_data = processing_results["fov_data"].get(fov, {})

    # Unified schema: one traces CSV per FOV
    if "traces" in fov_data:
        return fov_data["traces"]

    return None


# =============================================================================
# PUBLIC API - SERIALIZATION FUNCTIONS
# =============================================================================


def serialize_processing_results(
    context: Any,
    time_units: str = "min",
) -> dict[str, Any]:
    """Serialize processing context to a YAML-safe dictionary.

    This function converts a ProcessingContext (or dict-like object) into a
    dictionary that can be safely written to YAML. The caller is responsible
    for merging with existing results if needed before calling this function.

    Args:
        context: ProcessingContext to serialize (should already be merged if needed)
        time_units: Time units string to include (default: "min")

    Returns:
        Dictionary ready for YAML serialization

    Raises:
        ValueError: If context cannot be serialized
    """
    # Ensure time_units is set on context (create a copy to avoid modifying original)
    # Set time_units if context is a ProcessingContext
    if isinstance(context, ProcessingContext):
        context.time_units = time_units
    elif hasattr(context, "time_units"):
        context.time_units = time_units
    else:
        # For dict-like contexts, create a copy with time_units
        context_dict = dict(context) if isinstance(context, dict) else context
        if isinstance(context_dict, dict):
            context_dict = dict(context_dict)
            context_dict["time_units"] = time_units
            context = context_dict

    # Serialize context for YAML using recursive helper
    def _serialize_for_yaml(obj: Any) -> Any:
        """Convert context to a YAML-friendly representation.

        - pathlib.Path -> str
        - set -> list (sorted for determinism)
        - tuple -> list
        - dict/list: recurse
        - dataclasses: convert to dict
        """
        try:
            if isinstance(obj, ChannelSelection):
                return obj.to_payload()
            if isinstance(obj, Channels):
                return obj.to_raw()
            # Handle dataclasses
            if hasattr(obj, "__dataclass_fields__"):
                result = {}
                for field_name in obj.__dataclass_fields__:
                    field_value = getattr(obj, field_name)
                    result[field_name] = _serialize_for_yaml(field_value)
                return result
            if isinstance(obj, Path):
                return str(obj)
            if isinstance(obj, dict):
                return {str(k): _serialize_for_yaml(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_serialize_for_yaml(v) for v in obj]
            if isinstance(obj, set):
                return [
                    _serialize_for_yaml(v)
                    for v in sorted(list(obj), key=lambda x: str(x))
                ]
            return obj
        except Exception:
            # Fallback to string if anything goes wrong
            try:
                return str(obj)
            except Exception:
                return None

    return _serialize_for_yaml(context)


def save_processing_results_yaml(
    context: Any,
    output_dir: Path,
    time_units: str = "min",
) -> None:
    """Save processing context to processing_results.yaml file.

    This function provides a unified API for saving processing results YAML files.
    It handles serialization and file writing. The caller is responsible for
    merging with existing results if needed.

    Args:
        context: ProcessingContext to serialize (should already be merged if needed)
        output_dir: Directory where processing_results.yaml will be written
        time_units: Time units string to include (default: "min")

    Raises:
        OSError: If the file cannot be written
        ValueError: If context cannot be serialized
    """
    yaml_path = output_dir / "processing_results.yaml"

    # Serialize context to YAML-safe dict
    safe_context = serialize_processing_results(context, time_units)

    try:
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                safe_context,
                f,
                sort_keys=False,
                default_flow_style=False,
                allow_unicode=True,
            )
        logger.info(f"Wrote processing results to {yaml_path}")
    except Exception as e:
        logger.warning(f"Failed to write processing_results.yaml: {e}")
        raise


def deserialize_from_dict(data: dict) -> Any:
    """Convert a dict back to a ProcessingContext object.

    Args:
        data: Dictionary loaded from YAML

    Returns:
        ProcessingContext object
    """
    context = ProcessingContext()

    if not isinstance(data, dict):
        return context

    context.output_dir = (
        Path(data.get("output_dir")) if data.get("output_dir") else None
    )

    channels_data = data.get("channels")
    if channels_data is None:
        context.channels = Channels()
    elif isinstance(channels_data, Mapping):
        context.channels = Channels.from_serialized(channels_data)
    else:
        raise ValueError("Invalid 'channels' section when deserializing context")

    results_block = data.get("results")
    if results_block:
        context.results = {}
        for fov_str, fov_data in results_block.items():
            fov = int(fov_str)
            fov_entry = ensure_results_entry()

            if fov_data.get("pc"):
                pc_data = fov_data["pc"]
                if isinstance(pc_data, (list, tuple)) and len(pc_data) == 2:
                    fov_entry.pc = (int(pc_data[0]), Path(pc_data[1]))

            if fov_data.get("fl"):
                for fl_item in fov_data["fl"]:
                    if isinstance(fl_item, (list, tuple)) and len(fl_item) == 2:
                        fov_entry.fl.append((int(fl_item[0]), Path(fl_item[1])))

            if fov_data.get("seg"):
                seg_data = fov_data["seg"]
                if isinstance(seg_data, (list, tuple)) and len(seg_data) == 2:
                    fov_entry.seg = (int(seg_data[0]), Path(seg_data[1]))

            if fov_data.get("seg_labeled"):
                seg_labeled_data = fov_data["seg_labeled"]
                if (
                    isinstance(seg_labeled_data, (list, tuple))
                    and len(seg_labeled_data) == 2
                ):
                    fov_entry.seg_labeled = (
                        int(seg_labeled_data[0]),
                        Path(seg_labeled_data[1]),
                    )

            bg_data = fov_data.get("fl_background")
            if bg_data:
                for fl_bg_item in bg_data:
                    if isinstance(fl_bg_item, (list, tuple)) and len(fl_bg_item) == 2:
                        fov_entry.fl_background.append(
                            (int(fl_bg_item[0]), Path(fl_bg_item[1]))
                        )

            traces_value = fov_data.get("traces")
            if isinstance(traces_value, (str, Path)):
                fov_entry.traces = Path(traces_value)

            context.results[fov] = fov_entry

    context.params = data.get("params", {})
    context.time_units = data.get("time_units")

    return context


# =============================================================================
# PRIVATE HELPER FUNCTIONS
# =============================================================================


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
