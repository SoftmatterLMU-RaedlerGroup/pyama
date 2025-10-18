"""Processing-related data structures."""

# =============================================================================
# IMPORTS
# =============================================================================

from dataclasses import dataclass
from pathlib import Path

from pyama_core.processing.merge import FeatureMaps as MergeFeatureMaps


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


FeatureMaps = MergeFeatureMaps
