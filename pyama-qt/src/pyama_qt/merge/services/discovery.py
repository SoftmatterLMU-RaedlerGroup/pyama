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
        """
        if not output_dir.exists():
            raise FileNotFoundError(f"Output directory not found: {output_dir}")
            
        if not output_dir.is_dir():
            raise ValueError(f"Path is not a directory: {output_dir}")
            
        logger.info(f"Discovering FOV files in {output_dir}")
        
        # Find all CSV files that match trace file patterns
        trace_files = self._find_trace_files(output_dir)
        
        if not trace_files:
            raise ValueError(f"No trace CSV files found in {output_dir}")
            
        # Prioritize inspected files over regular trace files
        prioritized_files = self._prioritize_inspected_files(trace_files)
        
        # Load metadata for each file
        fov_infos = []
        for file_path in prioritized_files:
            try:
                fov_info = self.load_fov_metadata(file_path)
                fov_infos.append(fov_info)
                logger.debug(f"Loaded FOV {fov_info.index}: {fov_info.cell_count} cells")
            except Exception as e:
                logger.warning(f"Failed to load metadata from {file_path}: {e}")
                continue
                
        if not fov_infos:
            raise ValueError(f"No valid trace files could be loaded from {output_dir}")
            
        # Sort by FOV index
        fov_infos.sort(key=lambda x: x.index)
        
        logger.info(f"Discovered {len(fov_infos)} FOV files with {sum(f.cell_count for f in fov_infos)} total cells")
        return fov_infos
    
    def load_fov_metadata(self, csv_path: Path) -> FOVInfo:
        """
        Load metadata from a single FOV trace CSV file.
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            FOVInfo object with extracted metadata
            
        Raises:
            Exception: If file cannot be loaded or is invalid
        """
        metadata = self.csv_loader.get_fov_metadata(csv_path)
        
        return FOVInfo(
            index=metadata['fov_index'],
            cell_count=metadata['cell_count'],
            file_path=metadata['file_path'],
            has_quality_data=metadata['has_quality_data'],
            frame_count=metadata['frame_count']
        )
    
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
        
        for csv_file in output_dir.glob('*.csv'):
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
                'avg_cells_per_fov': 0
            }
            
        cell_counts = [fov.cell_count for fov in fov_infos]
        
        return {
            'total_fovs': len(fov_infos),
            'total_cells': sum(cell_counts),
            'files_with_quality_data': sum(1 for fov in fov_infos if fov.has_quality_data),
            'min_cells_per_fov': min(cell_counts),
            'max_cells_per_fov': max(cell_counts),
            'avg_cells_per_fov': int(sum(cell_counts) / len(cell_counts))
        }