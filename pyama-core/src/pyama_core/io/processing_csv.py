"""
Processing CSV format definitions for PyAMA sample data.

This module defines utilities for handling CSV files consumed by the
processing module. The format includes FOV information, cell tracking data,
and extracted features.

Format: fov, cell, frame, time, good, position_x, position_y, and dynamic feature columns
"""

from pathlib import Path
import pandas as pd

# Import Result class for field definitions
from pyama_core.processing.extraction.trace import Result


def get_dataframe(csv_path: Path) -> pd.DataFrame:
    """
    Get the dataframe from a processing CSV file.

    Args:
        csv_path: Path to the processing CSV file

    Returns:
        DataFrame with the processing data
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        raise ValueError(f"Failed to read CSV file: {exc}") from exc

    if df.empty:
        raise ValueError(f"CSV file is empty: {csv_path}")

    return df


def extract_cell_quality_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract a dataframe with cell quality information.

    Args:
        df: Processing DataFrame

    Returns:
        DataFrame with columns 'cell' and 'good'
    """
    if "cell" not in df.columns or "good" not in df.columns:
        raise ValueError("DataFrame must contain 'cell' and 'good' columns")

    # Get unique cells and their quality status
    cell_quality = df.groupby("cell")["good"].first().reset_index()
    cell_quality["cell"] = cell_quality["cell"].astype(int)

    return cell_quality[["cell", "good"]]


def extract_cell_feature_dataframe(df: pd.DataFrame, cell_id: int) -> pd.DataFrame:
    """
    Extract a dataframe with time series features for a specific cell.

    Args:
        df: Processing DataFrame
        cell_id: Cell ID to extract data for

    Returns:
        DataFrame with columns 'time' and feature columns
    """
    # Filter data for the specific cell
    cell_df = df[df["cell"] == cell_id].copy()

    if cell_df.empty:
        raise ValueError(f"Cell ID {cell_id} not found in DataFrame")

    # Get available features (exclude basic columns)
    basic_cols = [f.name for f in Result.__dataclass_fields__.values()]
    feature_cols = [col for col in df.columns if col not in basic_cols]

    # Sort by time
    cell_df = cell_df.sort_values("time")

    # Create result dataframe
    result_df = pd.DataFrame({"time": cell_df["time"]})

    # Add feature columns
    for feature in feature_cols:
        result_df[feature] = cell_df[feature].values

    return result_df


def write_dataframe(df: pd.DataFrame, csv_path: Path, **kwargs) -> None:
    """
    Write a DataFrame to a CSV file.

    Args:
        df: DataFrame to write
        csv_path: Path to the output CSV file
        **kwargs: Additional arguments passed to pandas.to_csv()
    """
    if df.empty:
        raise ValueError("Cannot write empty DataFrame to CSV")

    try:
        # Ensure parent directory exists
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to CSV with default settings optimized for processing format
        df.to_csv(csv_path, index=False, **kwargs)
    except Exception as exc:
        raise ValueError(f"Failed to write CSV file: {exc}") from exc


def update_cell_quality(df: pd.DataFrame, quality_df: pd.DataFrame) -> pd.DataFrame:
    """
    Update the 'good' column in a DataFrame based on an updated cell quality DataFrame.

    Args:
        df: Original processing DataFrame
        quality_df: DataFrame with updated cell quality information containing 'cell' and 'good' columns

    Returns:
        Updated DataFrame with modified 'good' column
    """
    if "cell" not in df.columns or "good" not in df.columns:
        raise ValueError("Original DataFrame must contain 'cell' and 'good' columns")

    if "cell" not in quality_df.columns or "good" not in quality_df.columns:
        raise ValueError("Quality DataFrame must contain 'cell' and 'good' columns")

    # Create a copy to avoid modifying the original
    updated_df = df.copy()

    # Create a mapping from cell ID to quality status
    quality_map = dict(zip(quality_df["cell"], quality_df["good"]))

    # Update the 'good' column based on the mapping
    updated_df["good"] = updated_df["cell"].map(quality_map).fillna(updated_df["good"])

    return updated_df


def extract_cell_position_dataframe(df: pd.DataFrame, cell_id: int) -> pd.DataFrame:
    """
    Extract a dataframe with position data for a specific cell.

    Args:
        df: Processing DataFrame
        cell_id: Cell ID to extract data for

    Returns:
        DataFrame with columns 'frame', 'position_x', 'position_y'
    """
    # Filter data for the specific cell
    cell_df = df[df["cell"] == cell_id].copy()

    if cell_df.empty:
        raise ValueError(f"Cell ID {cell_id} not found in DataFrame")

    # Sort by frame
    cell_df = cell_df.sort_values("frame")

    # Create result dataframe
    result_df = pd.DataFrame(
        {
            "frame": cell_df["frame"].values,
            "position_x": cell_df["position_x"].values,
            "position_y": cell_df["position_y"].values,
        }
    )

    return result_df
