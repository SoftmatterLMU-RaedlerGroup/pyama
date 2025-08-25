"""
Utilities for fitting trace data from DataFrames.
"""

from typing import Callable

import pandas as pd

from .model_fitting import fit_model, FittingResult
from .load_data import get_trace


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


