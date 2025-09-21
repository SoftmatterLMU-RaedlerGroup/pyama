"""Typed state containers for the analysis UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:  # Avoid hard dependency during documentation builds
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - pandas may be unavailable in docs
    pd = None  # type: ignore


@dataclass(slots=True)
class AnalysisState:
    """Shared state for the analysis page."""

    raw_csv_path: Optional[Path] = None
    raw_data: Optional["pd.DataFrame"] = None
    fitted_csv_path: Optional[Path] = None
    fitted_results: Optional["pd.DataFrame"] = None
    selected_cell: Optional[str] = None
    is_fitting: bool = False
    status_message: str = ""
    error_message: str = ""


@dataclass(slots=True)
class FittingRequest:
    """Parameters for triggering a fitting job."""

    model_type: str
    model_params: dict[str, float] = field(default_factory=dict)
    model_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
