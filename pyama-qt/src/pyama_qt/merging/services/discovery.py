"""
FOV discovery service for PyAMA merge application.

This module provides functionality to discover and load FOV trace CSV files
from processing output directories, with priority for 'inspected' suffix files.
"""

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict
import re

from pyama_core.io.processing_csv import ProcessingCSVLoader

logger = logging.getLogger(__name__)


@dataclass
class FOVInfo:
    """
    Information about a discovered FOV trace file.
    
    Attributes:
        index: FOV index (0-based)
        cell_count: Number of unique cells in this FOV
        file_path: Path to the CSV file
        has_quality_data: Whether the file contains 'good' column for quality filtering
        frame_count: Number of time points in this FOV
    """
    index: int
    cell_count: int
    file_path: Path
    has_quality_data: bool
    frame_count: int = 0


class FOVDiscoveryService:
    """
    Service for discovering and loading FOV trace CSV files.
    
    Handles automatic discovery of trace files in processing output directories,
    with priority given to files with 'inspected' suffix over regular trace files.
    """
    
    def __init__(self):
        self.csv_loader = ProcessingCSVLoader()
        
    def discover_fov_files(self, output_dir: Path) -> List[FOVInfo]:
        """
        Discover all FOV trace CSV files in the given output directory.
        
        Args:
            output_dir: Path to processing output directory
            
        Returns:
            List of FOVInfo objects sorted by FOV index
            
        Raises:
            FileNotFoundError: If output directory doesn't exist
            ValueError: If no valid trace files are found
            PermissionError: If directory cannot be accessed
        """
        # Validate directory existence and accessibility
        if not output_dir.exists():
            logger.error(f"Output directory does not exist: {output_dir}")
            raise FileNotFoundError(f"Output directory not found: {output_dir}")
            
        if not output_dir.is_dir():
            logger.error(f"Path is not a directory: {output_dir}")
            raise ValueError(f"Path is not a directory: {output_dir}")
            
        # Test directory accessibility
        try:
            list(output_dir.iterdir())
        except PermissionError as e:
            logger.error(f"Permission denied accessing directory {output_dir}: {e}")
            raise PermissionError(f"Cannot access directory {output_dir}: {e}")
        except OSError as e:
            logger.error(f"OS error accessing directory {output_dir}: {e}")
            raise ValueError(f"Cannot access directory {output_dir}: {e}")
            
        logger.info(f"Discovering FOV files in {output_dir}")
        
        # Find all CSV files that match trace file patterns
        try:
            trace_files = self._find_trace_files(output_dir)
            logger.debug(f"Found {len(trace_files)} potential trace files")
        except Exception as e:
            logger.error(f"Error searching for trace files in {output_dir}: {e}")
            raise ValueError(f"Failed to search for trace files: {e}")
        
        if not trace_files:
            logger.warning(f"No trace CSV files found in {output_dir}")
            # List available CSV files for debugging
            try:
                csv_files = list(output_dir.glob('*.csv'))
                if csv_files:
                    logger.info(f"Found {len(csv_files)} CSV files, but none match trace file pattern:")
                    for csv_file in csv_files[:10]:  # Show first 10 files
                        logger.info(f"  - {csv_file.name}")
                    if len(csv_files) > 10:
                        logger.info(f"  ... and {len(csv_files) - 10} more")
                else:
                    logger.info("No CSV files found in directory")
            except Exception as e:
                logger.warning(f"Could not list CSV files for debugging: {e}")
                
            raise ValueError(f"No trace CSV files found in {output_dir}. Expected files matching pattern '*_fov####_traces*.csv'")
            
        # Prioritize inspected files over regular trace files
        try:
            prioritized_files = self._prioritize_inspected_files(trace_files)
            logger.info(f"Prioritized {len(prioritized_files)} files from {len(trace_files)} candidates")
        except Exception as e:
            logger.error(f"Error prioritizing trace files: {e}")
            raise ValueError(f"Failed to prioritize trace files: {e}")
        
        # Load metadata for each file with detailed error tracking
        fov_infos = []
        load_errors = []
        corrupted_files = []
        
        for file_path in prioritized_files:
            try:
                fov_info = self.load_fov_metadata(file_path)
                fov_infos.append(fov_info)
                logger.debug(f"Loaded FOV {fov_info.index}: {fov_info.cell_count} cells, {fov_info.frame_count} frames")
            except FileNotFoundError as e:
                error_msg = f"File not found: {file_path}"
                logger.warning(error_msg)
                load_errors.append(error_msg)
            except PermissionError as e:
                error_msg = f"Permission denied reading {file_path}: {e}"
                logger.warning(error_msg)
                load_errors.append(error_msg)
            except pd.errors.EmptyDataError:
                error_msg = f"Empty or corrupted CSV file: {file_path}"
                logger.warning(error_msg)
                corrupted_files.append(str(file_path))
                load_errors.append(error_msg)
            except pd.errors.ParserError as e:
                error_msg = f"CSV parsing error in {file_path}: {e}"
                logger.warning(error_msg)
                corrupted_files.append(str(file_path))
                load_errors.append(error_msg)
            except ValueError as e:
                error_msg = f"Invalid data format in {file_path}: {e}"
                logger.warning(error_msg)
                corrupted_files.append(str(file_path))
                load_errors.append(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error loading {file_path}: {e}"
                logger.error(error_msg)
                load_errors.append(error_msg)
                
        # Report summary of loading issues
        if load_errors:
            logger.warning(f"Encountered {len(load_errors)} errors while loading FOV files:")
            for error in load_errors[:5]:  # Show first 5 errors
                logger.warning(f"  - {error}")
            if len(load_errors) > 5:
                logger.warning(f"  ... and {len(load_errors) - 5} more errors")
                
        if corrupted_files:
            logger.error(f"Found {len(corrupted_files)} corrupted or invalid CSV files:")
            for corrupted_file in corrupted_files[:5]:
                logger.error(f"  - {corrupted_file}")
            if len(corrupted_files) > 5:
                logger.error(f"  ... and {len(corrupted_files) - 5} more corrupted files")
                
        if not fov_infos:
            error_msg = f"No valid trace files could be loaded from {output_dir}"
            if load_errors:
                error_msg += f". Encountered {len(load_errors)} loading errors."
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Sort by FOV index and validate continuity
        fov_infos.sort(key=lambda x: x.index)
        
        # Check for data consistency issues
        consistency_warnings = self._validate_fov_consistency(fov_infos)
        for warning in consistency_warnings:
            logger.warning(warning)
        
        total_cells = sum(f.cell_count for f in fov_infos)
        logger.info(f"Successfully discovered {len(fov_infos)} FOV files with {total_cells} total cells")
        
        if load_errors:
            logger.info(f"Note: {len(load_errors)} files could not be loaded due to errors")
            
        return fov_infos
    
    def load_fov_metadata(self, csv_path: Path) -> FOVInfo:
        """
        Load metadata from a single FOV trace CSV file.
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            FOVInfo object with extracted metadata
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file cannot be read
            ValueError: If file format is invalid
            Exception: For other unexpected errors
        """
        try:
            # Validate file exists and is readable
            if not csv_path.exists():
                raise FileNotFoundError(f"CSV file not found: {csv_path}")
                
            if not csv_path.is_file():
                raise ValueError(f"Path is not a file: {csv_path}")
                
            # Check file size (empty files or extremely large files might be problematic)
            try:
                file_size = csv_path.stat().st_size
                if file_size == 0:
                    raise ValueError(f"CSV file is empty: {csv_path}")
                elif file_size > 100 * 1024 * 1024:  # 100MB threshold
                    logger.warning(f"Large CSV file detected ({file_size / 1024 / 1024:.1f}MB): {csv_path}")
            except OSError as e:
                logger.warning(f"Could not check file size for {csv_path}: {e}")
            
            # Load metadata using the CSV loader
            metadata = self.csv_loader.get_fov_metadata(csv_path)
            
            # Validate metadata completeness
            required_keys = ['fov_index', 'cell_count', 'has_quality_data', 'frame_count', 'file_path']
            missing_keys = [key for key in required_keys if key not in metadata]
            if missing_keys:
                raise ValueError(f"Incomplete metadata from {csv_path}: missing {missing_keys}")
            
            # Validate metadata values
            if metadata['cell_count'] < 0:
                raise ValueError(f"Invalid cell count ({metadata['cell_count']}) in {csv_path}")
            if metadata['frame_count'] < 0:
                raise ValueError(f"Invalid frame count ({metadata['frame_count']}) in {csv_path}")
            if metadata['fov_index'] < 0:
                raise ValueError(f"Invalid FOV index ({metadata['fov_index']}) in {csv_path}")
                
            # Warn about potential data quality issues
            if metadata['cell_count'] == 0:
                logger.warning(f"FOV {metadata['fov_index']} has no cells: {csv_path}")
            elif metadata['cell_count'] > 1000:
                logger.warning(f"FOV {metadata['fov_index']} has unusually high cell count ({metadata['cell_count']}): {csv_path}")
                
            if metadata['frame_count'] == 0:
                logger.warning(f"FOV {metadata['fov_index']} has no time points: {csv_path}")
            elif metadata['frame_count'] < 10:
                logger.warning(f"FOV {metadata['fov_index']} has very few time points ({metadata['frame_count']}): {csv_path}")
            
            return FOVInfo(
                index=metadata['fov_index'],
                cell_count=metadata['cell_count'],
                file_path=metadata['file_path'],
                has_quality_data=metadata['has_quality_data'],
                frame_count=metadata['frame_count']
            )
            
        except (FileNotFoundError, PermissionError, ValueError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected exceptions with more context
            logger.error(f"Unexpected error loading metadata from {csv_path}: {type(e).__name__}: {e}")
            raise ValueError(f"Failed to load metadata from {csv_path}: {e}") from e
    
    def _find_trace_files(self, output_dir: Path) -> List[Path]:
        """
        Find all CSV files that match trace file naming patterns.
        
        Expected patterns:
        - {base_name}_fov{index:04d}_traces.csv
        - {base_name}_fov{index:04d}_traces_inspected.csv
        
        Args:
            output_dir: Directory to search
            
        Returns:
            List of CSV file paths
        """
        trace_files = []
        
        # Pattern for trace files: *_fov####_traces*.csv
        trace_pattern = re.compile(r'.*_fov\d{4}_traces.*\.csv$')
        
        # Search both in root directory and FOV subdirectories
        for csv_file in output_dir.glob('**/*.csv'):
            if trace_pattern.match(csv_file.name):
                trace_files.append(csv_file)
                
        logger.debug(f"Found {len(trace_files)} potential trace files")
        return trace_files
    
    def _prioritize_inspected_files(self, files: List[Path]) -> List[Path]:
        """
        Prioritize files with 'inspected' suffix over regular trace files.
        
        For each FOV, if both regular and inspected versions exist,
        only the inspected version is included in the result.
        
        Args:
            files: List of trace file paths
            
        Returns:
            List of prioritized file paths
        """
        # Group files by FOV index
        fov_files: Dict[int, Dict[str, Path]] = {}
        
        fov_pattern = re.compile(r'.*_fov(\d{4})_traces(_inspected)?\.csv$')
        
        for file_path in files:
            match = fov_pattern.match(file_path.name)
            if match:
                fov_index = int(match.group(1))
                is_inspected = match.group(2) is not None
                
                if fov_index not in fov_files:
                    fov_files[fov_index] = {}
                    
                file_type = 'inspected' if is_inspected else 'regular'
                fov_files[fov_index][file_type] = file_path
        
        # Select prioritized files
        prioritized = []
        for fov_index, file_types in fov_files.items():
            if 'inspected' in file_types:
                prioritized.append(file_types['inspected'])
                if 'regular' in file_types:
                    logger.debug(f"FOV {fov_index}: Using inspected file over regular file")
            elif 'regular' in file_types:
                prioritized.append(file_types['regular'])
                
        logger.info(f"Prioritized {len(prioritized)} files from {len(files)} candidates")
        return prioritized
    
    def validate_fov_continuity(self, fov_infos: List[FOVInfo]) -> bool:
        """
        Validate that FOV indices are continuous starting from 0.
        
        Args:
            fov_infos: List of FOVInfo objects
            
        Returns:
            True if FOV indices are continuous, False otherwise
        """
        if not fov_infos:
            return True
            
        indices = [fov.index for fov in fov_infos]
        expected_indices = list(range(len(indices)))
        
        if indices != expected_indices:
            logger.warning(f"FOV indices are not continuous: {indices}")
            return False
            
        return True
    
    def _validate_fov_consistency(self, fov_infos: List[FOVInfo]) -> List[str]:
        """
        Validate consistency across discovered FOV files.
        
        Args:
            fov_infos: List of FOVInfo objects to validate
            
        Returns:
            List of warning messages about inconsistencies
        """
        warnings = []
        
        if not fov_infos:
            return warnings
            
        # Check FOV index continuity
        indices = [fov.index for fov in fov_infos]
        expected_indices = list(range(len(indices)))
        
        if indices != expected_indices:
            missing_indices = set(expected_indices) - set(indices)
            if missing_indices:
                warnings.append(f"Missing FOV indices: {sorted(missing_indices)}")
            
            gaps = []
            for i in range(1, len(indices)):
                if indices[i] != indices[i-1] + 1:
                    gaps.append(f"{indices[i-1]}-{indices[i]}")
            if gaps:
                warnings.append(f"Non-continuous FOV indices detected: gaps at {', '.join(gaps)}")
        
        # Check for consistent frame counts (time points)
        frame_counts = [fov.frame_count for fov in fov_infos if fov.frame_count > 0]
        if frame_counts:
            unique_frame_counts = set(frame_counts)
            if len(unique_frame_counts) > 1:
                warnings.append(f"Inconsistent frame counts across FOVs: {sorted(unique_frame_counts)}")
                
            # Check for extremely different frame counts
            min_frames = min(frame_counts)
            max_frames = max(frame_counts)
            if max_frames > 0 and min_frames / max_frames < 0.8:  # More than 20% difference
                warnings.append(f"Large variation in frame counts: {min_frames} to {max_frames}")
        
        # Check for consistent quality data availability
        has_quality = [fov.has_quality_data for fov in fov_infos]
        if not all(has_quality) and any(has_quality):
            with_quality = sum(has_quality)
            total = len(has_quality)
            warnings.append(f"Inconsistent quality data: {with_quality}/{total} files have quality filtering")
        
        # Check for unusual cell count distributions
        cell_counts = [fov.cell_count for fov in fov_infos if fov.cell_count > 0]
        if cell_counts:
            avg_cells = sum(cell_counts) / len(cell_counts)
            outliers = [fov.index for fov in fov_infos 
                       if fov.cell_count > 0 and abs(fov.cell_count - avg_cells) > 2 * avg_cells]
            if outliers:
                warnings.append(f"FOVs with unusual cell counts (>2x average): {outliers}")
        
        # Check for empty FOVs
        empty_fovs = [fov.index for fov in fov_infos if fov.cell_count == 0]
        if empty_fovs:
            warnings.append(f"FOVs with no cells: {empty_fovs}")
            
        return warnings
    
    def get_summary_stats(self, fov_infos: List[FOVInfo]) -> Dict[str, int]:
        """
        Get summary statistics for discovered FOV files.
        
        Args:
            fov_infos: List of FOVInfo objects
            
        Returns:
            Dictionary with summary statistics
        """
        if not fov_infos:
            return {
                'total_fovs': 0,
                'total_cells': 0,
                'files_with_quality_data': 0,
                'min_cells_per_fov': 0,
                'max_cells_per_fov': 0,
                'avg_cells_per_fov': 0,
                'min_frames_per_fov': 0,
                'max_frames_per_fov': 0,
                'avg_frames_per_fov': 0
            }
            
        cell_counts = [fov.cell_count for fov in fov_infos]
        frame_counts = [fov.frame_count for fov in fov_infos if fov.frame_count > 0]
        
        stats = {
            'total_fovs': len(fov_infos),
            'total_cells': sum(cell_counts),
            'files_with_quality_data': sum(1 for fov in fov_infos if fov.has_quality_data),
            'min_cells_per_fov': min(cell_counts) if cell_counts else 0,
            'max_cells_per_fov': max(cell_counts) if cell_counts else 0,
            'avg_cells_per_fov': int(sum(cell_counts) / len(cell_counts)) if cell_counts else 0
        }
        
        if frame_counts:
            stats.update({
                'min_frames_per_fov': min(frame_counts),
                'max_frames_per_fov': max(frame_counts),
                'avg_frames_per_fov': int(sum(frame_counts) / len(frame_counts))
            })
        else:
            stats.update({
                'min_frames_per_fov': 0,
                'max_frames_per_fov': 0,
                'avg_frames_per_fov': 0
            })
            
        return stats