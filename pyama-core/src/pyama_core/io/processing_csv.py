"""
Processing CSV format definitions for PyAMA sample data.

This module defines utilities for handling CSV files consumed by the
processing module. The format includes FOV information, cell tracking data,
and extracted features.

Format: fov, cell, frame, time, good, position_x, position_y, and dynamic feature columns
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd


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
    basic_cols = ["fov", "cell", "frame", "time", "good", "position_x", "position_y"]
    feature_cols = [col for col in df.columns if col not in basic_cols]
    
    # Sort by time
    cell_df = cell_df.sort_values("time")
    
    # Create result dataframe
    result_df = pd.DataFrame({"time": cell_df["time"]})
    
    # Add feature columns
    for feature in feature_cols:
        result_df[feature] = cell_df[feature].values
    
    return result_df


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
    result_df = pd.DataFrame({
        "frame": cell_df["frame"].values,
        "position_x": cell_df["position_x"].values,
        "position_y": cell_df["position_y"].values
    })
    
    return result_df