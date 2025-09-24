"""Typed state containers for the analysis UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:  # Avoid hard dependency during documentation builds
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - pandas may be unavailable in docs
    pd = None  # type: ignore


@dataclass(slots=True)
class AnalysisState:
    """Shared state for the analysis page."""

    raw_csv_path: Path | None = None
    raw_data: "pd.DataFrame" | None = None
    fitted_csv_path: Path | None = None
    fitted_results: "pd.DataFrame" | None = None
    selected_cell: str | None = None
    is_fitting: bool = False
    status_message: str = ""
    error_message: str = ""


@dataclass(slots=True)
class FittingRequest:
    """Parameters for triggering a fitting job."""

    model_type: str
    model_params: dict[str, float] = field(default_factory=dict)
    model_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
