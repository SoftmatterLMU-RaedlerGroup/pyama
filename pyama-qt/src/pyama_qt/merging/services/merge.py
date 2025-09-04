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
        Load FOV trace data for a sample group with comprehensive error handling.
        
        Args:
            sample_group: Sample group to load data for
            fov_file_paths: Dictionary mapping FOV index to CSV file path
            
        Raises:
            ValueError: If no FOV data could be loaded for the sample
        """
        load_errors = []
        loaded_fovs = []
        data_warnings = []
        
        logger.info(f"Loading data for sample '{sample_group.name}' with {len(sample_group.resolved_fovs)} FOVs")
        
        for fov_idx in sample_group.resolved_fovs:
            if fov_idx not in fov_file_paths:
                error_msg = f"No file path found for FOV {fov_idx} in sample '{sample_group.name}'"
                logger.warning(error_msg)
                load_errors.append(error_msg)
                continue
            
            try:
                csv_path = fov_file_paths[fov_idx]
                
                # Validate file exists and is accessible
                if not csv_path.exists():
                    error_msg = f"FOV {fov_idx} file not found: {csv_path}"
                    logger.error(error_msg)
                    load_errors.append(error_msg)
                    continue
                
                # Load trace data with error handling
                try:
                    df = self.processing_loader.load_fov_traces(csv_path)
                except pd.errors.EmptyDataError:
                    error_msg = f"FOV {fov_idx} file is empty: {csv_path}"
                    logger.error(error_msg)
                    load_errors.append(error_msg)
                    continue
                except pd.errors.ParserError as e:
                    error_msg = f"FOV {fov_idx} CSV parsing error: {e}"
                    logger.error(error_msg)
                    load_errors.append(error_msg)
                    continue
                except ValueError as e:
                    error_msg = f"FOV {fov_idx} invalid data format: {e}"
                    logger.error(error_msg)
                    load_errors.append(error_msg)
                    continue
                
                # Validate loaded data
                if df.empty:
                    error_msg = f"FOV {fov_idx} contains no data after loading"
                    logger.warning(error_msg)
                    data_warnings.append(error_msg)
                    continue
                
                # Check for required columns
                required_cols = ['cell_id', 'frame', 'intensity_total']
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    error_msg = f"FOV {fov_idx} missing required columns: {missing_cols}"
                    logger.error(error_msg)
                    load_errors.append(error_msg)
                    continue
                
                # Filter to good traces only if quality data is available
                original_count = len(df)
                df = self.processing_loader.filter_good_traces(df)
                filtered_count = len(df)
                
                if filtered_count < original_count:
                    logger.info(f"FOV {fov_idx}: filtered {original_count} traces to {filtered_count} good traces")
                
                if df.empty:
                    warning_msg = f"FOV {fov_idx} has no good traces after quality filtering"
                    logger.warning(warning_msg)
                    data_warnings.append(warning_msg)
                    continue
                
                # Validate data consistency
                cell_count = df['cell_id'].nunique()
                frame_count = df['frame'].nunique()
                
                if cell_count == 0:
                    warning_msg = f"FOV {fov_idx} has no cells after filtering"
                    logger.warning(warning_msg)
                    data_warnings.append(warning_msg)
                    continue
                
                if frame_count < 2:
                    warning_msg = f"FOV {fov_idx} has insufficient time points ({frame_count})"
                    logger.warning(warning_msg)
                    data_warnings.append(warning_msg)
                
                # Check for missing intensity values
                missing_intensity = df['intensity_total'].isnull().sum()
                if missing_intensity > 0:
                    warning_msg = f"FOV {fov_idx} has {missing_intensity} missing intensity values"
                    logger.warning(warning_msg)
                    data_warnings.append(warning_msg)
                
                # Store the loaded data
                sample_group.fov_data[fov_idx] = df
                loaded_fovs.append(fov_idx)
                logger.debug(f"Successfully loaded FOV {fov_idx}: {cell_count} cells, {frame_count} frames, {len(df)} traces")
                
            except PermissionError as e:
                error_msg = f"Permission denied reading FOV {fov_idx} file {csv_path}: {e}"
                logger.error(error_msg)
                load_errors.append(error_msg)
            except OSError as e:
                error_msg = f"OS error reading FOV {fov_idx} file {csv_path}: {e}"
                logger.error(error_msg)
                load_errors.append(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error loading FOV {fov_idx} data for sample '{sample_group.name}': {type(e).__name__}: {e}"
                logger.error(error_msg)
                load_errors.append(error_msg)
        
        # Report loading results
        if not loaded_fovs:
            error_summary = f"No FOV data could be loaded for sample '{sample_group.name}'"
            if load_errors:
                error_summary += f". Errors: {'; '.join(load_errors[:3])}"
                if len(load_errors) > 3:
                    error_summary += f" (and {len(load_errors) - 3} more)"
            logger.error(error_summary)
            raise ValueError(error_summary)
        
        # Calculate total cells from successfully loaded data
        sample_group.total_cells = sum(
            df['cell_id'].nunique() for df in sample_group.fov_data.values()
        )
        
        # Update resolved FOVs to only include successfully loaded ones
        sample_group.resolved_fovs = loaded_fovs
        
        # Log summary
        success_msg = f"Loaded data for sample '{sample_group.name}': {len(loaded_fovs)} FOVs, {sample_group.total_cells} total cells"
        if load_errors:
            success_msg += f" ({len(load_errors)} FOVs failed to load)"
        if data_warnings:
            success_msg += f" ({len(data_warnings)} data quality warnings)"
        logger.info(success_msg)
        
        # Log detailed errors and warnings
        if load_errors:
            logger.warning(f"Sample '{sample_group.name}' load errors:")
            for error in load_errors[:5]:  # Show first 5 errors
                logger.warning(f"  - {error}")
            if len(load_errors) > 5:
                logger.warning(f"  ... and {len(load_errors) - 5} more errors")
        
        if data_warnings:
            logger.info(f"Sample '{sample_group.name}' data quality warnings:")
            for warning in data_warnings[:5]:  # Show first 5 warnings
                logger.info(f"  - {warning}")
            if len(data_warnings) > 5:
                logger.info(f"  ... and {len(data_warnings) - 5} more warnings")
    
    def merge_sample_data(self, sample_group: SampleGroup) -> pd.DataFrame:
        """
        Merge FOV data into analysis format for a sample group with comprehensive validation.
        
        Args:
            sample_group: Sample group with loaded FOV data
            
        Returns:
            DataFrame in analysis format (time as index, cells as columns)
            
        Raises:
            ValueError: If no valid data can be merged or data is inconsistent
        """
        if not sample_group.fov_data:
            raise ValueError(f"No FOV data loaded for sample '{sample_group.name}'")
        
        logger.info(f"Merging data for sample '{sample_group.name}' with {len(sample_group.fov_data)} FOVs")
        
        # Collect all trace data with sequential cell ID renumbering
        all_traces = []
        next_cell_id = 0
        merge_warnings = []
        fov_stats = {}
        
        # First pass: validate data consistency across FOVs
        frame_ranges = {}
        time_intervals = {}
        
        for fov_idx in sorted(sample_group.resolved_fovs):
            if fov_idx not in sample_group.fov_data:
                warning_msg = f"FOV {fov_idx} data not available for sample '{sample_group.name}'"
                logger.warning(warning_msg)
                merge_warnings.append(warning_msg)
                continue
            
            fov_df = sample_group.fov_data[fov_idx]
            
            # Validate FOV data structure
            if fov_df.empty:
                warning_msg = f"FOV {fov_idx} contains no data"
                logger.warning(warning_msg)
                merge_warnings.append(warning_msg)
                continue
            
            # Check for required columns
            required_cols = ['cell_id', 'frame', 'intensity_total']
            missing_cols = [col for col in required_cols if col not in fov_df.columns]
            if missing_cols:
                error_msg = f"FOV {fov_idx} missing required columns: {missing_cols}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Analyze frame ranges and time intervals
            frames = sorted(fov_df['frame'].unique())
            if len(frames) < 2:
                warning_msg = f"FOV {fov_idx} has insufficient time points ({len(frames)})"
                logger.warning(warning_msg)
                merge_warnings.append(warning_msg)
                continue
            
            frame_ranges[fov_idx] = (min(frames), max(frames))
            
            # Calculate time intervals
            frame_diffs = [frames[i+1] - frames[i] for i in range(len(frames)-1)]
            avg_interval = sum(frame_diffs) / len(frame_diffs)
            time_intervals[fov_idx] = avg_interval
            
            # Check for irregular time intervals
            if max(frame_diffs) - min(frame_diffs) > avg_interval * 0.1:  # More than 10% variation
                warning_msg = f"FOV {fov_idx} has irregular time intervals"
                logger.warning(warning_msg)
                merge_warnings.append(warning_msg)
        
        # Check for consistent time intervals across FOVs
        if time_intervals:
            interval_values = list(time_intervals.values())
            avg_interval = sum(interval_values) / len(interval_values)
            inconsistent_fovs = [
                fov_idx for fov_idx, interval in time_intervals.items()
                if abs(interval - avg_interval) > avg_interval * 0.1
            ]
            if inconsistent_fovs:
                warning_msg = f"Inconsistent time intervals across FOVs: {inconsistent_fovs}"
                logger.warning(warning_msg)
                merge_warnings.append(warning_msg)
        
        # Second pass: merge the data
        for fov_idx in sorted(sample_group.resolved_fovs):
            if fov_idx not in sample_group.fov_data:
                continue
            
            try:
                fov_df = sample_group.fov_data[fov_idx].copy()
                
                if fov_df.empty:
                    continue
                
                # Validate intensity data
                intensity_col = fov_df['intensity_total']
                if intensity_col.isnull().all():
                    warning_msg = f"FOV {fov_idx} has no valid intensity data"
                    logger.warning(warning_msg)
                    merge_warnings.append(warning_msg)
                    continue
                
                # Check for negative intensities
                negative_count = (intensity_col < 0).sum()
                if negative_count > 0:
                    warning_msg = f"FOV {fov_idx} has {negative_count} negative intensity values"
                    logger.warning(warning_msg)
                    merge_warnings.append(warning_msg)
                
                # Check for extremely high intensities (potential outliers)
                intensity_median = intensity_col.median()
                if intensity_median > 0:
                    outlier_threshold = intensity_median * 100  # 100x median
                    outlier_count = (intensity_col > outlier_threshold).sum()
                    if outlier_count > 0:
                        warning_msg = f"FOV {fov_idx} has {outlier_count} potential intensity outliers (>100x median)"
                        logger.warning(warning_msg)
                        merge_warnings.append(warning_msg)
                
                # Create mapping from original cell_id to sequential cell_id
                unique_cells = sorted(fov_df['cell_id'].unique())
                if not unique_cells:
                    warning_msg = f"FOV {fov_idx} has no cells"
                    logger.warning(warning_msg)
                    merge_warnings.append(warning_msg)
                    continue
                
                cell_id_mapping = {orig_id: next_cell_id + i for i, orig_id in enumerate(unique_cells)}
                
                # Apply sequential cell ID renumbering
                fov_df['sequential_cell_id'] = fov_df['cell_id'].map(cell_id_mapping)
                
                # Convert frame to time in hours
                fov_df['time_hours'] = fov_df['frame'] / self.frames_per_hour
                
                # Validate time conversion
                if fov_df['time_hours'].isnull().any():
                    error_msg = f"FOV {fov_idx} has invalid frame values that cannot be converted to time"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # Select relevant columns for merging
                trace_data = fov_df[['sequential_cell_id', 'time_hours', 'intensity_total']].copy()
                
                # Remove any rows with missing data
                original_len = len(trace_data)
                trace_data = trace_data.dropna()
                if len(trace_data) < original_len:
                    dropped_count = original_len - len(trace_data)
                    warning_msg = f"FOV {fov_idx}: dropped {dropped_count} rows with missing data"
                    logger.warning(warning_msg)
                    merge_warnings.append(warning_msg)
                
                if trace_data.empty:
                    warning_msg = f"FOV {fov_idx} has no valid data after cleaning"
                    logger.warning(warning_msg)
                    merge_warnings.append(warning_msg)
                    continue
                
                all_traces.append(trace_data)
                
                # Store FOV statistics
                fov_stats[fov_idx] = {
                    'cells': len(unique_cells),
                    'traces': len(trace_data),
                    'time_points': trace_data['time_hours'].nunique(),
                    'cell_id_range': (next_cell_id, next_cell_id + len(unique_cells) - 1)
                }
                
                next_cell_id += len(unique_cells)
                
                logger.debug(f"FOV {fov_idx}: mapped {len(unique_cells)} cells to IDs {next_cell_id - len(unique_cells)}-{next_cell_id - 1}")
                
            except Exception as e:
                error_msg = f"Error processing FOV {fov_idx} for sample '{sample_group.name}': {e}"
                logger.error(error_msg)
                raise ValueError(error_msg) from e
        
        if not all_traces:
            error_msg = f"No valid trace data found for sample '{sample_group.name}'"
            if merge_warnings:
                error_msg += f". Warnings: {'; '.join(merge_warnings[:3])}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            # Combine all traces
            combined_traces = pd.concat(all_traces, ignore_index=True)
            
            # Check for duplicate time-cell combinations
            duplicates = combined_traces.duplicated(subset=['sequential_cell_id', 'time_hours'])
            if duplicates.any():
                duplicate_count = duplicates.sum()
                warning_msg = f"Found {duplicate_count} duplicate time-cell combinations, keeping first occurrence"
                logger.warning(warning_msg)
                merge_warnings.append(warning_msg)
                combined_traces = combined_traces[~duplicates]
            
            # Pivot to analysis format: time as index, cells as columns
            analysis_df = combined_traces.pivot_table(
                index='time_hours',
                columns='sequential_cell_id',
                values='intensity_total',
                aggfunc='first'  # Should be unique after duplicate removal
            )
            
            # Ensure column names are sequential integers starting from 0
            analysis_df.columns = range(len(analysis_df.columns))
            analysis_df.index.name = 'time'
            
            # Sort by time
            analysis_df = analysis_df.sort_index()
            
            # Final validation
            if analysis_df.empty:
                raise ValueError(f"Merged data is empty for sample '{sample_group.name}'")
            
            # Check for excessive missing data
            missing_ratio = analysis_df.isnull().sum().sum() / (len(analysis_df) * len(analysis_df.columns))
            if missing_ratio > 0.5:
                warning_msg = f"High proportion of missing data in merged sample ({missing_ratio:.1%})"
                logger.warning(warning_msg)
                merge_warnings.append(warning_msg)
            
            # Log merge statistics
            logger.info(f"Successfully merged sample '{sample_group.name}': {len(analysis_df)} time points, {len(analysis_df.columns)} cells")
            logger.debug(f"FOV contributions: {fov_stats}")
            
            if merge_warnings:
                logger.info(f"Merge completed with {len(merge_warnings)} warnings:")
                for warning in merge_warnings[:5]:  # Show first 5 warnings
                    logger.info(f"  - {warning}")
                if len(merge_warnings) > 5:
                    logger.info(f"  ... and {len(merge_warnings) - 5} more warnings")
            
            return analysis_df
            
        except Exception as e:
            error_msg = f"Failed to merge data for sample '{sample_group.name}': {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def export_sample_csv(self, sample_group: SampleGroup, output_dir: Path) -> Path:
        """
        Export sample data to analysis CSV format with comprehensive error handling.
        
        Args:
            sample_group: Sample group with loaded data
            output_dir: Directory to save the CSV file
            
        Returns:
            Path to the exported CSV file
            
        Raises:
            ValueError: If data cannot be merged or is invalid
            PermissionError: If output directory cannot be written to
            OSError: If file cannot be created
        """
        logger.info(f"Exporting sample '{sample_group.name}' to {output_dir}")
        
        try:
            # Validate output directory
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created output directory: {output_dir}")
                except PermissionError as e:
                    error_msg = f"Permission denied creating output directory {output_dir}: {e}"
                    logger.error(error_msg)
                    raise PermissionError(error_msg) from e
                except OSError as e:
                    error_msg = f"Cannot create output directory {output_dir}: {e}"
                    logger.error(error_msg)
                    raise OSError(error_msg) from e
            
            if not output_dir.is_dir():
                error_msg = f"Output path is not a directory: {output_dir}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Test write permissions
            try:
                test_file = output_dir / ".write_test"
                test_file.touch()
                test_file.unlink()
            except PermissionError as e:
                error_msg = f"No write permission for output directory {output_dir}: {e}"
                logger.error(error_msg)
                raise PermissionError(error_msg) from e
            except OSError as e:
                error_msg = f"Cannot write to output directory {output_dir}: {e}"
                logger.error(error_msg)
                raise OSError(error_msg) from e
            
            # Merge the data with error handling
            try:
                analysis_df = self.merge_sample_data(sample_group)
            except ValueError as e:
                error_msg = f"Cannot merge data for sample '{sample_group.name}': {e}"
                logger.error(error_msg)
                raise ValueError(error_msg) from e
            
            # Validate merged data before export
            if analysis_df.empty:
                error_msg = f"Merged data is empty for sample '{sample_group.name}'"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Check for reasonable data dimensions
            if len(analysis_df.columns) == 0:
                error_msg = f"No cells in merged data for sample '{sample_group.name}'"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            if len(analysis_df) == 0:
                error_msg = f"No time points in merged data for sample '{sample_group.name}'"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Create output file path with safe filename
            safe_name = "".join(c for c in sample_group.name if c.isalnum() or c in (' ', '-', '_')).strip()
            if not safe_name:
                safe_name = f"sample_{hash(sample_group.name) % 10000}"
                logger.warning(f"Sample name '{sample_group.name}' contains invalid characters, using '{safe_name}'")
            
            output_path = output_dir / f"{safe_name}.csv"
            
            # Check if file already exists and handle appropriately
            if output_path.exists():
                logger.warning(f"Output file already exists, will overwrite: {output_path}")
            
            # Write the CSV file with error handling
            try:
                self.analysis_writer.write_sample_data(analysis_df, output_path)
            except PermissionError as e:
                error_msg = f"Permission denied writing to {output_path}: {e}"
                logger.error(error_msg)
                raise PermissionError(error_msg) from e
            except OSError as e:
                error_msg = f"OS error writing to {output_path}: {e}"
                logger.error(error_msg)
                raise OSError(error_msg) from e
            except Exception as e:
                error_msg = f"Unexpected error writing to {output_path}: {e}"
                logger.error(error_msg)
                raise OSError(error_msg) from e
            
            # Verify the file was written successfully
            if not output_path.exists():
                error_msg = f"Export file was not created: {output_path}"
                logger.error(error_msg)
                raise OSError(error_msg)
            
            # Check file size is reasonable
            try:
                file_size = output_path.stat().st_size
                if file_size == 0:
                    error_msg = f"Export file is empty: {output_path}"
                    logger.error(error_msg)
                    raise OSError(error_msg)
                
                # Log file size for reference
                if file_size > 1024 * 1024:  # > 1MB
                    logger.info(f"Large export file created ({file_size / 1024 / 1024:.1f}MB): {output_path}")
                else:
                    logger.debug(f"Export file size: {file_size} bytes")
                    
            except OSError as e:
                logger.warning(f"Could not verify export file size: {e}")
            
            # Log export statistics
            logger.info(f"Successfully exported sample '{sample_group.name}' to {output_path}")
            logger.info(f"Export contains {len(analysis_df)} time points and {len(analysis_df.columns)} cells")
            
            return output_path
            
        except (ValueError, PermissionError, OSError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error_msg = f"Unexpected error exporting sample '{sample_group.name}': {type(e).__name__}: {e}"
            logger.error(error_msg)
            raise OSError(error_msg) from e
    
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