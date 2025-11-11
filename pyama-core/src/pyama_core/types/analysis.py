"""
Analysis types for model fitting.
"""

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(slots=True)
class FixedParam:
    """A single fixed parameter with just a value."""
    name: str
    value: float


@dataclass(slots=True)
class FitParam:
    """A single parameter to be fitted with value and bounds."""
    name: str
    value: float
    lb: float
    ub: float


# Type aliases for parameter dictionaries
FixedParams: TypeAlias = dict[str, FixedParam]
FitParams: TypeAlias = dict[str, FitParam]


@dataclass
class FittingResult:
    """Result of model fitting."""
    fixed_params: FixedParams
    fitted_params: FitParams
    success: bool
    r_squared: float = 0.0
    
    def to_dict(self) -> dict[str, float]:
        """Convert result to flat dictionary of parameter values."""
        result = {}
        # Add fixed parameters
        for param_name, param in self.fixed_params.items():
            result[param_name] = param.value
        # Add fit parameters
        for param_name, param in self.fitted_params.items():
            result[param_name] = param.value
        return result
