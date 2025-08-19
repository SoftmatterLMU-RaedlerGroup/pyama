"""
CSV data loading utilities for time-series fluorescence data.

Handles CSV format where:
- First row: column indices (ignored)
- First column: time in hours
- Remaining columns: one cell per column
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Any


def load_csv_data(csv_path: Path) -> pd.DataFrame:
    """
    Load data from CSV and transform to required long format.
    
    Args:
        csv_path: Path to the CSV file

    Returns:
        DataFrame in long format with columns: cell_id, frame, time, intensity_total
    """
    # Read CSV, skip the first row (column indices)
    df = pd.read_csv(csv_path, skiprows=1, header=None)
    
    # First column is time in hours
    time_hours = df.iloc[:, 0].values
    
    # Remaining columns are cell data
    records = []
    for cell_idx in range(1, df.shape[1]):
        cell_id = f"cell_{cell_idx:03d}"
        intensity = df.iloc[:, cell_idx].values
        
        for frame, (time, intensity_val) in enumerate(zip(time_hours, intensity)):
            records.append({
                'cell_id': cell_id,
                'frame': frame,
                'time': time,
                'intensity_total': intensity_val
            })
            
    return pd.DataFrame(records)


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