"""
CSV data loading utilities for time-series fluorescence data.

Handles CSV format where:
- Time as index (first column)
- Sequential cell IDs as columns (0, 1, 2, 3...)
- Compatible with AnalysisCSVWriter format
"""

import pandas as pd
from pathlib import Path
from typing import List
from pyama_core.io.analysis_csv import AnalysisCSVWriter


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """
    Load data from analysis CSV file using AnalysisCSVWriter.
    
    The CSV is expected to have time as index and sequential cell IDs as columns.

    Args:
        csv_path: Path to the CSV file

    Returns:
        DataFrame with time as index and cells as columns
    """
    # Use AnalysisCSVWriter to load and validate the format
    writer = AnalysisCSVWriter()
    df = writer.load_analysis_csv(csv_path)
    return df


def discover_csv_files(data_path: Path | str) -> List[Path]:
    """
    Discover CSV files for analysis.

    Args:
        data_path: Path to a CSV file or directory containing CSV files

    Returns:
        List of CSV file paths
    """
    data_path = Path(data_path)
    csv_files = []

    if data_path.is_file() and data_path.suffix.lower() == ".csv":
        csv_files.append(data_path)
    elif data_path.is_dir():
        csv_files.extend(data_path.glob("*.csv"))

    return [f for f in csv_files if "_fitted" not in f.name and "_traces" not in f.name]