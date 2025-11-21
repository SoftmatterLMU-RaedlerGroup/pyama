"""Analysis configuration types for pyama-air GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AnalysisPageData:
    """Data structure for analysis wizard page data."""
    
    # File selection page
    csv_path: Path | None = None
    
    # Model configuration page
    model_type: str = ""
    model_params: dict[str, float] = None
    model_bounds: dict[str, tuple[float, float]] = None
    
    # Execution results
    fitted_results_path: Path | None = None
    fitting_success: bool = False
    fitting_message: str = ""
    
    def __post_init__(self) -> None:
        """Initialize mutable defaults."""
        if self.model_params is None:
            self.model_params = {}
        if self.model_bounds is None:
            self.model_bounds = {}


@dataclass
class AnalysisConfig:
    """Complete analysis configuration."""
    
    # File paths
    csv_path: Path
    
    # Model configuration
    model_type: str
    model_params: dict[str, float]
    model_bounds: dict[str, tuple[float, float]]
    
    @classmethod
    def from_page_data(cls, page_data: AnalysisPageData) -> AnalysisConfig | None:
        """Create AnalysisConfig from AnalysisPageData."""
        if not page_data.csv_path or not page_data.model_type:
            return None
            
        return cls(
            csv_path=page_data.csv_path,
            model_type=page_data.model_type,
            model_params=page_data.model_params or {},
            model_bounds=page_data.model_bounds or {},
        )
