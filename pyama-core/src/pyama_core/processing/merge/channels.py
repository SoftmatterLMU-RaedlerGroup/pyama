"""Helpers for determining channel/feature selections during merge."""

from __future__ import annotations

from typing import List, Tuple

from pyama_core.processing.extraction.feature import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama_core.processing.workflow.services.types import Channels


def get_channel_feature_config(proc_results: dict) -> List[Tuple[int, List[str]]]:
    """Determine the channel/feature selections from processing results."""
    channels_data = proc_results.get("channels")
    if channels_data is None:
        raise ValueError("Processing results missing 'channels' section")

    try:
        channel_config = Channels.from_serialized(channels_data)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid channel configuration in processing results: {exc}") from exc

    config: List[Tuple[int, List[str]]] = []

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
