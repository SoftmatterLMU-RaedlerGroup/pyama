"""Data merging service for converting processing CSV format to analysis CSV format.

This module provides the MergeService class that handles:
- Sample group creation and validation
- Format conversion from processing to analysis CSV
- Sequential cell ID renumbering across FOVs
- Time conversion from frame numbers to hours
"""

import pandas as pd
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import logging
import json

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


@dataclass
class MergeConfiguration:
    """
    Configuration for merge operations, including sample groupings and settings.
    
    Attributes:
        samples: List of sample group definitions
        processing_directory: Path to processing output directory
        frames_per_hour: Number of frames per hour for time conversion
        min_trace_length: Minimum trace length filter (frames)
        created_timestamp: ISO timestamp when configuration was created
        version: Configuration format version
    """
    samples: List[Dict[str, any]]  # Serializable sample group data
    processing_directory: str = ""
    frames_per_hour: float = 12.0
    min_trace_length: int = 0
    created_timestamp: str = ""
    version: str = "1.0"
    
    def to_sample_groups(self) -> List[SampleGroup]:
        """
        Convert serialized sample data back to SampleGroup objects.
        
        Returns:
            List of SampleGroup instances
        """
        sample_groups = []
        for sample_data in self.samples:
            sample_group = SampleGroup(
                name=sample_data['name'],
                fov_ranges=sample_data['fov_ranges'],
                resolved_fovs=sample_data.get('resolved_fovs', []),
                total_cells=sample_data.get('total_cells', 0)
            )
            sample_groups.append(sample_group)
        return sample_groups
    
    @classmethod
    def from_sample_groups(cls, sample_groups: List[SampleGroup], 
                          processing_directory: Path = None,
                          frames_per_hour: float = 12.0,
                          min_trace_length: int = 0) -> 'MergeConfiguration':
        """
        Create configuration from SampleGroup objects.
        
        Args:
            sample_groups: List of sample groups
            processing_directory: Processing output directory
            frames_per_hour: Frames per hour setting
            min_trace_length: Minimum trace length filter
            
        Returns:
            MergeConfiguration instance
        """
        from datetime import datetime
        
        # Convert sample groups to serializable format
        samples_data = []
        for sg in sample_groups:
            sample_data = {
                'name': sg.name,
                'fov_ranges': sg.fov_ranges,
                'resolved_fovs': sg.resolved_fovs,
                'total_cells': sg.total_cells
            }
            samples_data.append(sample_data)
        
        return cls(
            samples=samples_data,
            processing_directory=str(processing_directory) if processing_directory else "",
            frames_per_hour=frames_per_hour,
            min_trace_length=min_trace_length,
            created_timestamp=datetime.now().isoformat(),
            version="1.0"
        )


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
    
    def save_configuration(self, sample_groups: List[SampleGroup], 
                          config_path: Path,
                          processing_directory: Path = None) -> None:
        """
        Save sample grouping configuration to JSON file.
        
        Args:
            sample_groups: List of sample groups to save
            config_path: Path to save configuration file
            processing_directory: Processing output directory
        """
        try:
            # Create configuration object
            config = MergeConfiguration.from_sample_groups(
                sample_groups=sample_groups,
                processing_directory=processing_directory,
                frames_per_hour=self.frames_per_hour
            )
            
            # Convert to dictionary for JSON serialization
            config_dict = asdict(config)
            
            # Ensure output directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write JSON file
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved configuration with {len(sample_groups)} samples to {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration to {config_path}: {e}")
            raise
    
    def load_configuration(self, config_path: Path) -> Tuple[MergeConfiguration, List[str]]:
        """
        Load sample grouping configuration from JSON file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Tuple of (MergeConfiguration, list of warning messages)
            
        Raises:
            FileNotFoundError: If configuration file doesn't exist
            ValueError: If configuration format is invalid
        """
        warnings = []
        
        try:
            # Read JSON file
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            # Validate required fields
            required_fields = ['samples', 'version']
            missing_fields = [field for field in required_fields if field not in config_dict]
            if missing_fields:
                raise ValueError(f"Configuration missing required fields: {missing_fields}")
            
            # Check version compatibility
            version = config_dict.get('version', '1.0')
            if version != '1.0':
                warnings.append(f"Configuration version {version} may not be fully compatible")
            
            # Create configuration object
            config = MergeConfiguration(**config_dict)
            
            # Validate sample data
            for i, sample_data in enumerate(config.samples):
                if 'name' not in sample_data or 'fov_ranges' not in sample_data:
                    warnings.append(f"Sample {i} missing required fields (name, fov_ranges)")
            
            logger.info(f"Loaded configuration with {len(config.samples)} samples from {config_path}")
            
            return config, warnings
            
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file {config_path}: {e}")
            raise ValueError(f"Invalid JSON format: {e}")
        except Exception as e:
            logger.error(f"Failed to load configuration from {config_path}: {e}")
            raise
    
    def validate_configuration_compatibility(self, config: MergeConfiguration, 
                                           available_fovs: List[int],
                                           processing_directory: Path = None) -> Tuple[List[SampleGroup], List[str]]:
        """
        Validate configuration compatibility with current dataset.
        
        Args:
            config: Configuration to validate
            available_fovs: List of currently available FOV indices
            processing_directory: Current processing directory
            
        Returns:
            Tuple of (validated sample groups, list of warning messages)
        """
        warnings = []
        validated_samples = []
        
        # Check processing directory compatibility
        if config.processing_directory and processing_directory:
            config_dir = Path(config.processing_directory)
            if config_dir != processing_directory:
                warnings.append(
                    f"Configuration was created for directory '{config_dir}' "
                    f"but current directory is '{processing_directory}'"
                )
        
        # Validate each sample group
        for sample_data in config.samples:
            try:
                sample_name = sample_data['name']
                fov_ranges = sample_data['fov_ranges']
                
                # Parse FOV ranges
                resolved_fovs = parse_fov_ranges(fov_ranges)
                
                # Check for missing FOVs
                missing_fovs = [fov for fov in resolved_fovs if fov not in available_fovs]
                if missing_fovs:
                    warnings.append(
                        f"Sample '{sample_name}' references missing FOVs: {missing_fovs}. "
                        f"Available FOVs: {available_fovs}"
                    )
                    # Filter to only available FOVs
                    available_resolved_fovs = [fov for fov in resolved_fovs if fov in available_fovs]
                    if not available_resolved_fovs:
                        warnings.append(f"Sample '{sample_name}' has no available FOVs - skipping")
                        continue
                    resolved_fovs = available_resolved_fovs
                
                # Create sample group
                sample_group = SampleGroup(
                    name=sample_name,
                    fov_ranges=fov_ranges,
                    resolved_fovs=resolved_fovs,
                    total_cells=sample_data.get('total_cells', 0)
                )
                
                validated_samples.append(sample_group)
                
            except Exception as e:
                warnings.append(f"Failed to validate sample '{sample_data.get('name', 'unknown')}': {e}")
        
        logger.info(f"Validated configuration: {len(validated_samples)} samples, {len(warnings)} warnings")
        
        return validated_samples, warnings