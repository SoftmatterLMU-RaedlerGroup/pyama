"""
Analysis CSV format definitions for PyAMA sample data.

This module defines the data structures and utilities for handling CSV files
consumed by the analysis module. The format uses time as index and cells as columns.

Format: time (hours) as index, cell IDs (0,1,2,3...) as columns
"""

import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class AnalysisCSVWriter:
    """
    Writer for analysis CSV files containing sample-level trace data.
    
    Handles writing and validation of CSV files for the analysis module.
    Expected format: time (hours) as index, sequential cell IDs as columns
    """
    
    def write_sample_data(self, df: pd.DataFrame, output_path: Path) -> None:
        """
        Write sample data to analysis CSV format.
        
        Args:
            df: DataFrame with time as index and cell IDs as columns
            output_path: Path where to save the CSV file
            
        Raises:
            ValueError: If the DataFrame format is invalid
            IOError: If the file cannot be written
        """
        if not self.validate_format(df):
            raise ValueError("Invalid DataFrame format for analysis CSV")
            
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write CSV with time as index and cell IDs as column headers
            df.to_csv(output_path, index=True, header=True)
            
            logger.info(f"Wrote analysis CSV with {len(df)} time points and {len(df.columns)} cells to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to write analysis CSV to {output_path}: {e}")
            raise IOError(f"Could not write file {output_path}: {e}")
    
    def validate_format(self, df: pd.DataFrame) -> bool:
        """
        Validate that the DataFrame has the expected analysis CSV format.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            True if format is valid, False otherwise
        """
        # Check that index represents time (should be numeric)
        if not pd.api.types.is_numeric_dtype(df.index):
            logger.error("Index must be numeric (time values)")
            return False
            
        # Check that column names are sequential integers starting from 0
        expected_columns = list(range(len(df.columns)))
        if not all(isinstance(col, (int, str)) for col in df.columns):
            logger.error("Column names must be integers or string representations of integers")
            return False
            
        # Convert string column names to integers for validation
        try:
            actual_columns = [int(col) for col in df.columns]
            if actual_columns != expected_columns:
                logger.error(f"Column names must be sequential integers starting from 0. Expected: {expected_columns}, Got: {actual_columns}")
                return False
        except ValueError:
            logger.error("Column names must be convertible to integers")
            return False
            
        # Check that all data is numeric
        for col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                logger.error(f"Column {col} contains non-numeric data")
                return False
                
        # Check for reasonable time values (should be positive and increasing)
        if len(df) > 1:
            time_diff = df.index.diff().dropna()
            if (time_diff <= 0).any():
                logger.warning("Time values should be strictly increasing")
                
        return True
    
    def create_analysis_dataframe(self, time_values: List[float], cell_data: Dict[int, List[float]]) -> pd.DataFrame:
        """
        Create a properly formatted analysis DataFrame.
        
        Args:
            time_values: List of time points in hours
            cell_data: Dictionary mapping cell IDs to intensity values
            
        Returns:
            DataFrame formatted for analysis CSV
        """
        # Ensure cell IDs are sequential starting from 0
        max_cell_id = max(cell_data.keys()) if cell_data else -1
        expected_cell_ids = list(range(max_cell_id + 1))
        
        # Create DataFrame with time as index
        df_data = {}
        for cell_id in expected_cell_ids:
            if cell_id in cell_data:
                df_data[cell_id] = cell_data[cell_id]
            else:
                # Fill missing cell IDs with NaN
                df_data[cell_id] = [float('nan')] * len(time_values)
                logger.warning(f"Cell ID {cell_id} missing, filled with NaN")
        
        df = pd.DataFrame(df_data, index=time_values)
        df.index.name = 'time'
        
        return df
    
    def load_analysis_csv(self, csv_path: Path) -> pd.DataFrame:
        """
        Load an existing analysis CSV file.
        
        Args:
            csv_path: Path to the analysis CSV file
            
        Returns:
            DataFrame with analysis data
            
        Raises:
            FileNotFoundError: If the CSV file doesn't exist
            ValueError: If the CSV format is invalid
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"Analysis CSV file not found: {csv_path}")
            
        try:
            df = pd.read_csv(csv_path, index_col=0)
            
            if not self.validate_format(df):
                raise ValueError(f"Invalid analysis CSV format in {csv_path}")
                
            logger.info(f"Loaded analysis CSV with {len(df)} time points and {len(df.columns)} cells from {csv_path}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load analysis CSV file {csv_path}: {e}")
            raise
    
    def get_sample_statistics(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Extract statistics from an analysis DataFrame.
        
        Args:
            df: Analysis DataFrame
            
        Returns:
            Dictionary with sample statistics
        """
        stats = {
            'time_points': len(df),
            'cell_count': len(df.columns),
            'duration_hours': df.index.max() - df.index.min() if len(df) > 1 else 0,
            'time_interval': df.index.to_series().diff().median() if len(df) > 1 else 0,
            'missing_values': df.isnull().sum().sum(),
            'complete_traces': (df.isnull().sum() == 0).sum()
        }
        
        return stats


def validate_analysis_csv_compatibility(df: pd.DataFrame) -> List[str]:
    """
    Validate that a DataFrame is compatible with analysis module requirements.
    
    Args:
        df: DataFrame to validate
        
    Returns:
        List of validation warnings/errors (empty if valid)
    """
    issues = []
    
    # Check minimum requirements
    if len(df) < 2:
        issues.append("Analysis requires at least 2 time points")
        
    if len(df.columns) < 1:
        issues.append("Analysis requires at least 1 cell")
        
    # Check for excessive missing data
    missing_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
    if missing_ratio > 0.5:
        issues.append(f"High proportion of missing data: {missing_ratio:.1%}")
        
    # Check time intervals
    if len(df) > 1:
        time_intervals = df.index.diff().dropna()
        if time_intervals.std() / time_intervals.mean() > 0.1:
            issues.append("Irregular time intervals detected")
            
    return issues