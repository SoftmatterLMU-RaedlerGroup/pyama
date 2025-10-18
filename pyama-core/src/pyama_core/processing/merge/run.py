"""Entry point for executing merge operations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from pyama_core.io.processing_csv import get_dataframe
from pyama_core.io.results_yaml import (
    get_time_units_from_yaml,
    get_trace_csv_path_from_yaml,
    load_processing_results_yaml,
)

from .channels import get_channel_feature_config
from .features import (
    build_feature_maps,
    extract_channel_dataframe,
    get_all_times,
    write_feature_csv,
)
from .samples import parse_fovs_field, read_samples_yaml
from .types import FeatureMaps

logger = logging.getLogger(__name__)


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

    feature_maps_by_fov_channel: Dict[Tuple[int, int], FeatureMaps] = {}
    traces_cache: dict[Path, pd.DataFrame] = {}

    for fov in sorted(all_fovs):
        for channel, features in channel_feature_config:
            csv_entry = get_trace_csv_path_from_yaml(proc_results, fov, channel)
            if csv_entry is None:
                logger.warning("No trace CSV entry for FOV %s, channel %s", fov, channel)
                continue

            csv_path = Path(csv_entry)
            if not csv_path.is_absolute():
                csv_path = input_dir / csv_path
            if not csv_path.exists():
                logger.warning("Trace CSV file does not exist: %s", csv_path)
                continue

            if csv_path not in traces_cache:
                try:
                    traces_cache[csv_path] = get_dataframe(csv_path)
                except Exception as exc:
                    logger.warning("Failed to read %s: %s", csv_path, exc)
                    continue

            channel_df = extract_channel_dataframe(traces_cache[csv_path], channel)
            if channel_df.empty:
                logger.warning(
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
                logger.warning("No data for sample %s, channel %s", sample_name, channel)
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
