"""
Core fitting utilities using scipy optimization.

Provides parameter estimation using single-start optimization.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize, OptimizeResult
from typing import Dict, Tuple, List, Callable
import warnings

from ..models.base import ModelBase, FittingResult


def calculate_r_squared(y_observed: np.ndarray, y_predicted: np.ndarray) -> float:
    """
    Calculate coefficient of determination (R²).

    Args:
        y_observed: Observed data values
        y_predicted: Model predictions

    Returns:
        R² value between 0 and 1
    """
    # Remove NaN values for calculation
    mask = ~(np.isnan(y_observed) | np.isnan(y_predicted))
    if np.sum(mask) < 2:
        return 0.0

    y_obs = y_observed[mask]
    y_pred = y_predicted[mask]

    ss_res = np.sum((y_obs - y_pred) ** 2)
    ss_tot = np.sum((y_obs - np.mean(y_obs)) ** 2)

    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0

    r_squared = 1 - (ss_res / ss_tot)
    return max(0.0, min(1.0, r_squared))  # Clamp to [0, 1]


def create_objective_function(
    model: ModelBase,
    t_data: np.ndarray,
    y_data: np.ndarray,
    param_names: List[str],
    fixed_params: Dict[str, float],
) -> Callable[[np.ndarray], float]:
    """
    Create objective function for optimization.

    Args:
        model: Model instance
        t_data: Time points
        y_data: Observed fluorescence values
        param_names: Names of parameters being optimized
        fixed_params: Fixed parameter values

    Returns:
        Objective function that takes parameter array and returns SSE
    """
    # Remove NaN values from data
    mask = ~(np.isnan(t_data) | np.isnan(y_data))
    t_clean = t_data[mask]
    y_clean = y_data[mask]

    if len(t_clean) < 2:
        # Not enough data points
        def empty_objective(params):
            return 1e6

        return empty_objective

    def objective(param_array: np.ndarray) -> float:
        """Objective function: sum of squared residuals."""
        try:
            # Build complete parameter dictionary
            params = fixed_params.copy()
            for i, name in enumerate(param_names):
                params[name] = param_array[i]

            # Evaluate model
            y_pred = model.evaluate(t_clean, **params)

            # Check for invalid predictions
            if np.any(~np.isfinite(y_pred)):
                return 1e6

            # Sum of squared errors
            residuals = y_clean - y_pred
            sse = np.sum(residuals**2)

            return sse

        except Exception:
            # Return large value for any evaluation errors
            return 1e6

    return objective


def fit_single_start(
    model: ModelBase,
    t_data: np.ndarray,
    y_data: np.ndarray,
    initial_params: Dict[str, float],
    method: str = "L-BFGS-B",
) -> Tuple[FittingResult, OptimizeResult]:
    """
    Perform single-start optimization.

    Args:
        model: Model instance
        t_data: Time points
        y_data: Observed values
        initial_params: Initial parameter guess
        method: Optimization method

    Returns:
        Tuple of (FittingResult, scipy OptimizeResult)
    """
    # Separate fixed and free parameters
    free_param_names = [
        name for name in model.param_names if not model.is_param_fixed(name)
    ]
    fixed_params = {
        name: initial_params.get(name, model.get_param_value(name))
        for name in model.param_names
        if model.is_param_fixed(name)
    }

    if not free_param_names:
        # All parameters are fixed
        y_pred = model.evaluate(t_data, **initial_params)
        r_squared = calculate_r_squared(y_data, y_pred)
        sse = np.sum((y_data - y_pred) ** 2)

        result = FittingResult(
            fitted_params=initial_params.copy(),
            success=True,
            r_squared=r_squared,
            residual_sum_squares=sse,
            message="All parameters fixed",
            n_function_calls=1,
        )

        # Create dummy OptimizeResult
        opt_result = OptimizeResult(
            x=np.array([]),
            success=True,
            message="All parameters fixed",
            fun=sse,
            nfev=1,
        )

        return result, opt_result

    # Set up bounds for free parameters
    bounds = []
    x0 = []
    for name in free_param_names:
        bounds.append(model.get_param_bounds(name))
        x0.append(initial_params.get(name, model.get_param_value(name)))

    x0 = np.array(x0)

    # Create objective function
    objective = create_objective_function(
        model, t_data, y_data, free_param_names, fixed_params
    )

    # Suppress optimization warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        # Perform optimization
        opt_result = minimize(
            objective, x0, method=method, bounds=bounds, options={"maxiter": 1000}
        )

    # Extract fitted parameters
    fitted_params = fixed_params.copy()
    if opt_result.success and len(opt_result.x) == len(free_param_names):
        for i, name in enumerate(free_param_names):
            fitted_params[name] = float(opt_result.x[i])
    else:
        # Use initial values if optimization failed
        for name in free_param_names:
            fitted_params[name] = initial_params.get(name, model.get_param_value(name))

    # Calculate quality metrics
    try:
        y_pred = model.evaluate(t_data, **fitted_params)
        r_squared = calculate_r_squared(y_data, y_pred)
        sse = float(opt_result.fun) if opt_result.success else 1e6
    except Exception:
        r_squared = 0.0
        sse = 1e6

    result = FittingResult(
        fitted_params=fitted_params,
        success=opt_result.success,
        r_squared=r_squared,
        residual_sum_squares=sse,
        message=opt_result.message if hasattr(opt_result, "message") else "",
        n_function_calls=opt_result.nfev if hasattr(opt_result, "nfev") else 0,
    )

    return result, opt_result


def fit_model(
    model: ModelBase,
    t_data: np.ndarray,
    y_data: np.ndarray,
    method: str = "L-BFGS-B",
) -> FittingResult:
    """
    Perform single-start optimization for parameter estimation.

    Args:
        model: Model instance
        t_data: Time points
        y_data: Observed values
        method: Optimization method

    Returns:
        Fitting result
    """
    if len(t_data) != len(y_data):
        raise ValueError("Time and data arrays must have same length")

    # Remove NaN values
    mask = ~(np.isnan(t_data) | np.isnan(y_data))
    if np.sum(mask) < 2:
        # Not enough valid data points
        return FittingResult(
            fitted_params={
                name: model.get_param_value(name) for name in model.param_names
            },
            success=False,
            r_squared=0.0,
            residual_sum_squares=1e6,
            message="Insufficient valid data points",
            n_function_calls=0,
        )

    # Get default parameters
    default_params = {}
    for name in model.param_names:
        default_params[name] = model.get_param_value(name)

    # Estimate initial parameters from data if possible
    try:
        estimated_params = model.estimate_initial_params(t_data[mask], y_data[mask])
        default_params.update(estimated_params)
    except Exception:
        # Use model defaults if estimation fails
        pass

    # Perform single optimization
    try:
        result, _ = fit_single_start(model, t_data, y_data, default_params, method)
        return result
    except Exception as e:
        # Return failed result on error
        return FittingResult(
            fitted_params=default_params,
            success=False,
            r_squared=0.0,
            residual_sum_squares=1e6,
            message=f"Optimization failed: {str(e)}",
            n_function_calls=0,
        )


def fit_trace_data(
    trace_data: pd.DataFrame,
    model_type: str,
    cell_id: str | int,
    **model_params,
) -> FittingResult:
    """
    Fit model to a single cell's trace data.

    Args:
        trace_data: DataFrame containing trace data
        model_type: Type of model ('maturation', 'twostage', 'trivial')
        cell_id: Cell identifier to fit
        **model_params: Additional model parameter settings

    Returns:
        Fitting result for the cell
    """
    from ..models.maturation import MaturationModel
    from ..models.twostage import TwoStageModel
    from ..models.trivial import TrivialModel

    # Select model
    if model_type.lower() in ["maturation", "threestage"]:
        model = MaturationModel()
    elif model_type.lower() == "twostage":
        model = TwoStageModel()
    elif model_type.lower() == "trivial":
        model = TrivialModel()
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Apply any custom parameter settings
    for param_name, settings in model_params.items():
        if param_name in model.param_names:
            model.set_param(param_name, **settings)

    # Extract cell data
    cell_data = trace_data[trace_data["cell_id"] == cell_id].copy()
    if cell_data.empty:
        return FittingResult(
            fitted_params={
                name: model.get_param_value(name) for name in model.param_names
            },
            success=False,
            r_squared=0.0,
            residual_sum_squares=1e6,
            message=f"No data found for cell {cell_id}",
            n_function_calls=0,
        )

    # Sort by frame and extract time series
    cell_data = cell_data.sort_values("frame")

    if "frame" in cell_data.columns:
        t_data = cell_data["frame"].values.astype(float)
    else:
        t_data = np.arange(len(cell_data), dtype=float)

    # Use intensity_total as default, fallback to other columns
    if "intensity_total" in cell_data.columns:
        y_data = cell_data["intensity_total"].values.astype(float)
    elif "intensity" in cell_data.columns:
        y_data = cell_data["intensity"].values.astype(float)
    else:
        # Find first numeric column that's not frame/cell_id
        numeric_cols = cell_data.select_dtypes(include=[np.number]).columns
        value_cols = [col for col in numeric_cols if col not in ["frame", "cell_id"]]
        if value_cols:
            y_data = cell_data[value_cols[0]].values.astype(float)
        else:
            return FittingResult(
                fitted_params={
                    name: model.get_param_value(name) for name in model.param_names
                },
                success=False,
                r_squared=0.0,
                residual_sum_squares=1e6,
                message=f"No numeric data column found for cell {cell_id}",
                n_function_calls=0,
            )

    # Perform fitting
    return fit_model(model, t_data, y_data)
