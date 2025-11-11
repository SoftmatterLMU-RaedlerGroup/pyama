"""Dataclasses shared across workflow services to avoid circular imports."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(slots=True)
class ChannelSelection:
    channel: int
    features: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.channel = int(self.channel)
        self._normalize()

    def _normalize(self) -> None:
        seen: set[str] = set()
        normalized: list[str] = []
        for feature in self.features:
            if feature is None:
                continue
            feature_str = str(feature)
            if feature_str and feature_str not in seen:
                seen.add(feature_str)
                normalized.append(feature_str)
        normalized.sort()
        self.features = normalized

    def extend_features(self, new_features: Iterable[Any]) -> None:
        if not new_features:
            return
        combined = list(self.features)
        for feature in new_features:
            if feature is None:
                continue
            feature_str = str(feature)
            if feature_str:
                combined.append(feature_str)
        self.features = combined
        self._normalize()

    def merge(self, other: "ChannelSelection") -> None:
        if other.channel != self.channel:
            return
        self.extend_features(other.features)

    def copy(self) -> "ChannelSelection":
        return ChannelSelection(self.channel, list(self.features))

    def to_payload(self) -> list[Any]:
        return [self.channel, list(self.features)]

    @classmethod
    def from_value(cls, value: Any) -> "ChannelSelection | None":
        if value is None:
            return None
        if isinstance(value, cls):
            return value.copy()
        # Handle dictionary format: {channel: N, features: [...]}
        if isinstance(value, Mapping):
            try:
                channel = int(value["channel"])
                features = value.get("features", [])
                if features is None:
                    features = []
                return cls(channel=channel, features=list(features))
            except (KeyError, ValueError, TypeError):
                return None
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if not value:
                return None
            try:
                channel = int(value[0])
            except (ValueError, TypeError):
                return None
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
            return cls(channel=channel, features=list(feature_values))
        if isinstance(value, (int, str)):
            try:
                return cls(channel=int(value))
            except Exception:
                return None
        return None


@dataclass(slots=True)
class Channels:
    pc: ChannelSelection | None = None
    fl: list[ChannelSelection] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._normalize_inplace()

    def _normalize_inplace(self) -> None:
        self.pc = ChannelSelection.from_value(self.pc)
        self.fl = self._normalize_fl(self.fl)

    def normalize(self) -> None:
        self._normalize_inplace()

    @staticmethod
    def _normalize_fl(value: Any) -> list[ChannelSelection]:
        normalized: dict[int, ChannelSelection] = {}
        entries: list[Any] = []

        if isinstance(value, ChannelSelection):
            entries.append(value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            entries.extend(value)
        elif value is None:
            entries.append(value)

        for entry in entries:
            selection = ChannelSelection.from_value(entry)
            if selection is None:
                continue
            existing = normalized.get(selection.channel)
            if existing is None:
                normalized[selection.channel] = selection
            else:
                existing.merge(selection)

        return [normalized[channel] for channel in sorted(normalized)]

    def merge_from(self, other: "Channels") -> None:
        if other.pc:
            if self.pc is None:
                self.pc = other.pc.copy()
            elif self.pc.channel == other.pc.channel:
                self.pc.merge(other.pc)

        fl_map: dict[int, ChannelSelection] = {sel.channel: sel for sel in self.fl}
        for selection in other.fl:
            existing = fl_map.get(selection.channel)
            if existing is None:
                fl_map[selection.channel] = selection.copy()
            else:
                existing.merge(selection)

        self.fl = self._normalize_fl(list(fl_map.values()))

    def get_pc_channel(self) -> int | None:
        return self.pc.channel if self.pc else None

    def get_pc_features(self) -> list[str]:
        return list(self.pc.features) if self.pc else []

    def get_fl_feature_map(self) -> dict[int, list[str]]:
        return {selection.channel: list(selection.features) for selection in self.fl}

    def get_fl_channels(self) -> list[int]:
        return [selection.channel for selection in self.fl]

    def to_raw(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "pc": self.pc.to_payload() if self.pc else None,
            "fl": [selection.to_payload() for selection in self.fl],
        }
        return payload

    @classmethod
    def from_serialized(cls, data: Any) -> "Channels":
        if not isinstance(data, Mapping):
            raise ValueError("Channels payload must be a mapping")

        raw_pc = data.get("pc")
        pc_selection = ChannelSelection.from_value(raw_pc)

        raw_fl = data.get("fl", [])
        if raw_fl is None:
            raw_fl = []
        if not isinstance(raw_fl, Sequence) or isinstance(raw_fl, (str, bytes)):
            raise ValueError("channels.fl must be a sequence of [channel, features]")

        fl_list: list[ChannelSelection] = []
        for entry in raw_fl:
            selection = ChannelSelection.from_value(entry)
            if selection is None:
                continue  # Skip invalid entries, consistent with _normalize_fl
            fl_list.append(selection)

        return cls(pc=pc_selection, fl=fl_list)


@dataclass(slots=True)
class ResultsPerFOV:
    pc: tuple[int, Path] | None = None
    fl: list[tuple[int, Path]] = field(default_factory=list)
    seg: tuple[int, Path] | None = None
    seg_labeled: tuple[int, Path] | None = None
    fl_background: list[tuple[int, Path]] = field(default_factory=list)
    traces: Path | None = None


@dataclass(slots=True)
class ProcessingContext:
    output_dir: Path | None = None
    channels: Channels | None = None
    results: dict[int, ResultsPerFOV] | None = None
    params: dict | None = None
    time_units: str | None = None


def ensure_results_entry() -> ResultsPerFOV:
    return ResultsPerFOV()


def ensure_context(ctx: ProcessingContext | None) -> ProcessingContext:
    if ctx is None:
        return ProcessingContext(
            channels=Channels(),
            results={},
            params={},
        )

    if ctx.channels is None:
        ctx.channels = Channels()
    elif isinstance(ctx.channels, Channels):
        ctx.channels.normalize()
    elif isinstance(ctx.channels, Mapping):
        ctx.channels = Channels.from_serialized(ctx.channels)
    else:
        raise ValueError("ProcessingContext channels must use the new schema")

    if ctx.results is None:
        ctx.results = {}

    if ctx.params is None:
        ctx.params = {}

    return ctx


# =============================================================================
# EXTRACTION TYPES
# =============================================================================

FeatureResult = dict[str, float]


@dataclass(frozen=True)
class Result:
    """Result from trace extraction for a single cell at a single frame."""

    cell: int
    frame: int
    time: float
    good: bool
    position_x: float
    position_y: float
    bbox_x0: float
    bbox_y0: float
    bbox_x1: float
    bbox_y1: float


@dataclass(frozen=True)
class ResultWithFeatures(Result):
    """Result with extracted features."""

    features: FeatureResult


@dataclass
class ExtractionContext:
    """Context containing all information needed for feature extraction."""

    image: np.ndarray
    mask: np.ndarray
    background: np.ndarray  # Always present; zeros if no background correction available
    background_weight: float = 0.0  # Weight for background subtraction (default: 0.0)
    erosion_size: int = 0  # Size of erosion structuring element (default: 0, no erosion)


# =============================================================================
# TRACKING TYPES
# =============================================================================


@dataclass
class Region:
    """Connected-component region summary.

    Attributes:
        area: Number of pixels in the region.
        bbox: Bounding box as ``(y0, x0, y1, x1)`` with exclusive end indices.
        coords: Array of ``(y, x)`` coordinates for all pixels in the region.
    """

    area: int
    bbox: tuple[int, int, int, int]
    coords: np.ndarray


# =============================================================================
# BACKGROUND TYPES
# =============================================================================


@dataclass
class TileSupport:
    """Support data for tiled background interpolation.

    Attributes:
        centers_x: 1D array of tile center ``x`` coordinates (pixels).
        centers_y: 1D array of tile center ``y`` coordinates (pixels).
        support: 2D array ``(n_tiles_y, n_tiles_x)`` of tile medians.
        shape: Spatial ``(H, W)`` shape of the original frame.
    """

    centers_x: np.ndarray
    centers_y: np.ndarray
    support: np.ndarray
    shape: tuple[int, int]


# =============================================================================
# MERGE TYPES
# =============================================================================


@dataclass
class FeatureMaps:
    """Container for feature values per timepoint and cell."""

    features: dict[str, dict[tuple[float, int], float]]
    times: list[float]
    cells: list[int]


__all__ = [
    "ChannelSelection",
    "Channels",
    "ResultsPerFOV",
    "ProcessingContext",
    "FeatureResult",
    "Result",
    "ResultWithFeatures",
    "ExtractionContext",
    "Region",
    "TileSupport",
    "FeatureMaps",
]
