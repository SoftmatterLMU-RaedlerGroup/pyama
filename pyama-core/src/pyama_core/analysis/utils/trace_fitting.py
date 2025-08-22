"""
Utilities for fitting trace data from DataFrames.
"""

import numpy as np
import pandas as pd
from typing import Callable

from .model_fitting import fit_model, FittingResult


def get_trace(df: pd.DataFrame, cell_id: int) -> tuple[np.ndarray, np.ndarray]:
    time_data = df.index.values.astype(np.float64)
    trace_data = df.iloc[:, cell_id].values.astype(np.float64)
    return time_data, trace_data


def fit_trace_data(
    df: pd.DataFrame,
    model_type: str,
    cell_id: int,
    progress_callback: Callable | None = None,
    user_params: dict[str, float] | None = None,
    user_bounds: dict[str, tuple[float, float]] | None = None,
    **kwargs,
) -> FittingResult:
    time_data, trace_data = get_trace(df, cell_id)
    result = fit_model(
        model_type,
        time_data,
        trace_data,
        user_params=user_params,
        user_bounds=user_bounds,
    )
    if progress_callback:
        progress_callback(cell_id)
    return result


