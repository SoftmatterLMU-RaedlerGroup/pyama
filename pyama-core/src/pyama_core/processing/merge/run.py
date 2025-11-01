"""Merge functionality for combining CSV outputs from PyAMA processing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

from pyama_core.io.processing_csv import get_dataframe
from pyama_core.io.results_yaml import (
    get_time_units_from_yaml,
    get_trace_csv_path_from_yaml,
    load_processing_results_yaml,
)
from pyama_core.processing.extraction.features import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama_core.processing.extraction.run import Result
from pyama_core.processing.workflow.services.types import Channels

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class FeatureMaps:
    """Container for feature values per timepoint and cell."""

    features: dict[str, dict[tuple[float, int], float]]
    times: list[float]
    cells: list[int]


# =============================================================================
# CHANNEL CONFIGURATION
# =============================================================================


def get_channel_feature_config(proc_results: dict) -> list[tuple[int, list[str]]]:
    """Determine the channel/feature selections from processing results."""
    channels_data = proc_results.get("channels")
    if channels_data is None:
        raise ValueError("Processing results missing 'channels' section")

    try:
        channel_config = Channels.from_serialized(channels_data)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"Invalid channel configuration in processing results: {exc}"
        ) from exc

    config: list[tuple[int, list[str]]] = []

    pc_channel = channel_config.get_pc_channel()
    if pc_channel is not None:
        pc_features = channel_config.get_pc_features()
        if not pc_features:
            pc_features = list_phase_features()
        config.append((pc_channel, sorted(set(pc_features))))

    fl_feature_map = channel_config.get_fl_feature_map()
    for channel in sorted(fl_feature_map):
        features = fl_feature_map[channel]
        if not features:
            features = list_fluorescence_features()
        config.append((channel, sorted(set(features))))

    if not config:
        raise ValueError("No channels found in processing results")

    return config


# =============================================================================
# SAMPLE PARSING
# =============================================================================


def parse_fov_range(text: str) -> list[int]:
    """Parse comma-separated FOV ranges (e.g., '0-5, 7, 9-11')."""
    normalized = text.replace(" ", "").strip()
    if not normalized:
        raise ValueError("FOV specification cannot be empty")
    if ";" in normalized:
        raise ValueError("Use commas to separate FOVs; semicolons are not supported")

    fovs: list[int] = []
    parts = [part for part in normalized.split(",") if part]

    for part in parts:
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            if not start_str or not end_str:
                raise ValueError(f"Invalid range '{part}': missing start or end value")
            try:
                start, end = int(start_str), int(end_str)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid range '{part}': values must be integers"
                ) from exc
            if start < 0 or end < 0:
                raise ValueError(f"Invalid range '{part}': negative values not allowed")
            if start > end:
                raise ValueError(f"Invalid range '{part}': start must be <= end")
            fovs.extend(range(start, end + 1))
        else:
            try:
                value = int(part)
            except ValueError as exc:
                raise ValueError(f"Invalid FOV '{part}': must be an integer") from exc
            if value < 0:
                raise ValueError(f"FOV '{part}' must be >= 0")
            fovs.append(value)

    return sorted(set(fovs))


def parse_fovs_field(value: Any) -> list[int]:
    """Normalize a FOV specification originating from YAML."""
    if isinstance(value, list):
        normalized: list[int] = []
        for entry in value:
            try:
                fov = int(entry)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"FOV value '{entry}' is not a valid integer") from exc
            if fov < 0:
                raise ValueError(f"FOV value '{entry}' must be >= 0")
            normalized.append(fov)
        return sorted(set(normalized))
    if isinstance(value, str):
        return parse_fov_range(value)
    raise ValueError(
        "FOV specification must be a list of integers or a comma-separated string"
    )


def read_samples_yaml(path: Path) -> dict[str, Any]:
    """Load a samples YAML specification."""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Samples YAML must contain a mapping at the top level")
    samples = data.get("samples")
    if not isinstance(samples, list):
        raise ValueError("Samples YAML must include a 'samples' list")
    return data


# =============================================================================
# FEATURE PROCESSING
# =============================================================================


def build_feature_maps(rows: list[dict], feature_names: list[str]) -> FeatureMaps:
    """Build feature maps filtered by 'good' rows."""
    feature_maps: dict[str, dict[tuple[float, int], float]] = {
        feature_name: {} for feature_name in feature_names
    }
    times_set: set[float] = set()
    cells_set: set[int] = set()

    for row in rows:
        if "good" in row and not row["good"]:
            continue
        time = row.get("time")
        cell = row.get("cell")
        if time is None or cell is None:
            continue

        key = (float(time), int(cell))
        times_set.add(float(time))
        cells_set.add(int(cell))

        for feature_name in feature_names:
            if feature_name in row:
                value = row[feature_name]
                if value is not None:
                    feature_maps[feature_name][key] = float(value)

    return FeatureMaps(
        features=feature_maps,
        times=sorted(times_set),
        cells=sorted(cells_set),
    )


def extract_channel_dataframe(
    df: pd.DataFrame, channel: int, configured_features: list[str]
) -> pd.DataFrame:
    """Return a dataframe containing only configured features for a single channel.
    
    Args:
        df: Unified trace DataFrame with channel-suffixed columns
        channel: Channel ID to extract
        configured_features: List of feature names configured for this channel
        
    Returns:
        DataFrame with base columns and only the configured features for this channel
    """
    suffix = f"_ch_{channel}"
    base_fields = ["fov"] + [field.name for field in dataclass_fields(Result)]
    base_cols = [col for col in base_fields if col in df.columns]
    
    # Only extract features that are configured for this channel
    feature_cols = []
    rename_map = {}
    for feature_name in configured_features:
        feature_col = f"{feature_name}{suffix}"
        if feature_col in df.columns:
            feature_cols.append(feature_col)
            rename_map[feature_col] = feature_name

    selected_cols = base_cols + feature_cols
    if not selected_cols:
        return pd.DataFrame()

    channel_df = df[selected_cols].copy()
    if rename_map:
        channel_df.rename(columns=rename_map, inplace=True)
    return channel_df


def get_all_times(
    feature_maps_by_fov: dict[int, FeatureMaps], fovs: Iterable[int]
) -> list[float]:
    """Collect sorted unique time points across FOVs."""
    times: set[float] = set()
    for fov in fovs:
        feature_maps = feature_maps_by_fov.get(fov)
        if feature_maps:
            times.update(feature_maps.times)
    return sorted(times)


def write_feature_csv(
    out_path: Path,
    times: list[float],
    fovs: Iterable[int],
    feature_name: str,
    feature_maps_by_fov: dict[int, FeatureMaps],
    channel: int,
    time_units: str | None = None,
) -> None:
    """Write a feature CSV mirroring the Qt merge output.

    Only includes FOVs that have data available. Missing FOVs are skipped
    to avoid NaN columns in the output.
    """
    all_cells: set[int] = set()
    fov_list = list(fovs)

    # Filter to only include FOVs that have data
    available_fovs = [fov for fov in fov_list if fov in feature_maps_by_fov]

    for fov in available_fovs:
        feature_maps = feature_maps_by_fov.get(fov)
        if feature_maps:
            all_cells.update(feature_maps.cells)

    sorted_cells = sorted(all_cells)
    columns = ["time"]
    for fov in available_fovs:
        for cell in sorted_cells:
            columns.append(f"fov_{fov:03d}_cell_{cell}")

    rows = []
    for time in times:
        row = [time]
        for fov in available_fovs:
            feature_maps = feature_maps_by_fov.get(fov)
            for cell in sorted_cells:
                value = None
                if feature_maps and feature_name in feature_maps.features:
                    value = feature_maps.features[feature_name].get((time, cell))
                row.append(value)
        rows.append(row)

    df = pd.DataFrame(rows, columns=columns)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if time_units:
        with out_path.open("w", encoding="utf-8") as handle:
            handle.write(f"# Time units: {time_units}\n")
            df.to_csv(handle, index=False, float_format="%.6f")
    else:
        df.to_csv(out_path, index=False, float_format="%.6f")


# =============================================================================
# MAIN MERGE FUNCTION
# =============================================================================


def run_merge(
    sample_yaml: Path,
    processing_results: Path,
    output_dir: Path,
) -> str:
    """Execute merge logic - return success message or raise error."""
    config = read_samples_yaml(sample_yaml)
    samples = config["samples"]

    proc_results = load_processing_results_yaml(processing_results)
    channel_feature_config = get_channel_feature_config(proc_results)
    time_units = get_time_units_from_yaml(proc_results)

    # Use processing results directory as input directory
    input_dir = processing_results.parent

    all_fovs: set[int] = set()
    for sample in samples:
        fovs = parse_fovs_field(sample.get("fovs", []))
        all_fovs.update(fovs)

    feature_maps_by_fov_channel: dict[tuple[int, int], FeatureMaps] = {}
    traces_cache: dict[Path, pd.DataFrame] = {}

    # Load trace CSVs per FOV (unified schema: one CSV per FOV, not per channel)
    for fov in sorted(all_fovs):
        # Get the unified trace CSV for this FOV
        csv_entry = get_trace_csv_path_from_yaml(proc_results, fov)
        
        if csv_entry is None:
            logger.debug(
                "No trace CSV entry found for FOV %s", fov
            )
            continue

        csv_path = Path(csv_entry)
        if not csv_path.is_absolute():
            csv_path = input_dir / csv_path
        if not csv_path.exists():
            logger.warning("Trace CSV file does not exist: %s", csv_path)
            continue

        # Load the unified CSV once per FOV
        if csv_path not in traces_cache:
            try:
                traces_cache[csv_path] = get_dataframe(csv_path)
            except Exception as exc:
                logger.warning("Failed to read %s: %s", csv_path, exc)
                continue

        # Extract channel-specific data from the unified CSV using configured features
        for channel, features in channel_feature_config:
            channel_df = extract_channel_dataframe(
                traces_cache[csv_path], channel, features
            )
            if channel_df.empty:
                logger.debug(
                    "Trace CSV %s contains no data for channel %s", csv_path, channel
                )
                continue

            rows = channel_df.to_dict("records")
            feature_maps_by_fov_channel[(fov, channel)] = build_feature_maps(
                rows, features
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    created_files: list[Path] = []

    for sample in samples:
        sample_name = sample["name"]
        sample_fovs = parse_fovs_field(sample.get("fovs", []))
        logger.info("Processing sample '%s' with FOVs: %s", sample_name, sample_fovs)

        for channel, features in channel_feature_config:
            channel_feature_maps: dict[int, FeatureMaps] = {}
            for fov in sample_fovs:
                key = (fov, channel)
                feature_maps = feature_maps_by_fov_channel.get(key)
                if feature_maps:
                    channel_feature_maps[fov] = feature_maps

            if not channel_feature_maps:
                logger.warning(
                    "No data for sample %s, channel %s", sample_name, channel
                )
                continue

            times = get_all_times(channel_feature_maps, sample_fovs)

            for feature_name in features:
                output_filename = f"{sample_name}_{feature_name}_ch_{channel}.csv"
                output_path = output_dir / output_filename
                write_feature_csv(
                    output_path,
                    times,
                    sample_fovs,
                    feature_name,
                    channel_feature_maps,
                    channel,
                    time_units,
                )
                created_files.append(output_path)
                logger.info("Created: %s", output_filename)

    logger.info("Merge completed successfully")
    logger.info("Created %d files in %s", len(created_files), output_dir)
    return f"Merge completed. Created {len(created_files)} files in {output_dir}"
