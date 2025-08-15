"""
Base classes and interfaces for fluorescence fitting models.
"""

from abc import ABC, abstractmethod
from typing import Any
import numpy as np


class ModelBase(ABC):
    """Abstract base class for fluorescence fitting models."""

    def __init__(self):
        self.params: dict[str, dict[str, Any]] = {}

    @abstractmethod
    def evaluate(self, t: np.ndarray, **params) -> np.ndarray:
        """
        Evaluate the model at given time points.

        Args:
            t: Array of time points
            **params: Model parameters

        Returns:
            Model values at time points
        """
        pass

    @property
    @abstractmethod
    def param_names(self) -> list[str]:
        """Return list of parameter names for this model."""
        pass

    @property
    @abstractmethod
    def default_bounds(self) -> dict[str, tuple[float, float]]:
        """Return default parameter bounds as {param_name: (min, max)}."""
        pass

    @property
    @abstractmethod
    def default_values(self) -> dict[str, float]:
        """Return default initial values for parameters."""
        pass

    def get_param_bounds(self, param_name: str) -> tuple[float, float]:
        """Get bounds for a specific parameter."""
        if param_name in self.params:
            param_info = self.params[param_name]
            min_val = param_info.get("min")
            max_val = param_info.get("max")

            # Use default bounds if not specified
            default_bounds = self.default_bounds
            if min_val is None:
                min_val = default_bounds[param_name][0]
            if max_val is None:
                max_val = default_bounds[param_name][1]

            return (min_val, max_val)
        else:
            return self.default_bounds[param_name]

    def get_param_value(self, param_name: str) -> float:
        """Get initial value for a specific parameter."""
        if param_name in self.params and "values" in self.params[param_name]:
            values = self.params[param_name]["values"]
            if values:
                return values[0]
        return self.default_values[param_name]

    def is_param_fixed(self, param_name: str) -> bool:
        """Check if a parameter is fixed during fitting."""
        if param_name in self.params:
            return self.params[param_name].get("fixed", False)
        return False

    def set_param(self, param_name: str, **kwargs):
        """Set parameter properties (bounds, values, fixed status)."""
        if param_name not in self.params:
            self.params[param_name] = {}

        for key, value in kwargs.items():
            if key == "value":
                # Store as single-element list for compatibility
                self.params[param_name]["values"] = [value]
            else:
                self.params[param_name][key] = value


class FittingResult:
    """Container for model fitting results."""

    def __init__(
        self,
        fitted_params: dict[str, float],
        success: bool,
        r_squared: float = 0.0,
        residual_sum_squares: float = 0.0,
        message: str = "",
        n_function_calls: int = 0,
    ):
        self.fitted_params = fitted_params
        self.success = success
        self.r_squared = r_squared
        self.residual_sum_squares = residual_sum_squares
        self.message = message
        self.n_function_calls = n_function_calls

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for export."""
        result = {
            "success": self.success,
            "r_squared": self.r_squared,
            "residual_sum_squares": self.residual_sum_squares,
            "n_function_calls": self.n_function_calls,
            "message": self.message,
        }
        result.update(self.fitted_params)
        return result
