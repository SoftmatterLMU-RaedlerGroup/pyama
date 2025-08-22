"""
Simplified fitting utilities for trace data analysis.
"""

import numpy as np
from dataclasses import dataclass
from scipy import optimize

from pyama_core.analysis.models import get_model, get_types


@dataclass
class FittingResult:
    """Container for model fitting results."""
    
    fitted_params: dict[str, float]
    success: bool
    r_squared: float = 0.0


def fit_model(
    model_type: str,
    t_data: np.ndarray,
    y_data: np.ndarray,
    user_params: dict[str, float] | None = None,
    user_bounds: dict[str, tuple[float, float]] | None = None,
) -> FittingResult:
    """
    Fit a model to time series data.
    
    Args:
        model_type: Type of model ('trivial', 'maturation', or 'maturation_blocked')
        t_data: Time points
        y_data: Observed values
        user_params: Optional initial parameters to override model defaults
        user_bounds: Optional parameter bounds to override model defaults
        
    Returns:
        FittingResult object
    """
    # Get model and types
    try:
        model = get_model(model_type.lower())
        types = get_types(model_type.lower())
    except ValueError:
        return FittingResult(
            fitted_params={},
            success=False,
            r_squared=0.0
        )
    
    # Type check user_params using UserParams TypedDict
    if user_params:
        UserParams = types['UserParams']
        # UserParams has optional fields, get all possible parameter names
        valid_params = set(UserParams.__annotations__.keys())
        invalid_params = set(user_params.keys()) - valid_params
        if invalid_params:
            raise ValueError(f"Invalid parameter names: {invalid_params}. Valid user parameters: {valid_params}")
    
    # Type check user_bounds using UserBounds TypedDict
    if user_bounds:
        UserBounds = types['UserBounds']
        # Get valid parameter names from UserBounds
        valid_params = set(UserBounds.__annotations__.keys())
        invalid_params = set(user_bounds.keys()) - valid_params
        if invalid_params:
            raise ValueError(f"Invalid parameter names in bounds: {invalid_params}. Valid user parameters: {valid_params}")
        
        # Check that bounds are tuples of (min, max)
        for param_name, bounds in user_bounds.items():
            if not isinstance(bounds, (tuple, list)) or len(bounds) != 2:
                raise ValueError(f"Bounds for {param_name} must be a tuple of (min, max), got {bounds}")
            if bounds[0] >= bounds[1]:
                raise ValueError(f"Invalid bounds for {param_name}: min ({bounds[0]}) must be less than max ({bounds[1]})")
    
    # Remove NaN values
    mask = ~(np.isnan(t_data) | np.isnan(y_data))
    n_valid_points = np.sum(mask)
    n_params = len(model.DEFAULTS)
    
    # Need at least as many data points as parameters to fit
    if n_valid_points < n_params:
        return FittingResult(
            fitted_params=model.DEFAULTS,
            success=False,
            r_squared=0.0
        )
    
    t_clean = t_data[mask]
    y_clean = y_data[mask]
    
    # Setup optimization
    param_names = list(model.DEFAULTS.keys())
    
    # Start with model defaults and update with any provided initial parameters
    initial_params = model.DEFAULTS.copy()
    if user_params:
        initial_params.update(user_params)
    
    # Create initial parameter array
    p0 = np.array([initial_params[name] for name in param_names])
    
    # Start with model bounds and update with any provided user bounds
    bounds_dict = model.BOUNDS.copy()
    if user_bounds:
        bounds_dict.update(user_bounds)
    
    lower_bounds = [bounds_dict[name][0] for name in param_names]
    upper_bounds = [bounds_dict[name][1] for name in param_names]
    
    # Objective function
    def residual_func(params):
        # Convert array to Params TypedDict for model.eval
        params_dict = dict(zip(param_names, params))
        y_pred = model.eval(t_clean, params_dict)
        return y_clean - y_pred
    
    # Perform optimization
    try:
        result = optimize.least_squares(
            residual_func,
            p0,
            bounds=(lower_bounds, upper_bounds),
            max_nfev=5000
        )
        
        # Calculate R-squared
        ss_res = np.sum(result.fun**2)
        ss_tot = np.sum((y_clean - np.mean(y_clean))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))
        
        # Convert result back to dict
        fitted_params = dict(zip(param_names, result.x))
        
        return FittingResult(
            fitted_params=fitted_params,
            success=result.success,
            r_squared=r_squared
        )
        
    except Exception:
        return FittingResult(
            fitted_params=model.DEFAULTS,
            success=False,
            r_squared=0.0
        )




