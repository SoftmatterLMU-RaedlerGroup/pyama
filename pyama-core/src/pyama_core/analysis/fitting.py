'''
Simplified fitting utilities for trace data analysis.
'''

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Callable
from scipy import optimize

from pyama_core.analysis.models import get_model, get_types


@dataclass
class FittingResult:
    fitted_params: dict[str, float]
    success: bool
    r_squared: float = 0.0


def _validate_user_inputs(
    types: dict,
    user_params: dict[str, float] | None,
    user_bounds: dict[str, tuple[float, float]] | None,
) -> None:
    if user_params:
        UserParams = types['UserParams']
        valid_params = set(UserParams.__annotations__.keys())
        invalid_params = set(user_params.keys()) - valid_params
        if invalid_params:
            raise ValueError(
                f"Invalid parameter names: {invalid_params}. Valid user parameters: {valid_params}"
            )

    if user_bounds:
        UserBounds = types['UserBounds']
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
    param_names = list(model.DEFAULTS.keys())
    initial_params = model.DEFAULTS.copy()
    if user_params:
        initial_params.update(user_params)
    p0 = np.array([initial_params[name] for name in param_names])
    return param_names, p0


def _bounds_arrays(
    model, param_names: list[str], user_bounds: dict[str, tuple[float, float]] | None
) -> tuple[list[float], list[float]]:
    bounds_dict = model.BOUNDS.copy()
    if user_bounds:
        bounds_dict.update(user_bounds)
    lower_bounds = [bounds_dict[name][0] for name in param_names]
    upper_bounds = [bounds_dict[name][1] for name in param_names]
    return lower_bounds, upper_bounds


def _make_residual_func(model, t_clean: np.ndarray, y_clean: np.ndarray, param_names: list[str]):
    def residual_func(params):
        params_dict = dict(zip(param_names, params))
        y_pred = model.eval(t_clean, params_dict)
        return y_clean - y_pred
    return residual_func


def _compute_r_squared(y_clean: np.ndarray, residuals: np.ndarray) -> float:
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y_clean - np.mean(y_clean))**2))
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
    n_params = len(model.DEFAULTS)

    if n_valid_points < n_params:
        return FittingResult(fitted_params=model.DEFAULTS, success=False, r_squared=0.0)

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
        return FittingResult(fitted_params=fitted_params, success=result.success, r_squared=r_squared)
    except Exception:
        return FittingResult(fitted_params=model.DEFAULTS, success=False, r_squared=0.0)


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
