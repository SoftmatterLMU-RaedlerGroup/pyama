"""Merge configuration types for pyama-air GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class MergePageData:
    """Data structure for merge wizard page data."""
    
    # Sample configuration page
    samples: list[dict[str, str]] = None
    
    # File selection page
    sample_yaml_path: Path | None = None
    processing_results_path: Path | None = None
    output_dir: Path | None = None
    
    def __post_init__(self) -> None:
        """Initialize mutable defaults."""
        if self.samples is None:
            self.samples = []


@dataclass
class MergeConfig:
    """Complete merge configuration."""
    
    # Sample configuration
    samples: list[dict[str, str]]
    
    # File paths
    sample_yaml_path: Path
    processing_results_path: Path
    output_dir: Path
    
    @classmethod
    def from_page_data(cls, page_data: MergePageData) -> MergeConfig | None:
        """Create MergeConfig from MergePageData."""
        if not all([
            page_data.sample_yaml_path,
            page_data.processing_results_path,
            page_data.output_dir,
        ]):
            return None
            
        return cls(
            samples=page_data.samples,
            sample_yaml_path=page_data.sample_yaml_path,
            processing_results_path=page_data.processing_results_path,
            output_dir=page_data.output_dir,
        )
