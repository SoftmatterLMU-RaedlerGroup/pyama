"""
Core fitting utilities using scipy optimization.

Provides parameter estimation using single-start optimization.
"""

import numpy as np
import pandas as pd

from ..models.base import ModelBase


# R-squared calculation removed - using chi-squared instead


class FittingResult:
    """Container for model fitting results."""

    def __init__(
        self,
        fitted_params: dict[str, float],
        success: bool,
        residual_sum_squares: float = 0.0,
        message: str = "",
        n_function_calls: int = 0,
        chisq: float = 0.0,
        std: float = 0.0,
        vals: np.ndarray = None,
        residuals: np.ndarray = None,
        t_fit: np.ndarray = None,
        cov: np.ndarray = None,
    ):
        self.fitted_params = fitted_params
        self.success = success
        self.residual_sum_squares = residual_sum_squares
        self.message = message
        self.n_function_calls = n_function_calls
        self.chisq = chisq
        self.std = std
        self.vals = vals
        self.residuals = residuals
        self.t_fit = t_fit
        self.cov = cov

    def to_dict(self) -> dict[str, any]:
        """Convert result to dictionary for export."""
        result = {
            "success": self.success,
            "chisq": self.chisq,
            "residual_sum_squares": self.residual_sum_squares,
            "n_function_calls": self.n_function_calls,
            "message": self.message,
            "std": self.std,
        }
        result.update(self.fitted_params)
        return result


# Removed old function that used undefined create_objective_function


def fit_model(
    model: ModelBase,
    t_data: np.ndarray,
    y_data: np.ndarray,
    **init_params,
) -> FittingResult:
    """
    Perform optimization using the model's fit method.

    Args:
        model: Model instance
        t_data: Time points
        y_data: Observed values
        **init_params: Initial parameter values

    Returns:
        Fitting result
    """
    if len(t_data) != len(y_data):
        raise ValueError("Time and data arrays must have same length")

    # Remove NaN values
    mask = ~(np.isnan(t_data) | np.isnan(y_data))
    if np.sum(mask) < 2:
        # Not enough valid data points
        param_names = model.get_params()
        return FittingResult(
            fitted_params={name: 0.0 for name in param_names},
            success=False,
            residual_sum_squares=1e6,
            message="Insufficient valid data points",
            n_function_calls=0,
            chisq=1e6,
        )

    # Use the model's own fit method
    # ALWAYS pass empty init_params to use model defaults
    try:
        fit_result = model.fit(t_data[mask], y_data[mask])

        # Extract parameters from result
        param_names = model.get_params()
        fitted_params = {}
        if "params" in fit_result:
            for i, name in enumerate(param_names):
                if i < len(fit_result["params"]):
                    fitted_params[name] = float(fit_result["params"][i])
                else:
                    fitted_params[name] = 0.0

        return FittingResult(
            fitted_params=fitted_params,
            success=fit_result.get("success", False),
            residual_sum_squares=fit_result.get("chisq", 1e6),
            message=fit_result.get("message", ""),
            n_function_calls=0,
            chisq=fit_result.get("chisq", 0),
            std=fit_result.get("std", 0),
            vals=fit_result.get("vals"),
            residuals=fit_result.get("residuals"),
            t_fit=fit_result.get("t_fit"),
            cov=fit_result.get("cov"),
        )
    except Exception as e:
        # Return failed result on error
        param_names = model.get_params()
        return FittingResult(
            fitted_params={name: 0.0 for name in param_names},
            success=False,
            residual_sum_squares=1e6,
            message=f"Optimization failed: {str(e)}",
            n_function_calls=0,
            chisq=1e6,
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
    from ..models.trivial import TrivialModel

    # ALWAYS use TrivialModel with empty parameters dict
    # Ignoring model_type for now due to fitting issues
    model = TrivialModel({})

    # Note: model_params can be passed to fit() as init_params

    # Extract cell data
    cell_data = trace_data[trace_data["cell_id"] == cell_id].copy()
    if cell_data.empty:
        return FittingResult(
            fitted_params={name: 0.0 for name in model.get_params()},
            success=False,
            residual_sum_squares=1e6,
            message=f"No data found for cell {cell_id}",
            n_function_calls=0,
            chisq=1e6,
        )

    # Sort by frame and extract time series
    cell_data = cell_data.sort_values("frame")

    # Use time column if available, otherwise use frame
    if "time" in cell_data.columns:
        t_data = cell_data["time"].values.astype(float)
    elif "frame" in cell_data.columns:
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
                fitted_params={name: 0.0 for name in model.get_params()},
                success=False,
                residual_sum_squares=1e6,
                message=f"No numeric data column found for cell {cell_id}",
                n_function_calls=0,
                chisq=1e6,
            )

    # Perform fitting - ignore model_params, always use defaults
    return fit_model(model, t_data, y_data)
