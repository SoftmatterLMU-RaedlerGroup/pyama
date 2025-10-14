"""Analysis-related data structures."""

# =============================================================================
# IMPORTS
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass(slots=True)
class FittingRequest:
    """Parameters for triggering a fitting job."""

    model_type: str
    model_params: Dict[str, float] = field(default_factory=dict)
    model_bounds: Dict[str, tuple[float, float]] = field(default_factory=dict)
