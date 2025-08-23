"""
CSV data loading utilities for time-series fluorescence data.

Handles CSV format where:
- No header row
- First column: time in hours
- Remaining columns: one cell per column
"""

import pandas as pd
from pathlib import Path
from typing import List


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """
    Load data from CSV file.
    
    The CSV is expected to have no header, time as the first column (used as index),
    and each subsequent column representing a single cell's data.

    Args:
        csv_path: Path to the CSV file

    Returns:
        DataFrame with time as index and cells as columns
    """
    # Read CSV, no header, use first column as index
    df = pd.read_csv(csv_path, header=None, index_col=0)
    offset = df.iloc[:10, :].values.mean(axis=0)
    df = df - offset
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