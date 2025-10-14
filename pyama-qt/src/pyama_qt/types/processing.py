"""Processing-related data structures."""

# =============================================================================
# IMPORTS
# =============================================================================

from dataclasses import dataclass
from pathlib import Path


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass(frozen=True)
class ChannelSelectionPayload:
    """Lightweight payload describing selected channels."""

    phase: int | None
    fluorescence: list[int]


@dataclass(frozen=True)
class MergeRequest:
    """Data structure for merge operation requests."""

    sample_yaml: Path
    processing_results_yaml: Path
    input_dir: Path
    output_dir: Path


@dataclass(frozen=True)
class FeatureMaps:
    """Maps for feature data organized by (time, cell) tuples."""

    features: dict[
        str, dict[tuple[float, int], float]
    ]  # feature_name -> (time, cell) -> value
    times: list[float]
    cells: list[int]
