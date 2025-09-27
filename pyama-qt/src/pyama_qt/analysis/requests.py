from dataclasses import dataclass, field


@dataclass(slots=True)
class FittingRequest:
    """Parameters for triggering a fitting job."""

    model_type: str
    model_params: dict[str, float] = field(default_factory=dict)
    model_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
