"""Workflow configuration types for pyama-air GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class WorkflowPageData:
    """Data structure for workflow wizard page data."""
    
    # File selection page
    nd2_path: Path | None = None
    output_dir: Path | None = None
    metadata: Any = None
    
    # Channel configuration page
    pc_channel: int = 0
    fl_channels: set[int] = None
    
    # Feature selection page
    pc_features: set[str] = None
    fl_feature_map: dict[int, set[str]] = None
    
    # Parameter configuration page
    fov_start: int = 0
    fov_end: int = 0
    batch_size: int = 2
    n_workers: int = 1
    
    def __post_init__(self) -> None:
        """Initialize mutable defaults."""
        if self.fl_channels is None:
            self.fl_channels = set()
        if self.pc_features is None:
            self.pc_features = set()
        if self.fl_feature_map is None:
            self.fl_feature_map = {}


@dataclass
class WorkflowConfig:
    """Complete workflow configuration."""
    
    # File paths
    nd2_path: Path
    output_dir: Path
    
    # Channel configuration
    pc_channel: int
    fl_channels: set[int]
    
    # Feature configuration
    pc_features: set[str]
    fl_feature_map: dict[int, set[str]]
    
    # Processing parameters
    fov_start: int
    fov_end: int
    batch_size: int
    n_workers: int
    
    # Metadata
    metadata: Any = None
    
    @classmethod
    def from_page_data(cls, page_data: WorkflowPageData) -> WorkflowConfig | None:
        """Create WorkflowConfig from WorkflowPageData."""
        if not page_data.nd2_path or not page_data.output_dir:
            return None
            
        return cls(
            nd2_path=page_data.nd2_path,
            output_dir=page_data.output_dir,
            pc_channel=page_data.pc_channel,
            fl_channels=page_data.fl_channels,
            pc_features=page_data.pc_features,
            fl_feature_map=page_data.fl_feature_map,
            fov_start=page_data.fov_start,
            fov_end=page_data.fov_end,
            batch_size=page_data.batch_size,
            n_workers=page_data.n_workers,
            metadata=page_data.metadata,
        )
