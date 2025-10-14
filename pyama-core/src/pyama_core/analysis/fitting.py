"""
Simplified fitting utilities for trace data analysis.
"""

from dataclasses import asdict, dataclass
from typing import Callable
import numpy as np
import pandas as pd
from scipy import optimize

from .models import get_model, get_types


@dataclass
class FittingResult:
    fitted_params: dict[str, float]
    success: bool
    r_squared: float = 0.0


def analyze_fitting_quality(results_df: pd.DataFrame) -> dict:
    """
    Analyze fitting quality metrics from results DataFrame.

    Args:
        results_df: DataFrame containing fitting results with 'r_squared' column

    Returns:
        Dictionary containing quality metrics
    """
    if results_df is None or "r_squared" not in results_df.columns:
        return {}

    r_squared = pd.to_numeric(results_df["r_squared"], errors="coerce").dropna()
    if r_squared.empty:
        return {}

    good_count = (r_squared > 0.9).sum()
    fair_count = ((r_squared > 0.7) & (r_squared <= 0.9)).sum()
    poor_count = (r_squared <= 0.7).sum()
    total = len(r_squared)

    quality_metrics = {
        "r_squared_values": r_squared.values,
        "cell_indices": list(range(len(r_squared))),
        "colors": [
            "green" if r2 > 0.9 else "orange" if r2 > 0.7 else "red" for r2 in r_squared
        ],
        "good_percentage": (good_count / total) * 100 if total > 0 else 0,
        "fair_percentage": (fair_count / total) * 100 if total > 0 else 0,
        "poor_percentage": (poor_count / total) * 100 if total > 0 else 0,
        "good_count": good_count,
        "fair_count": fair_count,
        "poor_count": poor_count,
        "total_count": total,
    }

    return quality_metrics


def _validate_user_inputs(
    types: dict,
    user_params: dict[str, float] | None,
    user_bounds: dict[str, tuple[float, float]] | None,
) -> None:
    if user_params:
        UserParams = types["UserParams"]
        valid_params = set(UserParams.__annotations__.keys())
        invalid_params = set(user_params.keys()) - valid_params
        if invalid_params:
            raise ValueError(
                f"Invalid parameter names: {invalid_params}. Valid user parameters: {valid_params}"
            )

    if user_bounds:
        UserBounds = types["UserBounds"]
        valid_params = set(UserBounds.__annotations__.keys())
        invalid_params = set(user_bounds.keys()) - valid_params
        if invalid_params:
            raise ValueError(
                f"Invalid parameter names in bounds: {invalid_params}. Valid user parameters: {valid_params}"
            )
        for param_name, bounds in user_bounds.items():
            if not isinstance(bounds, (tuple, list)) or len(bounds) != 2:
                raise ValueError(
                    f"Bounds for {param_name} must be a tuple of (min, max), got {bounds}"
                )
            if bounds[0] >= bounds[1]:
                raise ValueError(
                    f"Invalid bounds for {param_name}: min ({bounds[0]}) must be less than max ({bounds[1]})"
                )


def _clean_data(
    t_data: np.ndarray, y_data: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mask = ~(np.isnan(t_data) | np.isnan(y_data))
    return t_data[mask], y_data[mask], mask


def _param_names_and_init(
    model, user_params: dict[str, float] | None
) -> tuple[list[str], np.ndarray]:
    defaults_dict = asdict(model.DEFAULTS)
    param_names = list(defaults_dict.keys())
    initial_params = defaults_dict
    if user_params:
        initial_params.update(user_params)
    p0 = np.array([initial_params[name] for name in param_names])
    return param_names, p0


def _bounds_arrays(
    model, param_names: list[str], user_bounds: dict[str, tuple[float, float]] | None
) -> tuple[list[float], list[float]]:
    bounds_dict = asdict(model.BOUNDS)
    if user_bounds:
        bounds_dict.update(user_bounds)
    lower_bounds = [bounds_dict[name][0] for name in param_names]
    upper_bounds = [bounds_dict[name][1] for name in param_names]
    return lower_bounds, upper_bounds


def _make_residual_func(
    model, t_clean: np.ndarray, y_clean: np.ndarray, param_names: list[str]
):
    def residual_func(params):
        params_dict = dict(zip(param_names, params))
        params_obj = model.Params(**params_dict)
        y_pred = model.eval(t_clean, params_obj)
        return y_clean - y_pred

    return residual_func


def _compute_r_squared(y_clean: np.ndarray, residuals: np.ndarray) -> float:
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y_clean - np.mean(y_clean)) ** 2))
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return max(0.0, min(1.0, r_squared))


def fit_model(
    model_type: str,
    t_data: np.ndarray,
    y_data: np.ndarray,
    user_params: dict[str, float] | None = None,
    user_bounds: dict[str, tuple[float, float]] | None = None,
) -> FittingResult:
    try:
        model = get_model(model_type.lower())
        types = get_types(model_type.lower())
    except ValueError:
        return FittingResult(fitted_params={}, success=False, r_squared=0.0)

    _validate_user_inputs(types, user_params, user_bounds)

    t_clean, y_clean, mask = _clean_data(t_data, y_data)
    n_valid_points = int(np.sum(mask))
    n_params = len(model.DEFAULTS.__dataclass_fields__)

    if n_valid_points < n_params:
        return FittingResult(
            fitted_params=asdict(model.DEFAULTS), success=False, r_squared=0.0
        )

    param_names, p0 = _param_names_and_init(model, user_params)

    lower_bounds, upper_bounds = _bounds_arrays(model, param_names, user_bounds)

    residual_func = _make_residual_func(model, t_clean, y_clean, param_names)

    try:
        result = optimize.least_squares(
            residual_func,
            p0,
            bounds=(lower_bounds, upper_bounds),
        )

        r_squared = _compute_r_squared(y_clean, result.fun)
        fitted_params = dict(zip(param_names, result.x))
        return FittingResult(
            fitted_params=fitted_params, success=result.success, r_squared=r_squared
        )
    except Exception:
        return FittingResult(
            fitted_params=asdict(model.DEFAULTS), success=False, r_squared=0.0
        )


def get_trace(df: pd.DataFrame, cell_id) -> tuple[np.ndarray, np.ndarray]:
    """
    Extract time and intensity trace data for a specific cell.

    Args:
        df: DataFrame with time as index and cells as columns
        cell_id: Either integer index (for positional access) or string column name

    Returns:
        Tuple of (time_data, trace_data) as numpy arrays
    """
    time_data = df.index.values.astype(np.float64)

    # Handle both integer (positional) and string (column name) access
    if isinstance(cell_id, int):
        # Use positional access for backward compatibility
        trace_data = df.iloc[:, cell_id].values.astype(np.float64)
    else:
        # Use direct column access for string column names
        trace_data = df[cell_id].values.astype(np.float64)

    return time_data, trace_data


def fit_trace_data(
    df: pd.DataFrame,
    model_type: str,
    cell_id,
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
