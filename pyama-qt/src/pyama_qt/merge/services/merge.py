"""Data merging service for converting processing CSV format to analysis CSV format.

This module provides the MergeService class that handles:
- Sample group creation and validation
- Format conversion from processing to analysis CSV
- Sequential cell ID renumbering across FOVs
- Time conversion from frame numbers to hours
"""

import pandas as pd
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import logging

from pyama_core.io.processing_csv import ProcessingCSVLoader
from pyama_core.io.analysis_csv import AnalysisCSVWriter
from ..utils.fov_parser import parse_fov_ranges, validate_fov_ranges

logger = logging.getLogger(__name__)


@dataclass
class SampleGroup:
    """
    Represents a sample group with assigned FOVs.
    
    Attributes:
        name: Sample name
        fov_ranges: FOV range notation string (e.g., "1-4,6,9-20")
        resolved_fovs: List of resolved FOV indices
        total_cells: Total number of cells across all FOVs
        fov_data: Dictionary mapping FOV index to DataFrame (loaded on demand)
    """
    name: str
    fov_ranges: str
    resolved_fovs: List[int] = None
    total_cells: int = 0
    fov_data: Dict[int, pd.DataFrame] = None
    
    def __post_init__(self):
        if self.resolved_fovs is None:
            self.resolved_fovs = []
        if self.fov_data is None:
            self.fov_data = {}


class MergeService:
    """
    Service for merging FOV trace data into sample-level analysis CSV files.
    
    Handles conversion from processing format (fov, cell_id, frame, features...)
    to analysis format (time as index, cells as columns).
    """
    
    def __init__(self, frames_per_hour: float = 12.0):
        """
        Initialize the merge service.
        
        Args:
            frames_per_hour: Number of frames per hour for time conversion
        """
        self.frames_per_hour = frames_per_hour
        self.processing_loader = ProcessingCSVLoader()
        self.analysis_writer = AnalysisCSVWriter()
    
    def create_sample_group(self, name: str, fov_ranges: str, available_fovs: List[int]) -> SampleGroup:
        """
        Create a sample group with validated FOV ranges.
        
        Args:
            name: Sample name
            fov_ranges: FOV range notation string
            available_fovs: List of available FOV indices
            
        Returns:
            SampleGroup instance
            
        Raises:
            ValueError: If FOV ranges are invalid
        """
        # Validate FOV ranges
        is_valid, errors = validate_fov_ranges(fov_ranges, available_fovs)
        if not is_valid:
            raise ValueError(f"Invalid FOV ranges for sample '{name}': {'; '.join(errors)}")
        
        # Parse resolved FOVs
        resolved_fovs = parse_fov_ranges(fov_ranges)
        
        sample_group = SampleGroup(
            name=name,
            fov_ranges=fov_ranges,
            resolved_fovs=resolved_fovs
        )
        
        logger.info(f"Created sample group '{name}' with {len(resolved_fovs)} FOVs: {resolved_fovs}")
        return sample_group
    
    def load_fov_data(self, sample_group: SampleGroup, fov_file_paths: Dict[int, Path]) -> None:
        """
        Load FOV trace data for a sample group.
        
        Args:
            sample_group: Sample group to load data for
            fov_file_paths: Dictionary mapping FOV index to CSV file path
        """
        for fov_idx in sample_group.resolved_fovs:
            if fov_idx not in fov_file_paths:
                logger.warning(f"No file path found for FOV {fov_idx} in sample '{sample_group.name}'")
                continue
            
            try:
                csv_path = fov_file_paths[fov_idx]
                df = self.processing_loader.load_fov_traces(csv_path)
                
                # Filter to good traces only if quality data is available
                df = self.processing_loader.filter_good_traces(df)
                
                sample_group.fov_data[fov_idx] = df
                logger.debug(f"Loaded {len(df)} traces from FOV {fov_idx} for sample '{sample_group.name}'")
                
            except Exception as e:
                logger.error(f"Failed to load FOV {fov_idx} data for sample '{sample_group.name}': {e}")
                raise
        
        # Calculate total cells
        sample_group.total_cells = sum(
            df['cell_id'].nunique() for df in sample_group.fov_data.values()
        )
        
        logger.info(f"Loaded data for sample '{sample_group.name}': {len(sample_group.fov_data)} FOVs, {sample_group.total_cells} total cells")
    
    def merge_sample_data(self, sample_group: SampleGroup) -> pd.DataFrame:
        """
        Merge FOV data into analysis format for a sample group.
        
        Args:
            sample_group: Sample group with loaded FOV data
            
        Returns:
            DataFrame in analysis format (time as index, cells as columns)
        """
        if not sample_group.fov_data:
            raise ValueError(f"No FOV data loaded for sample '{sample_group.name}'")
        
        # Collect all trace data with sequential cell ID renumbering
        all_traces = []
        next_cell_id = 0
        
        for fov_idx in sorted(sample_group.resolved_fovs):
            if fov_idx not in sample_group.fov_data:
                logger.warning(f"FOV {fov_idx} data not available for sample '{sample_group.name}'")
                continue
            
            fov_df = sample_group.fov_data[fov_idx].copy()
            
            # Create mapping from original cell_id to sequential cell_id
            unique_cells = sorted(fov_df['cell_id'].unique())
            cell_id_mapping = {orig_id: next_cell_id + i for i, orig_id in enumerate(unique_cells)}
            
            # Apply sequential cell ID renumbering
            fov_df['sequential_cell_id'] = fov_df['cell_id'].map(cell_id_mapping)
            
            # Convert frame to time in hours
            fov_df['time_hours'] = fov_df['frame'] / self.frames_per_hour
            
            # Select relevant columns for merging
            trace_data = fov_df[['sequential_cell_id', 'time_hours', 'intensity_total']].copy()
            
            all_traces.append(trace_data)
            next_cell_id += len(unique_cells)
            
            logger.debug(f"FOV {fov_idx}: mapped {len(unique_cells)} cells to IDs {next_cell_id - len(unique_cells)}-{next_cell_id - 1}")
        
        if not all_traces:
            raise ValueError(f"No valid trace data found for sample '{sample_group.name}'")
        
        # Combine all traces
        combined_traces = pd.concat(all_traces, ignore_index=True)
        
        # Pivot to analysis format: time as index, cells as columns
        analysis_df = combined_traces.pivot_table(
            index='time_hours',
            columns='sequential_cell_id',
            values='intensity_total',
            aggfunc='first'  # Should be unique anyway
        )
        
        # Ensure column names are sequential integers starting from 0
        analysis_df.columns = range(len(analysis_df.columns))
        analysis_df.index.name = 'time'
        
        # Sort by time
        analysis_df = analysis_df.sort_index()
        
        logger.info(f"Merged sample '{sample_group.name}': {len(analysis_df)} time points, {len(analysis_df.columns)} cells")
        return analysis_df
    
    def export_sample_csv(self, sample_group: SampleGroup, output_dir: Path) -> Path:
        """
        Export sample data to analysis CSV format.
        
        Args:
            sample_group: Sample group with loaded data
            output_dir: Directory to save the CSV file
            
        Returns:
            Path to the exported CSV file
        """
        # Merge the data
        analysis_df = self.merge_sample_data(sample_group)
        
        # Create output file path
        output_path = output_dir / f"{sample_group.name}.csv"
        
        # Write the CSV file
        self.analysis_writer.write_sample_data(analysis_df, output_path)
        
        logger.info(f"Exported sample '{sample_group.name}' to {output_path}")
        return output_path
    
    def validate_sample_groups(self, sample_groups: List[SampleGroup], available_fovs: List[int]) -> List[str]:
        """
        Validate a list of sample groups for conflicts and issues.
        
        Args:
            sample_groups: List of sample groups to validate
            available_fovs: List of available FOV indices
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Check for duplicate sample names
        sample_names = [sg.name for sg in sample_groups]
        duplicate_names = set([name for name in sample_names if sample_names.count(name) > 1])
        if duplicate_names:
            errors.append(f"Duplicate sample names: {sorted(duplicate_names)}")
        
        # Check for FOV conflicts
        all_assigned_fovs = {}  # fov_index -> sample_name
        
        for sample_group in sample_groups:
            for fov_idx in sample_group.resolved_fovs:
                if fov_idx in all_assigned_fovs:
                    other_sample = all_assigned_fovs[fov_idx]
                    errors.append(f"FOV {fov_idx} assigned to both '{sample_group.name}' and '{other_sample}'")
                else:
                    all_assigned_fovs[fov_idx] = sample_group.name
        
        # Check for empty sample groups
        empty_samples = [sg.name for sg in sample_groups if not sg.resolved_fovs]
        if empty_samples:
            errors.append(f"Samples with no assigned FOVs: {empty_samples}")
        
        return errors
    
    def get_merge_statistics(self, sample_groups: List[SampleGroup]) -> Dict[str, any]:
        """
        Get statistics about the merge operation.
        
        Args:
            sample_groups: List of sample groups
            
        Returns:
            Dictionary with merge statistics
        """
        total_fovs = sum(len(sg.resolved_fovs) for sg in sample_groups)
        total_cells = sum(sg.total_cells for sg in sample_groups)
        
        stats = {
            'sample_count': len(sample_groups),
            'total_fovs': total_fovs,
            'total_cells': total_cells,
            'samples': []
        }
        
        for sg in sample_groups:
            sample_stats = {
                'name': sg.name,
                'fov_count': len(sg.resolved_fovs),
                'fov_indices': sg.resolved_fovs,
                'cell_count': sg.total_cells,
                'has_data': bool(sg.fov_data)
            }
            stats['samples'].append(sample_stats)
        
        return stats