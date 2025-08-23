"""
Utilities for fitting trace data from DataFrames.
Bridges between DataFrame format and fitting functions.
"""

import numpy as np
import pandas as pd
from typing import Any, Callable

from pyama_core.analysis.utils.model_fitting import fit_model, FittingResult


def get_trace(df: pd.DataFrame, cell_id: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Extract time and intensity arrays for a specific cell from DataFrame.
    
    Args:
        df: DataFrame with time as index and cells as columns
        cell_id: Cell identifier (0-based indexing)
    
    Returns:
        Tuple of (time_array, intensity_array)
    """
    # Time from index
    time_data = df.index.values
    
    # Cell data from column (cell_id is 0-based, same as DataFrame columns)
    trace_data = df.iloc[:, cell_id].values
    
    return time_data, trace_data


def fit_trace_data(
    df: pd.DataFrame,
    model_type: str,
    cell_id: int,
    progress_callback: Callable | None = None,
    user_params: dict[str, float] | None = None,
    user_bounds: dict[str, tuple[float, float]] | None = None,
    **kwargs
) -> FittingResult:
    """
    Fit a model to trace data for a specific cell.
    
    Args:
        df: DataFrame with time as index and cells as columns
        model_type: Type of model to fit
        cell_id: Cell identifier (0-based)
        progress_callback: Optional callback for progress updates
        user_params: Optional initial parameters for fitting
        user_bounds: Optional parameter bounds for fitting
        **kwargs: Additional parameters (unused, for compatibility)
    
    Returns:
        FittingResult object from fitting
    """
    # Extract time and trace data
    time_data, trace_data = get_trace(df, cell_id)
    
    # Perform fitting
    result = fit_model(
        model_type, 
        time_data, 
        trace_data, 
        user_params=user_params,
        user_bounds=user_bounds
    )
    
    # Call progress callback if provided
    if progress_callback:
        progress_callback(cell_id)
    
    return result