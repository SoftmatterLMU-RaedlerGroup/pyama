"""
Lightweight helpers for reading and querying processing_results.yaml files.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

import yaml

from pyama_core.processing.workflow.services.types import (
    Channels,
    channel_selection_from_value,
    get_fl_channels,
    normalize_channels,
)


class ProcessingResults(TypedDict, total=False):
    project_path: str
    n_fov: int
    fov_data: dict[Any, Any]
    channels: dict[str, Any]
    time_units: str | None
    extra: dict[str, Any]


def _load_yaml_file(path: Path) -> ProcessingResults:
    if not path.exists():
        raise FileNotFoundError(f"processing_results.yaml not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("processing_results.yaml must contain a mapping")
    return data


def load_processing_results_yaml(file_path: Path) -> ProcessingResults:
    """Load processing results from an explicit YAML path."""
    return _load_yaml_file(file_path)


def get_channels_from_yaml(processing_results: ProcessingResults) -> list[int]:
    """Extract normalized fluorescence channel IDs from processing results."""
    channels_info = processing_results.get("channels")
    if channels_info is None:
        return []
    if not isinstance(channels_info, Mapping):
        raise ValueError("Processing results 'channels' section must be a mapping")

    channels_model: Channels = {"fl": []}
    pc_selection = channel_selection_from_value(channels_info.get("pc"))
    if pc_selection:
        channels_model["pc"] = pc_selection
    fl_entries = []
    for item in channels_info.get("fl", []):
        selection = channel_selection_from_value(item)
        if selection:
            fl_entries.append(selection)
    channels_model["fl"] = fl_entries
    normalize_channels(channels_model)
    return get_fl_channels(channels_model)


def get_time_units_from_yaml(processing_results: ProcessingResults) -> str | None:
    """Return the stored time units, if any."""
    return processing_results.get("time_units")


def get_trace_csv_path_from_yaml(
    processing_results: ProcessingResults, fov: int
) -> Path | None:
    """Return the traces CSV path recorded for a given FOV."""
    fov_data = processing_results.get("fov_data")
    if not isinstance(fov_data, Mapping):
        return None

    entry = fov_data.get(fov)
    if entry is None:
        entry = fov_data.get(str(fov))
    if not isinstance(entry, Mapping):
        return None

    trace_path = entry.get("traces")
    if not trace_path:
        return None
    return Path(trace_path)
