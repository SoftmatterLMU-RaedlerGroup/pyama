"""Dataclasses shared across workflow services to avoid circular imports."""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, TypedDict


class ChannelSelection(TypedDict, total=False):
    channel: int
    features: list[str]


def normalize_channel_selection(selection: ChannelSelection) -> None:
    """Normalize channel selection features in-place."""
    features = selection.get("features", [])
    seen: set[str] = set()
    normalized: list[str] = []
    for feature in features:
        if feature is None:
            continue
        feature_str = str(feature)
        if feature_str and feature_str not in seen:
            seen.add(feature_str)
            normalized.append(feature_str)
    normalized.sort()
    selection["features"] = normalized
    # Ensure channel is int
    if "channel" in selection:
        selection["channel"] = int(selection["channel"])


def extend_channel_selection_features(selection: ChannelSelection, new_features: Iterable[Any]) -> None:
    """Extend channel selection features in-place."""
    if not new_features:
        return
    features = selection.get("features", [])
    combined = list(features)
    for feature in new_features:
        if feature is None:
            continue
        feature_str = str(feature)
        if feature_str:
            combined.append(feature_str)
    selection["features"] = combined
    normalize_channel_selection(selection)


def merge_channel_selection(parent: ChannelSelection, other: ChannelSelection) -> None:
    """Merge other channel selection into parent in-place."""
    if other.get("channel") != parent.get("channel"):
        return
    extend_channel_selection_features(parent, other.get("features", []))


def copy_channel_selection(selection: ChannelSelection) -> ChannelSelection:
    """Create a copy of channel selection."""
    return {
        "channel": int(selection.get("channel", 0)),
        "features": list(selection.get("features", [])),
    }


def channel_selection_to_payload(selection: ChannelSelection) -> list[Any]:
    """Convert channel selection to payload format for serialization."""
    return [selection.get("channel", 0), list(selection.get("features", []))]


def channel_selection_from_value(value: Any) -> ChannelSelection | None:
    """Create ChannelSelection from various input formats."""
    if value is None:
        return None
    if isinstance(value, dict) and ("channel" in value or "features" in value):
        # Already a ChannelSelection dict
        selection: ChannelSelection = {
            "channel": int(value.get("channel", 0)),
            "features": list(value.get("features", [])),
        }
        normalize_channel_selection(selection)
        return selection
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if not value:
            return None
        channel = value[0]
        remainder = list(value[1:])
        feature_values: list[Any] = []
        if remainder:
            head = remainder[0]
            if isinstance(head, Sequence) and not isinstance(head, (str, bytes)):
                feature_values.extend(head)
                extra = remainder[1:]
            else:
                if head is not None:
                    feature_values.append(head)
                extra = remainder[1:]
            for item in extra:
                if isinstance(item, Sequence) and not isinstance(
                    item, (str, bytes)
                ):
                    feature_values.extend(item)
                elif item is not None:
                    feature_values.append(item)
        selection: ChannelSelection = {
            "channel": int(channel),
            "features": list(feature_values),
        }
        normalize_channel_selection(selection)
        return selection
    if isinstance(value, (int, str)):
        try:
            selection: ChannelSelection = {
                "channel": int(value),
                "features": [],
            }
            normalize_channel_selection(selection)
            return selection
        except Exception:
            return None
    return None


class Channels(TypedDict, total=False):
    pc: ChannelSelection | None
    fl: list[ChannelSelection]


def _normalize_fl(value: Any) -> list[ChannelSelection]:
    """Normalize fluorescence channel list."""
    normalized: dict[int, ChannelSelection] = {}
    entries: list[Any] = []

    if isinstance(value, dict) and ("channel" in value or "features" in value):
        entries.append(value)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        entries.extend(value)
    elif value is not None:
        entries.append(value)

    for entry in entries:
        selection = channel_selection_from_value(entry)
        if selection is None:
            continue
        channel = selection.get("channel", 0)
        existing = normalized.get(channel)
        if existing is None:
            normalized[channel] = selection
        else:
            merge_channel_selection(existing, selection)

    return [normalized[channel] for channel in sorted(normalized)]


def normalize_channels(channels: Channels) -> None:
    """Normalize channels in-place."""
    channels["pc"] = channel_selection_from_value(channels.get("pc"))
    if channels.get("pc"):
        normalize_channel_selection(channels["pc"])
    channels["fl"] = _normalize_fl(channels.get("fl", []))


def merge_channels(parent: Channels, other: Channels) -> None:
    """Merge other channels into parent in-place."""
    other_pc = other.get("pc")
    if other_pc:
        parent_pc = parent.get("pc")
        if parent_pc is None:
            parent["pc"] = copy_channel_selection(other_pc)
        elif parent_pc.get("channel") == other_pc.get("channel"):
            merge_channel_selection(parent_pc, other_pc)

    parent_fl = parent.setdefault("fl", [])
    fl_map: dict[int, ChannelSelection] = {sel.get("channel", 0): sel for sel in parent_fl}
    for selection in other.get("fl", []):
        channel = selection.get("channel", 0)
        existing = fl_map.get(channel)
        if existing is None:
            fl_map[channel] = copy_channel_selection(selection)
        else:
            merge_channel_selection(existing, selection)

    parent["fl"] = _normalize_fl(list(fl_map.values()))


def get_pc_channel(channels: Channels) -> int | None:
    """Get phase contrast channel ID."""
    pc = channels.get("pc")
    return pc.get("channel") if pc else None


def get_pc_features(channels: Channels) -> list[str]:
    """Get phase contrast feature list."""
    pc = channels.get("pc")
    return list(pc.get("features", [])) if pc else []


def get_fl_feature_map(channels: Channels) -> dict[int, list[str]]:
    """Get fluorescence channel to features mapping."""
    fl = channels.get("fl", [])
    return {sel.get("channel", 0): list(sel.get("features", [])) for sel in fl}


def get_fl_channels(channels: Channels) -> list[int]:
    """Get list of fluorescence channel IDs."""
    fl = channels.get("fl", [])
    return [sel.get("channel", 0) for sel in fl]




class ResultsPerFOV(TypedDict, total=False):
    pc: tuple[int, str] | None
    fl: list[tuple[int, str]]
    seg: tuple[int, str] | None
    seg_labeled: tuple[int, str] | None
    fl_background: list[tuple[int, str]]
    traces: str | None


class ProcessingContext(TypedDict, total=False):
    output_dir: str | None
    channels: Channels | None
    results: dict[int, ResultsPerFOV] | None
    params: dict[str, Any] | None
    time_units: str | None


def ensure_results_entry() -> ResultsPerFOV:
    return {
        "fl": [],
        "fl_background": [],
    }


def ensure_context(ctx: ProcessingContext | None) -> ProcessingContext:
    """Ensure context is properly initialized with required fields."""
    if ctx is None:
        return {
            "channels": {"fl": []},
            "results": {},
            "params": {},
        }

    ctx_channels = ctx.get("channels")
    if ctx_channels is None:
        ctx["channels"] = {"fl": []}
    elif isinstance(ctx_channels, Mapping):
        normalize_channels(ctx_channels)

    if ctx.get("results") is None:
        ctx["results"] = {}

    if ctx.get("params") is None:
        ctx["params"] = {}

    return ctx


__all__ = [
    "ChannelSelection",
    "Channels",
    "ResultsPerFOV",
    "ProcessingContext",
    "ensure_context",
    "ensure_results_entry",
    "normalize_channels",
    "merge_channels",
    "get_pc_channel",
    "get_pc_features",
    "get_fl_feature_map",
    "get_fl_channels",
    "normalize_channel_selection",
    "extend_channel_selection_features",
    "merge_channel_selection",
    "copy_channel_selection",
    "channel_selection_to_payload",
    "channel_selection_from_value",
]
